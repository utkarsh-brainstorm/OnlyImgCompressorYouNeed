# -*- mode: python ; coding: utf-8 -*-
# Light onefile build — uses OS native webview (WebKit2GTK / WKWebView / Edge).
# No Chromium/Qt bundled (same approach as Querii / AttendanceProcessor).

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = [
    "webview",
    "webview.platforms.gtk",
    "webview.platforms.cocoa",
    "webview.platforms.edgechromium",
    "gi",
    "gi.repository.GLib",
    "gi.repository.GObject",
    "gi.repository.Gio",
    "gi.repository.Gdk",
    "gi.repository.Gtk",
    "gi.repository.WebKit2",
    "gi.repository.cairo",
    "gi.repository.Pango",
]
hiddenimports += collect_submodules("core")

a = Analysis(
    ["onlyimg_compressor.py"],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6",
        "PyQt5",
        "PyQt6",
        "qtpy",
        "tkinter",
        "matplotlib",
        "numpy",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="OnlyImgCompressorYouNeed",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
