"""Register the bridge for one explicit extension ID in the current user's browsers."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

HOST = 'com.mediafetch.desktop'
KEYS = [rf'Software\Google\Chrome\NativeMessagingHosts\{HOST}',
        rf'Software\Microsoft\Edge\NativeMessagingHosts\{HOST}']


def prepare(extension_id, directory=None):
    if not re.fullmatch('[a-p]{32}', extension_id):
        raise ValueError('Extension ID must be the 32 lowercase letters shown on the extensions page.')
    base = Path(__file__).resolve().parent
    destination = Path(directory) if directory else base / '.native'
    destination.mkdir(parents=True, exist_ok=True)
    python, host_script = str(Path(sys.executable).resolve()), str(base / 'native_host.py')
    if any(any(char in value for char in '"%\r\n!') for value in (python, host_script, str(destination))):
        raise ValueError('Move the app to a path without quotes, %, ! or newline characters.')
    launcher = destination / 'host.cmd'
    launcher.write_text(f'@echo off\n"{python}" "{host_script}" %*\n', encoding='utf-8')
    manifest = {'name': HOST, 'description': 'Media Fetch desktop connection', 'path': str(launcher.resolve()),
                'type': 'stdio', 'allowed_origins': [f'chrome-extension://{extension_id}/']}
    path = destination / 'host.json'
    path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return path.resolve()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extension_id', nargs='?')
    parser.add_argument('--uninstall', action='store_true')
    args = parser.parse_args()
    if os.name != 'nt':
        parser.error('This registration helper is for Windows.')
    import winreg
    if args.uninstall:
        for path in KEYS:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, path)
            except FileNotFoundError:
                pass
        print('Removed Media Fetch native host registration for this user.')
        return
    if not args.extension_id:
        parser.error('Provide the extension ID shown in chrome://extensions or edge://extensions.')
    manifest = prepare(args.extension_id)
    for path in KEYS:
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            winreg.SetValueEx(key, '', 0, winreg.REG_SZ, str(manifest))
    print('Connected Media Fetch to Chrome and Edge for extension ' + args.extension_id)
    print('Reload the extension, then click Check connection in its manager.')


if __name__ == '__main__':
    main()
