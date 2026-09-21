import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import Choice, DownloadJob, build_command, default_destination, fetch_playlist, find_ffmpeg, http_url, import_har, parse_playlist, redact, sanitize_filename

ROOT = Path(__file__).resolve().parents[2]


class ParserTests(unittest.TestCase):
    def test_trueid_qualities_and_separate_thai_audio(self):
        text = (ROOT / 'tests/fixtures/trueid-master.m3u8').read_text()
        choices = parse_playlist(text, 'https://fixture.invalid/master.m3u8')
        self.assertEqual([c.height for c in choices], [180, 240, 360, 480, 720, 1080])
        self.assertTrue(all(c.audio_name == 'Thai' and c.audio_url for c in choices))

    def test_aes_128_vod_is_supported_but_drm_and_local_urls_are_not(self):
        text = (ROOT / 'tests/fixtures/trueid-video.m3u8').read_text()
        choice = parse_playlist(text, 'https://fixture.invalid/video.m3u8')[0]
        self.assertEqual(choice.encryption, 'AES-128')
        self.assertAlmostEqual(choice.duration, 1414.84)
        with self.assertRaises(ValueError):
            parse_playlist(text.replace('METHOD=AES-128', 'METHOD=SAMPLE-AES'), choice.url)
        for bad in ['file:///secret', 'http://127.0.0.1/key']:
            with self.assertRaises(ValueError):
                parse_playlist(f'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="{bad}"\n#EXT-X-ENDLIST\n', 'https://cdn.invalid/m.m3u8')
        with self.assertRaises(ValueError):
            parse_playlist('#EXTM3U\n#EXT-X-KEY:METHOD=SAMPLE-AES,URI="https://cdn.invalid/k"\n#EXT-X-ENDLIST\n', 'https://cdn.invalid/m.m3u8')
        with self.assertRaises(ValueError):
            http_url('file:///C:/secret')

    def test_sanitize_filename_and_default_destination(self):
        self.assertEqual(sanitize_filename('Episode 1: The Pilot | TrueID'), 'Episode 1 The Pilot TrueID')
        self.assertEqual(sanitize_filename('   '), 'video')
        self.assertEqual(sanitize_filename('invalid/\\:*?"<>|name'), 'invalid name')
        with tempfile.TemporaryDirectory() as temp_dir:
            path1 = default_destination('My Video', folder=temp_dir)
            self.assertEqual(Path(path1).name, 'My Video.mp4')
            Path(path1).touch()
            path2 = default_destination('My Video', folder=temp_dir)
            self.assertEqual(Path(path2).name, 'My Video (1).mp4')

    def test_har_headers_and_signed_urls(self):
        master = '#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100,RESOLUTION=320x180\nvideo.m3u8?token=abc\n'
        entry = {'request': {'url': 'https://cdn.invalid/master.m3u8', 'headers': [
            {'name': 'Cookie', 'value': 'secret'}, {'name': 'Authorization', 'value': 'secret'},
            {'name': 'Origin', 'value': 'https://player.invalid'}]},
            'response': {'status': 200, 'content': {'mimeType': 'application/vnd.apple.mpegurl', 'text': master}}}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.har'
            path.write_text(json.dumps({'log': {'entries': [entry]}}))
            choice = import_har(path)[0]
        self.assertEqual(choice.url, 'https://cdn.invalid/video.m3u8?token=abc')
        self.assertEqual(choice.headers, {'Origin': 'https://player.invalid'})

    def test_command_maps_both_tracks_without_shell_or_transcoding(self):
        choice = Choice('https://cdn.invalid/video.m3u8', audio_url='https://cdn.invalid/audio.m3u8')
        command = build_command('ffmpeg', choice, 'a file.mp4')
        self.assertIn('1:a:0', command)
        self.assertEqual(command[command.index('-c') + 1], 'copy')
        self.assertNotIn('file', command[command.index('-protocol_whitelist') + 1].split(','))
        self.assertNotIn('secret', redact('HTTP error https://cdn.invalid/file?token=secret'))

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'video.mp4'; path.write_bytes(b'keep')
            events = []
            DownloadJob('unused', Choice('https://fixture.invalid/a.m3u8'), path, lambda *e: events.append(e)).run()
            self.assertEqual(path.read_bytes(), b'keep')
            self.assertTrue(any(e[0] == 'error' for e in events))

    def test_cancel_before_download(self):
        with tempfile.TemporaryDirectory() as directory:
            events = []
            job = DownloadJob('unused', Choice('https://fixture.invalid/a.m3u8'), Path(directory) / 'out.mp4', lambda *e: events.append(e))
            job.cancel(); job.run()
            self.assertTrue(any(e[0] == 'cancelled' for e in events))
            self.assertFalse(list(Path(directory).iterdir()))


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@unittest.skipUnless(find_ffmpeg(), 'FFmpeg unavailable')
class IntegrationTests(unittest.TestCase):
    def test_encrypted_video_plus_audio_become_decodable_mp4(self):
        ffmpeg = find_ffmpeg()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'key.bin').write_bytes(bytes(range(16)))
            (root / 'key.info').write_text('key.bin\n' + str(root / 'key.bin') + '\n')
            def run(args):
                result = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y'] + args,
                                        cwd=root, capture_output=True, text=True, timeout=40)
                self.assertEqual(result.returncode, 0, result.stderr)
                return result
            run(['-f', 'lavfi', '-i', 'testsrc=size=160x90:rate=10', '-t', '4', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-g', '10', '-an',
                 '-hls_time', '1', '-hls_playlist_type', 'vod', '-hls_key_info_file', str(root / 'key.info'), str(root / 'video.m3u8')])
            run(['-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=44100', '-t', '4', '-c:a', 'aac', '-vn',
                 '-hls_time', '1', '-hls_playlist_type', 'vod', str(root / 'audio.m3u8')])
            (root / 'master.m3u8').write_text('#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="a",NAME="Test audio",DEFAULT=YES,URI="audio.m3u8"\n#EXT-X-STREAM-INF:BANDWIDTH=200000,RESOLUTION=160x90,AUDIO="a"\nvideo.m3u8\n')
            server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=directory))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                choice = fetch_playlist(f'http://127.0.0.1:{server.server_port}/master.m3u8')[0]
                events = []
                output = root / 'result.mp4'
                DownloadJob(ffmpeg, choice, output, lambda *e: events.append(e)).run()
                self.assertTrue(output.exists(), events)
                self.assertTrue(any(e[0] == 'done' for e in events), events)
                self.assertFalse(list(root.glob('*.partial.mp4')))
                # Decode both streams, so a successful exit cannot hide a missing audio track.
                run(['-i', str(output), '-map', '0:v:0', '-map', '0:a:0', '-f', 'null', '-'])
            finally:
                server.shutdown(); server.server_close()

    def test_concurrent_download_jobs_run_in_parallel(self):
        ffmpeg = find_ffmpeg()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            def run(args):
                result = subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-y'] + args,
                                        cwd=root, capture_output=True, text=True, timeout=40)
                self.assertEqual(result.returncode, 0, result.stderr)
            run(['-f', 'lavfi', '-i', 'testsrc=size=160x90:rate=10', '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                 '-hls_time', '1', '-hls_playlist_type', 'vod', str(root / 'vod.m3u8')])
            server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=directory))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                choice = fetch_playlist(f'http://127.0.0.1:{server.server_port}/vod.m3u8')[0]
                out1 = root / 'concurrent1.mp4'
                out2 = root / 'concurrent2.mp4'
                events1, events2 = [], []
                job1 = DownloadJob(ffmpeg, choice, out1, lambda *e: events1.append(e))
                job2 = DownloadJob(ffmpeg, choice, out2, lambda *e: events2.append(e))
                t1 = threading.Thread(target=job1.run)
                t2 = threading.Thread(target=job2.run)
                t1.start()
                t2.start()
                t1.join(timeout=30)
                t2.join(timeout=30)
                self.assertTrue(out1.exists())
                self.assertTrue(out2.exists())
                self.assertTrue(any(e[0] == 'done' for e in events1))
                self.assertTrue(any(e[0] == 'done' for e in events2))
            finally:
                server.shutdown(); server.server_close()


if __name__ == '__main__':
    unittest.main()
