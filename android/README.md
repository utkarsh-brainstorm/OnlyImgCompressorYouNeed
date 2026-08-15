# Android build (Kivy)

Native phone UI for OnlyImgCompressorYouNeed — **Kivy** (no WebView). Uses the same compression engine as desktop (`android/core`).

## Why Kivy

pywebview’s desktop WebView stack does not work as a production Android UI. Kivy draws with OpenGL ES and maps cleanly to touch screens, while Buildozer packages a Python APK.

## Run on a desktop (preview)

```bash
cd android
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

## Build an APK (Linux recommended)

Install [Buildozer](https://buildozer.readthedocs.io/) deps, then:

```bash
cd android
buildozer android debug
# APK → bin/onlyimgcompressor-*-arm64-v8a-debug.apk
```

Or use the **Android APK** GitHub Action (`workflow_dispatch` / version tags).

## UI map (desktop → Android)

| Desktop | Android |
|---------|---------|
| Dropzone / browse | Home → system image picker (plyer) |
| Config form | Config screen (min/max KB, format, max px) |
| Process + stack + terminal | Process screen + live result list |
| Summary / open folder | Done screen (path under Pictures/OnlyImg_Output) |

Outputs prefer a sibling `OnlyImg_Output` folder when writable; otherwise `Pictures/OnlyImg_Output`.
