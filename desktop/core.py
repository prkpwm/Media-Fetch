"""HLS discovery and a cancellable FFmpeg download job. No third-party Python imports."""
import base64
import collections
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen


def http_url(value, base=None):
    value = urljoin(base or '', value)
    parts = urlsplit(value)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('Use an HTTP or HTTPS media URL without embedded credentials.')
    return value


def attrs(line):
    return {key: value.strip('"') for key, value in re.findall(r'([A-Z0-9-]+)=("[^"]*"|[^,]*)', line.split(':', 1)[1])}


@dataclass
class Choice:
    url: str
    height: int = 0
    bandwidth: int = 0
    audio_url: str = ''
    audio_name: str = ''
    encryption: str = ''
    duration: float = 0
    headers: dict = field(default_factory=dict)
    source: str = ''

    @property
    def label(self):
        quality = f'{self.height}p' if self.height else 'Original'
        bitrate = f' · {round(self.bandwidth / 1000)} kbps' if self.bandwidth else ''
        audio = f' · {self.audio_name}' if self.audio_name else ''
        return quality + bitrate + audio


def parse_playlist(text, base, headers=None):
    lines = [line.strip() for line in text.lstrip('\ufeff').splitlines() if line.strip()]
    if not lines or lines[0] != '#EXTM3U':
        raise ValueError('The response is not an HLS playlist. Paste the media URL, not the webpage URL.')
    keys = [attrs(line) for line in lines if line.startswith(('#EXT-X-KEY:', '#EXT-X-SESSION-KEY:'))]
    for key in keys:
        if key.get('METHOD') not in ('NONE', 'AES-128') or key.get('KEYFORMAT', 'identity') != 'identity':
            raise ValueError('This playlist uses unsupported encryption or DRM.')
        if key.get('URI'):
            http_url(key['URI'], base)
    encryption = 'AES-128' if any(k.get('METHOD') == 'AES-128' for k in keys) else ''
    tracks = [attrs(line) for line in lines if line.startswith('#EXT-X-MEDIA:')]
    choices = []
    for index, line in enumerate(lines):
        if not line.startswith('#EXT-X-STREAM-INF:'):
            continue
        a = attrs(line)
        if index + 1 >= len(lines) or lines[index + 1].startswith('#'):
            raise ValueError('Malformed HLS variant.')
        if a.get('VIDEO'):
            raise ValueError('Separate video rendition groups are unsupported.')
        candidates = [t for t in tracks if t.get('TYPE') == 'AUDIO' and t.get('GROUP-ID') == a.get('AUDIO')]
        track = next((t for t in candidates if t.get('DEFAULT') == 'YES'), candidates[0] if candidates else {})
        choices.append(Choice(http_url(lines[index + 1], base),
                              int(a.get('RESOLUTION', '0x0').split('x')[-1]), int(a.get('BANDWIDTH', 0)),
                              http_url(track['URI'], base) if track.get('URI') else '',
                              track.get('NAME', track.get('LANGUAGE', '')), encryption,
                              headers=dict(headers or {}), source=base))
    if choices:
        return sorted(choices, key=lambda c: (c.height, c.bandwidth))
    if '#EXT-X-ENDLIST' not in lines:
        raise ValueError('This version downloads completed VOD playlists, not live streams.')
    segments = [http_url(line, base) for line in lines if not line.startswith('#')]
    if not segments:
        raise ValueError('The playlist has no segments.')
    duration = sum(float(line.split(':', 1)[1].split(',')[0]) for line in lines if line.startswith('#EXTINF:'))
    return [Choice(base, encryption=encryption, duration=duration, headers=dict(headers or {}), source=base)]


def fetch_playlist(url, headers=None):
    request = Request(http_url(url), headers=headers or {'User-Agent': 'MediaFetchDesktop/1.0'})
    with urlopen(request, timeout=20) as response:
        final = http_url(response.url)
        body = response.read(4 * 1024 * 1024 + 1)
        if len(body) > 4 * 1024 * 1024:
            raise ValueError('Playlist exceeds 4 MiB.')
        return parse_playlist(body.decode('utf-8-sig'), final, headers)


def import_har(path):
    # Only normal playback context headers are retained. Never forward HAR cookies or authorization.
    with open(path, encoding='utf-8-sig') as handle:
        entries = json.load(handle)['log']['entries']
    playlists = {}
    has_dash_drm = False
    has_youtube_ump = False
    for entry in entries:
        response = entry.get('response', {})
        content = response.get('content', {})
        request = entry.get('request', {})
        url = request.get('url', '')
        mime = content.get('mimeType', '').lower()
        req_url_lower = url.lower()

        if ('.mpd' in req_url_lower or 'dash' in mime) and ('widevine' in req_url_lower or 'cenc' in (content.get('text', '') or '').lower() or 'default_kid' in (content.get('text', '') or '').lower()):
            has_dash_drm = True
        elif 'widevine' in req_url_lower or 'playready' in req_url_lower:
            has_dash_drm = True
        elif 'application/vnd.yt-ump' in mime or ('googlevideo.com' in req_url_lower and ('videoplayback' in req_url_lower or 'sabr=1' in req_url_lower)):
            has_youtube_ump = True

        if response.get('status') != 200 or not content.get('text'):
            continue
        if 'mpegurl' not in content.get('mimeType', '').lower() and not urlsplit(url).path.lower().endswith('.m3u8'):
            continue
        text = content['text']
        if content.get('encoding') == 'base64':
            text = base64.b64decode(text).decode('utf-8-sig')
        headers = {h['name']: h['value'] for h in request.get('headers', [])
                   if h['name'].lower() in ('user-agent', 'referer', 'origin') and '\r' not in h['value'] and '\n' not in h['value']}
        playlists[http_url(url)] = (text, headers)
    masters, media = [], []
    for url, (text, headers) in playlists.items():
        try:
            choices = parse_playlist(text, url, headers)
        except ValueError:
            continue
        target = masters if '#EXT-X-STREAM-INF:' in text else media
        for choice in choices:
            if choice.url in playlists:
                try:
                    child = parse_playlist(playlists[choice.url][0], choice.url)[0]
                    choice.encryption = child.encryption or choice.encryption
                    choice.duration = child.duration
                except ValueError:
                    pass
            target.append(choice)
    result = list({(c.url, c.audio_url): c for c in masters or media}.values())
    if not result:
        if has_dash_drm:
            raise ValueError('This capture contains an MPEG-DASH stream protected by Widevine DRM (CENC). DRM-protected media requires a secure browser CDM license exchange and cannot be decoded.')
        if has_youtube_ump:
            raise ValueError('This capture contains YouTube SABR/UMP media (application/vnd.yt-ump). Proprietary UMP chunked streams require session-bound initialization headers and signature deciphering, and cannot be decoded from a browser HAR capture.')
        raise ValueError('No supported HLS playlists with response bodies found in this HAR.')
    return result


def find_ffmpeg():
    vendor = Path(__file__).parent / '.vendor' / 'imageio_ffmpeg' / 'binaries'
    bundled = sorted(vendor.glob('ffmpeg*.exe')) if vendor.exists() else []
    return str(bundled[0]) if bundled else shutil.which('ffmpeg') or ''


def redact(message):
    return re.sub(r'https?://[^\s\]<>"\']+', '[media URL]', str(message))


def build_command(ffmpeg, choice, output):
    args = [str(ffmpeg), '-hide_banner', '-nostdin', '-y', '-loglevel', 'warning']
    for url in [choice.url] + ([choice.audio_url] if choice.audio_url else []):
        args += ['-protocol_whitelist', 'http,https,tcp,tls,crypto', '-rw_timeout', '20000000']
        for name, value in choice.headers.items():
            if '\r' in value or '\n' in value:
                raise ValueError('Invalid request header.')
            if name.lower() == 'user-agent':
                args += ['-user_agent', value]
            elif name.lower() == 'referer':
                args += ['-referer', value]
            elif name.lower() == 'origin':
                args += ['-headers', f'Origin: {value}\r\n']
        args += ['-i', http_url(url)]
    args += ['-map', '0:v:0', '-map', '1:a:0' if choice.audio_url else '0:a:0?', '-c', 'copy',
             '-movflags', '+faststart', '-progress', 'pipe:1', '-nostats', '-f', 'mp4', str(output)]
    return args


class DownloadJob:
    def __init__(self, ffmpeg, choice, destination, notify):
        self.ffmpeg, self.choice = ffmpeg, choice
        self.destination, self.notify = Path(destination), notify
        self.cancelled = threading.Event()
        self.process = None

    def cancel(self):
        self.cancelled.set()
        process = self.process
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            except OSError:
                pass

    def run(self):
        partial = None
        reader = None
        try:
            if self.destination.exists():
                raise ValueError('The destination already exists. Choose a new filename.')
            self.notify('status', 'Checking the current video and audio playlists…')
            for index, url in enumerate([self.choice.url] + ([self.choice.audio_url] if self.choice.audio_url else [])):
                if self.cancelled.is_set():
                    return
                selected = fetch_playlist(url, self.choice.headers)
                if len(selected) != 1 or selected[0].url != selected[0].source:
                    raise ValueError('Select a media quality, not a nested master playlist.')
                if index == 0:
                    self.choice.duration = selected[0].duration
            if self.cancelled.is_set():
                return
            fd, temporary = tempfile.mkstemp(prefix='.media-fetch-', suffix='.partial.mp4', dir=self.destination.parent)
            os.close(fd)
            partial = Path(temporary)
            args = build_command(self.ffmpeg, self.choice, partial)
            self.process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                            encoding='utf-8', errors='replace',
                                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            if self.cancelled.is_set():
                self.cancel()
            errors = collections.deque(maxlen=12)
            media_failed = threading.Event()
            def read_errors():
                for line in self.process.stderr:
                    errors.append(redact(line.strip()))
                    if re.search(r'failed to open segment|error when loading first segment|unable to open key|invalid data found', line, re.I):
                        media_failed.set()
            reader = threading.Thread(target=read_errors, daemon=True)
            reader.start()
            self.notify('status', 'Downloading and combining tracks into MP4…')
            processed = 0
            for line in self.process.stdout:
                name, _, value = line.strip().partition('=')
                if name == 'out_time_us' and value.isdigit():
                    seconds = int(value) / 1000000
                    processed = max(processed, seconds)
                    self.notify('progress', (seconds, self.choice.duration))
            code = self.process.wait()
            reader.join()
            if self.cancelled.is_set():
                return
            if code != 0 or not partial.stat().st_size:
                raise RuntimeError('FFmpeg could not finish the download. Recapture expired URLs; the server must allow access to all tracks and playback keys.\n' + '\n'.join(errors))
            if self.choice.duration and processed < self.choice.duration - max(1, self.choice.duration * 0.001):
                raise RuntimeError('The output ended before the expected playlist duration. The incomplete download was discarded.')
            if media_failed.is_set():
                raise RuntimeError('One or more media segments or keys failed to load. The incomplete download was discarded.')
            # Atomic, no-overwrite publication on the same filesystem.
            os.link(partial, self.destination)
            self.notify('done', str(self.destination))
        except Exception as error:
            if not self.cancelled.is_set():
                self.notify('error', redact(error))
        finally:
            if self.process:
                if self.process.poll() is None:
                    self.process.kill()
                    self.process.wait()
                if reader:
                    reader.join(timeout=3)
                self.process.stdout.close()
                self.process.stderr.close()
            if partial and partial.exists():
                partial.unlink()
            if self.cancelled.is_set():
                self.notify('cancelled', 'Cancelled. Partial download removed.')
            self.notify('finished', None)


def sanitize_filename(name, fallback='video', max_len=200):
    if not name or not isinstance(name, str):
        return fallback
    cleaned = re.sub(r'[\x00-\x1f\\/:*?"<>|]+', ' ', name)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip('. ')
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip('. ')
    return cleaned if cleaned else fallback


def default_destination(title=None, folder=None):
    base_folder = Path(folder) if folder else (Path.home() / 'Downloads')
    stem = sanitize_filename(title)
    candidate = base_folder / f'{stem}.mp4'
    if not candidate.exists():
        return str(candidate)
    counter = 1
    while (base_folder / f'{stem} ({counter}).mp4').exists():
        counter += 1
    return str(base_folder / f'{stem} ({counter}).mp4')

