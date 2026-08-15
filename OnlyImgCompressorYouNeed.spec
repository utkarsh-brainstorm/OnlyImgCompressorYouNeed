# -*- mode: python ; coding: utf-8 -*-
# Linux: onedir + bundled PySide6/QtWebEngine (true standalone, no system GTK/WebKit).
# Windows/macOS: onefile (OS webview backends).

import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

datas = []
binaries = []
hiddenimports = [
    "webview",
    "webview.platforms.qt",
    "webview.platforms.edgechromium",
    "webview.platforms.cocoa",
]

is_linux = sys.platform.startswith("linux")

if is_linux:
    for pkg in ("PySide6", "shiboken6"):
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden

a = Analysis(
    ["onlyimg_compressor.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if is_linux:
    # QtWebEngine needs helper binaries/resources beside the main exe
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="OnlyImgCompressorYouNeed",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        console=False,
        disable_windowed_traceback=False,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=False,
        upx_exclude=[],
        name="OnlyImgCompressorYouNeed",
    )
else:
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
