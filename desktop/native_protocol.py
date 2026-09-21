"""Length-prefixed native messaging and a deliberately small message schema."""
import json
import struct
from urllib.parse import urlsplit
from core import Choice, http_url

MAX_MESSAGE = 64 * 1024


def read_exact(stream, count):
    result = bytearray()
    while len(result) < count:
        part = stream.read(count - len(result))
        if not part:
            raise ValueError('Incomplete native message.')
        result.extend(part)
    return bytes(result)


def read_message(stream):
    first = stream.read(1)
    if not first:
        return None
    length = struct.unpack('<I', first + read_exact(stream, 3))[0]
    if not 0 < length <= MAX_MESSAGE:
        raise ValueError('Invalid native message length.')
    result = json.loads(read_exact(stream, length).decode('utf-8'))
    if not isinstance(result, dict):
        raise ValueError('Native message must be an object.')
    return result


def write_message(stream, value):
    data = json.dumps(value, ensure_ascii=False).encode('utf-8')
    if len(data) > MAX_MESSAGE:
        raise ValueError('Native response is too large.')
    stream.write(struct.pack('<I', len(data)) + data)
    stream.flush()


def text_field(payload, key, limit=16384):
    value = payload.get(key, '')
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise ValueError(f'Invalid {key}.')
    return value


def number_field(payload, key, maximum):
    value = payload.get(key, 0)
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError(f'Invalid {key}.')
    return value


def parse_open(payload):
    url = http_url(text_field(payload, 'url'))
    page = text_field(payload, 'pageUrl')
    title = text_field(payload, 'title', 512)
    agent = text_field(payload, 'userAgent', 1024)
    headers = {}
    if page:
        page = http_url(page)
        parts = urlsplit(page)
        headers = {'Referer': page, 'Origin': f'{parts.scheme}://{parts.netloc}'}
    if agent:
        headers['User-Agent'] = agent
    selection = payload.get('selection')
    choice = None
    if selection is not None:
        if not isinstance(selection, dict):
            raise ValueError('Invalid quality selection.')
        video = http_url(text_field(selection, 'url'))
        audio = text_field(selection, 'audioUrl')
        choice = Choice(video, number_field(selection, 'height', 16384),
                        number_field(selection, 'bandwidth', 10**10),
                        http_url(audio) if audio else '', text_field(selection, 'audioName', 128),
                        headers=headers, source=url)
    return url, headers, title, choice
