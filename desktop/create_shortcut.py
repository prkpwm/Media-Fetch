"""Create Windows shortcuts for Media Fetch in Taskbar, Start Menu, and Desktop."""
import os
from pathlib import Path
import sys

import pythoncom
from win32com.propsys import propsys, pscon
from win32com.shell import shell
import win32com.client

APP_ID = 'MediaFetch.Desktop.App.0.2'


def ensure_icon(ico_path):
    if ico_path.is_file() and ico_path.stat().st_size > 0:
        return
    from PIL import Image, ImageDraw
    sizes = [16, 32, 48, 64, 128, 256]
    images = []
    for s in sizes:
        img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        margin = max(1, s // 16)
        r = s // 4
        draw.rounded_rectangle([margin, margin, s - margin - 1, s - margin - 1],
                               radius=r, fill=(16, 21, 29, 255), outline=(43, 55, 70, 255), width=max(1, s // 32))
        color = (128, 228, 188, 255)
        cx = s / 2
        stem_w = max(2, s // 8)
        top_y = s * 0.22
        mid_y = s * 0.58
        draw.rectangle([cx - stem_w / 2, top_y, cx + stem_w / 2, mid_y], fill=color)
        head_w = s * 0.32
        head_y = s * 0.70
        draw.polygon([(cx - head_w, mid_y), (cx + head_w, mid_y), (cx, head_y)], fill=color)
        tray_y = s * 0.78
        tray_h = max(2, s // 10)
        tray_w = s * 0.32
        draw.rounded_rectangle([cx - tray_w, tray_y, cx + tray_w, tray_y + tray_h], radius=tray_h // 2, fill=color)
        images.append(img)
    images[-1].save(str(ico_path), format='ICO', sizes=[(s, s) for s in sizes])


def create_shortcut_file(lnk_path, target, args, workdir, icon_path):
    lnk_path.parent.mkdir(parents=True, exist_ok=True)
    sl = pythoncom.CoCreateInstance(
        shell.CLSID_ShellLink, None,
        pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
    )
    sl.SetPath(str(target))
    sl.SetArguments(args)
    sl.SetWorkingDirectory(str(workdir))
    sl.SetIconLocation(str(icon_path), 0)
    sl.SetDescription('Media Fetch Desktop Downloader')

    persist_file = sl.QueryInterface(pythoncom.IID_IPersistFile)
    persist_file.Save(str(lnk_path), 0)
    del persist_file
    del sl

    # Set Windows AppUserModelID property so the shortcut groups with the running process
    try:
        store = propsys.SHGetPropertyStoreFromParsingName(str(lnk_path), None, 2, propsys.IID_IPropertyStore)
        key = pscon.PKEY_AppUserModel_ID
        prop = propsys.PROPVARIANTType(APP_ID, pythoncom.VT_LPWSTR)
        store.SetValue(key, prop)
        store.Commit()
        del store
    except Exception as err:
        print(f'Note: Could not set AUMID on {lnk_path.name}: {err}')


def main():
    root = Path(__file__).resolve().parent
    ico_path = root / 'app.ico'
    ensure_icon(ico_path)

    python_dir = Path(sys.executable).parent
    pythonw = python_dir / 'pythonw.exe'
    target = pythonw if pythonw.is_file() else Path(sys.executable)
    app_py = root / 'app.py'

    wscript = win32com.client.Dispatch('WScript.Shell')
    destinations = []

    # 1. Project directories
    destinations.append(('Project folder', root / 'Media Fetch.lnk'))
    destinations.append(('Workspace root', root.parent / 'Media Fetch.lnk'))

    # 2. Taskbar Pinned folder
    taskbar_dir = Path(os.path.expandvars(r'%APPDATA%\Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar'))
    if taskbar_dir.exists():
        destinations.append(('Taskbar (User Pinned)', taskbar_dir / 'Media Fetch.lnk'))

    # 3. Start Menu Programs
    try:
        programs_dir = Path(wscript.SpecialFolders('Programs'))
        if programs_dir.exists():
            destinations.append(('Start Menu', programs_dir / 'Media Fetch.lnk'))
    except Exception:
        pass

    # 4. Desktop
    try:
        desktop_dir = Path(wscript.SpecialFolders('Desktop'))
        if desktop_dir.exists():
            destinations.append(('Desktop', desktop_dir / 'Media Fetch.lnk'))
    except Exception:
        pass

    created = []
    for label, dst in destinations:
        try:
            create_shortcut_file(dst, target, f'"{app_py}"', root, ico_path)
            created.append((label, dst))
            print(f'[OK] Created shortcut for {label}')
        except Exception as err:
            print(f'[FAIL] Failed to create shortcut for {label}: {err}')

    print(f'\nSuccess! Created {len(created)} shortcut(s).')
    print('Media Fetch is now available on your Taskbar, Start Menu, and Desktop.')


if __name__ == '__main__':
    main()
