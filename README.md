# OnlyImgCompressorYouNeed

Intelligent batch image compressor with a target size range, optional resolution cap, and closest-match fallback.

Desktop app uses **pywebview + Pillow**. Tagged releases build standalone executables for **Windows**, **macOS**, and **Linux** via GitHub Actions.

## Features

- Pick files or folders (drag-and-drop on desktop)
- Target min/max output size (KB)
- Output formats: JPEG, PNG, WEBP, BMP
- Optional max resolution limit
- Live progress, result stack, and terminal log
- Writes into an `OnlyImg_Output` folder next to each source

## Run from source (desktop)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python onlyimg_compressor.py
```

**Linux:** needs system WebKit2GTK (keeps the download tiny — no Chromium bundled):

```bash
sudo apt install python3-gi python3-gi-cairo gir1.2-webkit2-4.1
# Fedora: sudo dnf install python3-gobject webkit2gtk4.1
```

## Releases

1. Push a version tag, e.g. `v1.0.2`
2. GitHub Actions uploads **plain binaries** (no zip) for Linux / Windows / macOS, plus an Android APK
3. Linux/macOS binaries are single files; Linux still expects WebKit2GTK on the machine (same model as Querii)

```bash
git tag v1.0.2
git push origin v1.0.2
```

You can also run the **Release** / **Android APK** workflows manually from the Actions tab.

## Project layout

| Path | Purpose |
|------|---------|
| `onlyimg_compressor.py` | Desktop UI (pywebview) |
| `core/` | Shared compression engine |
| `android/` | Native Android UI (Kivy) + Buildozer APK |

## Android

Native **Kivy** UI (no WebView) lives in [`android/`](android/). Same compression engine; Buildozer ships an APK. See [`android/README.md`](android/README.md).

Tag a release (`v*`) to also run the Android APK workflow, or trigger **Android APK** manually from Actions.

## License

MIT
