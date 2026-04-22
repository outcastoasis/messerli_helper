# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path


project_root = Path(SPECPATH).resolve()
sys.path.insert(0, str(project_root))

from app.metadata import APP_EXECUTABLE_NAME

onefile = os.environ.get("PYINSTALLER_ONEFILE", "0") == "1"
app_name = APP_EXECUTABLE_NAME
version_file = project_root / "packaging" / "windows" / "version_info.txt"
icon_file = project_root / "packaging" / "windows" / "app.ico"
splash_image_file = project_root / "packaging" / "windows" / "app-preview.png"

exe_options = {
    "name": app_name,
    "debug": False,
    "bootloader_ignore_signals": False,
    "strip": False,
    "upx": True,
    "upx_exclude": [],
    "runtime_tmpdir": None,
    "console": False,
    "disable_windowed_traceback": False,
    "argv_emulation": False,
    "target_arch": None,
    "codesign_identity": None,
    "entitlements_file": None,
}

if version_file.exists():
    exe_options["version"] = str(version_file)

if icon_file.exists():
    exe_options["icon"] = str(icon_file)

a = Analysis(
    [str(project_root / "app" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / "examples" / "project_templates.json"), "examples"),
        (str(project_root / "packaging" / "windows" / "app.ico"), "packaging/windows"),
        *[
            (str(path), "app/ui/assets")
            for path in (project_root / "app" / "ui" / "assets").glob("*")
            if path.is_file()
        ],
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

splash = None
if splash_image_file.exists():
    splash = Splash(
        str(splash_image_file),
        binaries=a.binaries,
        datas=a.datas,
        text_pos=None,
        text_size=12,
        minify_script=True,
        always_on_top=True,
    )

if onefile:
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.datas,
        *([splash, splash.binaries] if splash is not None else []),
        [],
        **exe_options,
    )
else:
    exe = EXE(
        pyz,
        a.scripts,
        *([splash] if splash is not None else []),
        [],
        exclude_binaries=True,
        **exe_options,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.datas,
        *([splash.binaries] if splash is not None else []),
        strip=False,
        upx=True,
        upx_exclude=[],
        name=app_name,
    )
