[app]

title = OnlyImgCompressor
package.name = onlyimgcompressor
package.domain = com.onlyimg

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
source.exclude_dirs = .buildozer,bin,.git,__pycache__
source.exclude_patterns = *.pyc,*.apk

version = 1.0.1

# Pin Python 3.11 — Kivy 2.3.x Cython code breaks on CPython 3.14 (_PyLong_AsByteArray)
requirements = python3==3.11.13,kivy==2.3.0,pillow,plyer,pyjnius,android

orientation = portrait
fullscreen = 0
android.presplash_color = #F5F5F7

android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
# Single arch = smaller/faster CI APK (covers modern phones)
android.archs = arm64-v8a

# Skip heavy unused modules where possible
android.add_src =

[buildozer]

log_level = 2
warn_on_root = 1
