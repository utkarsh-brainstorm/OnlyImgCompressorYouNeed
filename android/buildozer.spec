[app]

title = OnlyImgCompressor
package.name = onlyimgcompressor
package.domain = com.onlyimg

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
source.exclude_dirs = .buildozer,bin,.git,__pycache__
source.exclude_patterns = *.pyc,*.apk

version = 1.0.2

# hostpython3 and python3 MUST match
requirements = hostpython3==3.11.10,python3==3.11.10,kivy==2.3.0,pillow,plyer,pyjnius,android

orientation = portrait
fullscreen = 0
android.presplash_color = #F5F5F7

android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES
android.api = 34
android.minapi = 24
android.ndk = 26b
android.accept_sdk_license = True
android.archs = arm64-v8a

# Use current p4a with Android/NDK compile fixes
p4a.branch = master

android.add_src =

[buildozer]

log_level = 2
warn_on_root = 1
