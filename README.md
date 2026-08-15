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

**Linux note:** pywebview needs a backend such as `webkit2gtk` or Qt WebEngine.

## Releases

1. Push a version tag, e.g. `v1.0.1`
2. GitHub Actions builds executables for all three platforms
3. Artifacts are attached to the GitHub Release automatically

```bash
git tag v1.0.1
git push origin v1.0.1
```

**Linux note:** the Linux zip is a folder (not a single file). It bundles **Qt WebEngine**, so it runs on typical Ubuntu / Fedora / Mint desktops without installing WebKitGTK or PyGObject. Unzip and run `OnlyImgCompressorYouNeed/OnlyImgCompressorYouNeed`.

You can also run the **Release** workflow manually from the Actions tab (`workflow_dispatch`).

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
