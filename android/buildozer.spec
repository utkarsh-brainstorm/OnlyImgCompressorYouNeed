[app]

title = OnlyImgCompressor
package.name = onlyimgcompressor
package.domain = com.onlyimg

source.dir = .
source.include_exts = py,png,jpg,kv,atlas,ttf
source.exclude_dirs = .buildozer,bin,.git,__pycache__
source.exclude_patterns = *.pyc,*.apk

version = 1.0.0

# Keep the APK lean: only what the UI + engine need
requirements = python3,kivy==2.3.0,pillow,plyer,android,pyjnius

orientation = portrait
fullscreen = 0
android.presplash_color = #F5F5F7

android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE,READ_MEDIA_IMAGES
android.api = 33
android.minapi = 24
android.ndk = 25b
android.accept_sdk_license = True
android.archs = arm64-v8a,armeabi-v7a

# Release APK (unsigned). Sign locally or in CI with your keystore.
android.release_artifact = apk

# Skip heavy unused modules where possible
android.add_src =

[buildozer]

log_level = 2
warn_on_root = 1
