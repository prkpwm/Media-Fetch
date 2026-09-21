"""Chrome/Edge launch this via host.cmd. stdout is ONLY framed native messages."""
import json
import os
from pathlib import Path
import sys
import threading
from native_protocol import read_message, write_message


def main():
    config = json.loads((Path(__file__).parent / '.native' / 'host.json').read_text(encoding='utf-8'))
    if len(sys.argv) < 2 or sys.argv[1] not in config['allowed_origins']:
        return 1
    if os.name == 'nt':
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    source, output = sys.stdin.buffer, sys.stdout.buffer
    lock = threading.Lock()
    def reply(value):
        with lock:
            write_message(output, value)
    from app import App
    app = App(native_reply=reply)
    app.withdraw()
    def listen():
        try:
            while True:
                message = read_message(source)
                if message is None:
                    break
                app.emit('native_request', message)
        except (ValueError, OSError):
            pass
        finally:
            app.emit('native_disconnect', None)
    threading.Thread(target=listen, daemon=True).start()
    app.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
