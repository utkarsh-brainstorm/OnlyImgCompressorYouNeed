"""
OnlyImgCompressorYouNeed
Single-file desktop app (pywebview + Pillow) for batch image compression.

Dependencies: pywebview>=4.0, Pillow>=9.0
Ships as a standalone PyInstaller build for Windows / macOS / Linux via CI.
"""

import sys


# ------------------------------------------------------------------
# Guard against windowed/no-console builds where stdout/stderr are None
# (this happens with PyInstaller --windowed on Windows/macOS and would
# otherwise crash on the very first print()). Must run before anything
# else touches stdout/stderr.
# ------------------------------------------------------------------
class _NullStream:
    def write(self, *a, **k):
        pass

    def flush(self):
        pass

    def isatty(self):
        return False


if sys.stdout is None:
    sys.stdout = _NullStream()
if sys.stderr is None:
    sys.stderr = _NullStream()

import os
import json
import time
import threading
import traceback
import subprocess
import webbrowser
from datetime import datetime

try:
    import webview
except ImportError:
    print("Missing dependency: pywebview. Install with: pip install pywebview")
    sys.exit(1)

try:
    from PIL import Image  # noqa: F401 — validate install early
except ImportError:
    print("Missing dependency: Pillow. Install with: pip install Pillow")
    sys.exit(1)

from core import OUTPUT_FOLDER_NAME, collect_valid_images, process_single_image


# ==========================================
# CRASH LOGGING / GLOBAL EXCEPTION HOOKS
# ==========================================
def _crash_log_path():
    base = os.path.join(os.path.expanduser("~"), ".onlyimg_compressor")
    try:
        os.makedirs(base, exist_ok=True)
    except Exception:
        base = os.getcwd()
    return os.path.join(base, "crash.log")


def _write_crash(text):
    try:
        with open(_crash_log_path(), "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now().isoformat()} ---\n{text}\n")
    except Exception:
        pass


def _excepthook(exc_type, exc_value, exc_tb):
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    print(text)
    _write_crash(text)


sys.excepthook = _excepthook


def _thread_excepthook(args):
    text = "".join(
        traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback)
    )
    print(text)
    _write_crash(text)


threading.excepthook = _thread_excepthook


# ==========================================
# 1. HTML, CSS, AND JAVASCRIPT UI PAYLOAD
# ==========================================
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OnlyImgCompressorYouNeed</title>
    <style>
        :root {
            --bg: #f5f5f7;
            --surface: #ffffff;
            --text-main: #1d1d1f;
            --text-sub: #86868b;
            --accent: #0071e3;
            --accent-hover: #0077ed;
            --border: #d2d2d7;
            --success: #34c759;
            --error: #ff3b30;
            --warning: #ff9500;
            --ring: rgba(0, 113, 227, 0.4);
            --radius-lg: 18px;
            --radius-md: 12px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            user-select: none;
        }

        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-thumb { background: #d2d2d7; border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #b8b8bd; }
        ::-webkit-scrollbar-track { background: transparent; }

        body {
            background-color: var(--bg);
            color: var(--text-main);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            overflow: hidden;
        }

        .app-container {
            width: 100%;
            height: 100%;
            display: flex;
            flex-direction: column;
            padding: 30px;
            position: relative;
            min-height: 0;
        }

        header {
            text-align: center;
            margin-bottom: 16px;
            animation: fadeInDown 0.6s ease;
            flex-shrink: 0;
        }

        h1 {
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        p.subtitle {
            font-size: 14px;
            color: var(--text-sub);
            margin-top: 4px;
        }

        /* View Management */
        .view {
            display: none;
            opacity: 0;
            transform: translateY(10px);
            transition: opacity 0.3s ease, transform 0.3s ease;
            flex-grow: 1;
            flex-direction: column;
            min-height: 0;
        }

        .view.active {
            display: flex;
            opacity: 1;
            transform: translateY(0);
        }

        /* Dropzone */
        .dropzone {
            flex-grow: 1;
            border: 2px dashed var(--border);
            border-radius: var(--radius-lg);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            background-color: rgba(255, 255, 255, 0.5);
            transition: all 0.2s ease;
            cursor: pointer;
        }

        .dropzone.dragover {
            border-color: var(--accent);
            background-color: rgba(0, 113, 227, 0.05);
            transform: scale(1.01);
        }

        .drop-icon { font-size: 40px; margin-bottom: 15px; }
        .drop-text { font-size: 16px; font-weight: 500; color: var(--text-main); pointer-events: none; }
        .drop-subtext { font-size: 13px; color: var(--text-sub); margin-top: 8px; pointer-events: none; text-align: center; padding: 0 20px; }

        .browse-buttons { display: flex; gap: 15px; margin-top: 20px; }

        /* Form Elements */
        .form-card {
            background: var(--surface);
            padding: 25px;
            border-radius: var(--radius-lg);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
            margin-bottom: 20px;
            flex-shrink: 0;
        }

        #cfg-selection-info {
            font-size: 12.5px;
            font-weight: 600;
            color: var(--accent);
            margin-bottom: 16px;
        }

        .row { display: flex; gap: 20px; margin-bottom: 20px; }
        .form-group { flex: 1; display: flex; flex-direction: column; }

        label { font-size: 13px; font-weight: 600; margin-bottom: 6px; color: var(--text-main); }

        input, select {
            padding: 12px 14px;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            font-size: 15px;
            background: #fafafa;
            transition: all 0.15s ease;
            user-select: auto;
        }

        input:focus, select:focus {
            outline: none;
            border-color: var(--accent);
            background: var(--surface);
            box-shadow: 0 0 0 4px var(--ring);
        }

        input.invalid, select.invalid {
            border-color: var(--error) !important;
            box-shadow: 0 0 0 4px rgba(255, 59, 48, 0.12) !important;
        }

        .cfg-error {
            display: none;
            color: var(--error);
            font-size: 12.5px;
            font-weight: 600;
            margin-top: -8px;
            margin-bottom: 15px;
        }

        .hint-text { font-size: 12px; color: var(--text-sub); line-height: 1.5; }

        /* Buttons */
        button {
            background-color: var(--accent);
            color: white;
            border: none;
            border-radius: var(--radius-md);
            padding: 12px 24px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.15s ease;
            display: inline-flex;
            justify-content: center;
            align-items: center;
            gap: 6px;
        }

        button:hover { background-color: var(--accent-hover); }
        button:active { transform: scale(0.97); }
        button:focus-visible { outline: none; box-shadow: 0 0 0 4px var(--ring); }
        button:disabled { opacity: 0.45; cursor: not-allowed; transform: none; }

        button.secondary { background-color: #e8e8ed; color: var(--text-main); }
        button.secondary:hover { background-color: #d1d1d6; }

        .footer-actions { display: flex; justify-content: space-between; margin-top: auto; flex-shrink: 0; gap: 12px; }

        /* Process view (progress + live stack + terminal) */
        .process-card {
            background: var(--surface);
            border-radius: var(--radius-lg);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
            padding: 22px 25px;
            display: flex;
            flex-direction: column;
            flex-grow: 1;
            min-height: 0;
            margin-bottom: 20px;
        }

        .process-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 14px;
            flex-shrink: 0;
        }

        .process-header h3 { font-size: 17px; margin-bottom: 3px; }
        .proc-subtitle { font-size: 13px; color: var(--text-sub); }
        .process-actions { display: flex; gap: 10px; flex-shrink: 0; }

        .icon-btn {
            background: #e8e8ed;
            color: var(--text-main);
            font-family: "SF Mono", Menlo, Consolas, monospace;
            font-size: 12px;
            padding: 8px 14px;
        }
        .icon-btn:hover { background: #d1d1d6; }
        .icon-btn.active { background: var(--text-main); color: white; }
        .icon-btn.active:hover { background: #3a3a3c; }

        .progress-bar-bg {
            width: 100%;
            height: 9px;
            background: #e8e8ed;
            border-radius: 5px;
            overflow: hidden;
            margin: 4px 0 12px 0;
            flex-shrink: 0;
        }

        .progress-bar-fill {
            height: 100%;
            width: 0%;
            background: var(--accent);
            transition: width 0.3s ease;
        }

        .prog-file {
            font-size: 12px;
            color: var(--text-sub);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 14px;
            min-height: 16px;
            flex-shrink: 0;
        }

        .stack-wrap, .terminal-wrap {
            flex-grow: 1;
            min-height: 0;
            display: flex;
            flex-direction: column;
            border: 1px solid var(--border);
            border-radius: var(--radius-md);
            overflow: hidden;
        }
        .stack-wrap.hidden, .terminal-wrap.hidden { display: none; }

        .stack-head {
            display: grid;
            grid-template-columns: 2fr 1.1fr 2fr;
            padding: 9px 14px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            color: var(--text-sub);
            background: #fafafa;
            border-bottom: 1px solid var(--border);
            flex-shrink: 0;
        }

        .stack-list { overflow-y: auto; flex-grow: 1; min-height: 0; }

        .stack-empty {
            padding: 30px 14px;
            text-align: center;
            font-size: 13px;
            color: var(--text-sub);
        }

        .stack-item {
            padding: 10px 14px;
            border-bottom: 1px solid #f0f0f0;
            display: grid;
            grid-template-columns: 2fr 1.1fr 2fr;
            align-items: center;
            gap: 10px;
            font-size: 12.5px;
            animation: fadeInUp 0.25s ease;
        }
        .stack-item:last-child { border-bottom: none; }

        .stack-main { display: flex; align-items: center; gap: 8px; min-width: 0; }
        .stack-name { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

        .stack-badge {
            font-size: 10px;
            font-weight: 700;
            text-transform: uppercase;
            padding: 2px 7px;
            border-radius: 10px;
            flex-shrink: 0;
        }
        .stack-badge.b-pass { background: rgba(52, 199, 89, 0.15); color: #248a3d; }
        .stack-badge.b-warn { background: rgba(255, 149, 0, 0.15); color: #b36b00; }
        .stack-badge.b-fail { background: rgba(255, 59, 48, 0.15); color: #c42b23; }

        .stack-sizes { color: var(--text-sub); font-variant-numeric: tabular-nums; white-space: nowrap; }

        .stack-path {
            font-size: 11px;
            color: var(--text-sub);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            user-select: text;
        }
        .stack-item.status-fail .stack-path { color: var(--error); }

        .terminal-toolbar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 14px;
            background: #1d1d1f;
            color: #a8a8ac;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            font-weight: 700;
            flex-shrink: 0;
        }

        .mini-btn { background: #3a3a3c; color: white; padding: 5px 12px; font-size: 11px; border-radius: 8px; }
        .mini-btn:hover { background: #4a4a4c; }

        .terminal-output {
            flex-grow: 1;
            overflow-y: auto;
            background: #1d1d1f;
            color: #d1d1d6;
            font-family: "SF Mono", Menlo, Consolas, monospace;
            font-size: 12px;
            padding: 14px;
            white-space: pre-wrap;
            word-break: break-word;
            user-select: text;
            margin: 0;
        }
        .term-line { line-height: 1.6; }
        .term-error { color: #ff6961; }
        .term-warn { color: #ffb340; }
        .term-ok { color: #32d74b; }

        /* Error Banner */
        #error-banner {
            display: none;
            background: rgba(255, 59, 48, 0.1);
            color: var(--error);
            padding: 12px 14px;
            border-radius: var(--radius-md);
            margin-bottom: 15px;
            font-size: 13px;
            font-weight: 500;
            border: 1px solid rgba(255, 59, 48, 0.2);
            flex-shrink: 0;
        }

        /* Signature */
        .credit {
            position: absolute;
            bottom: 15px;
            right: 20px;
            font-size: 12px;
            color: #b0b0b5;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s, color 0.2s;
            letter-spacing: 0.2px;
        }
        .credit:hover { color: var(--accent); opacity: 1; }

        @keyframes fadeInDown { from { opacity: 0; transform: translateY(-15px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body>

    <div class="app-container">
        <header>
            <h1>OnlyImgCompressorYouNeed</h1>
            <p class="subtitle">Intelligent batch processing & upscaling engine</p>
        </header>

        <div id="error-banner"></div>

        <!-- VIEW 1: DROPZONE -->
        <div id="view-dropzone" class="view active">
            <div class="dropzone" id="dropzone">
                <div class="drop-icon">📦</div>
                <div class="drop-text">Drag & Drop Files or Folders Here</div>
                <div class="drop-subtext">Supports JPG, PNG, WEBP, BMP, GIF, TIFF and more</div>
                <div class="browse-buttons">
                    <button class="secondary" onclick="browseFiles()">Browse Files</button>
                    <button class="secondary" onclick="browseFolder()">Browse Folder</button>
                </div>
            </div>
        </div>

        <!-- VIEW 2: CONFIGURATION -->
        <div id="view-config" class="view">
            <div class="form-card">
                <p id="cfg-selection-info">No items selected</p>
                <div class="row">
                    <div class="form-group">
                        <label>Min Size (KB)</label>
                        <input type="number" id="cfg-min" value="50" min="1">
                    </div>
                    <div class="form-group">
                        <label>Max Size (KB)</label>
                        <input type="number" id="cfg-max" value="150" min="2">
                    </div>
                </div>
                <div class="row">
                    <div class="form-group">
                        <label>Output Format</label>
                        <select id="cfg-format">
                            <option value="JPEG">JPEG (.jpg)</option>
                            <option value="PNG">PNG (.png)</option>
                            <option value="WEBP">WEBP (.webp)</option>
                            <option value="BMP">BMP (.bmp)</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Max Resolution Limit (px)</label>
                        <input type="number" id="cfg-res" value="1920" min="0" placeholder="0 for no limit">
                    </div>
                </div>
                <p id="cfg-error" class="cfg-error"></p>
                <p class="hint-text">
                    * <b>Smart Engine:</b> if an image cannot reach your exact constraints, the closest possible output is saved automatically and marked "Closest".
                </p>
            </div>
            <div class="footer-actions">
                <button class="secondary" onclick="resetApp()">Cancel</button>
                <button id="start-btn" onclick="startProcessing()">Commence Engine</button>
            </div>
        </div>

        <!-- VIEW 3: PROCESSING (live progress + stack + terminal) -->
        <div id="view-process" class="view">
            <div class="process-card">
                <div class="process-header">
                    <div>
                        <h3 id="proc-title">Preparing</h3>
                        <p id="proc-subtitle" class="proc-subtitle">Scanning files</p>
                    </div>
                    <div class="process-actions">
                        <button class="icon-btn" id="terminal-toggle" onclick="toggleTerminal()" title="View raw terminal output">&gt;_ Terminal</button>
                        <button class="secondary" id="cancel-btn" onclick="cancelProcessing()">Cancel</button>
                    </div>
                </div>

                <div class="progress-bar-bg">
                    <div class="progress-bar-fill" id="prog-bar"></div>
                </div>
                <p id="prog-file" class="prog-file"></p>

                <div id="stack-wrap" class="stack-wrap">
                    <div class="stack-head">
                        <span>File</span><span>Size</span><span>Output / Notes</span>
                    </div>
                    <div id="stack-list" class="stack-list">
                        <div class="stack-empty" id="stack-empty-msg">Results will appear here as files finish processing…</div>
                    </div>
                </div>

                <div id="terminal-wrap" class="terminal-wrap hidden">
                    <div class="terminal-toolbar">
                        <span>Raw Output</span>
                        <button class="mini-btn" onclick="copyTerminal()">Copy</button>
                    </div>
                    <pre id="terminal-output" class="terminal-output"></pre>
                </div>
            </div>
            <div class="footer-actions" id="process-footer" style="display:none;">
                <button class="secondary" onclick="resetApp()">Process More Images</button>
                <button id="open-folder-btn" style="display:none;" onclick="openOutputFolder()">Open Output Folder</button>
            </div>
        </div>

        <!-- Signature Link -->
        <div class="credit" onclick="pywebview.api.open_link('https://github.com/utkarsh-brainstorm')">
            Made with ❤️ by Utkarsh
        </div>
    </div>

    <script>
        let selectedPaths = [];
        let terminalVisible = false;
        let lastOutDir = null;

        function switchView(viewId) {
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            setTimeout(() => {
                const el = document.getElementById(viewId);
                if (el) el.classList.add('active');
            }, 40);
            document.getElementById('error-banner').style.display = 'none';
        }

        function escapeHtml(s) {
            if (s === undefined || s === null) return '';
            return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
        }

        function showFatalError(msg) {
            switchView('view-config');
            const banner = document.getElementById('error-banner');
            banner.textContent = msg;
            banner.style.display = 'block';
        }

        function showProcessError(msg) {
            const banner = document.getElementById('error-banner');
            banner.textContent = msg;
            banner.style.display = 'block';
        }

        // --- Drag & Drop visual feedback (actual paths come from the native pywebview drop event) ---
        const dropzone = document.getElementById('dropzone');

        dropzone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzone.classList.add('dragover');
        });

        dropzone.addEventListener('dragleave', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
        });

        dropzone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzone.classList.remove('dragover');
            // Full filesystem paths are supplied by the native pywebview "dropped" event
            // (browsers do not expose real paths through the JS File API for security reasons).
        });

        // --- PyWebview Triggers ---
        function browseFiles() { pywebview.api.browse_files(); }
        function browseFolder() { pywebview.api.browse_folder(); }

        function handlePaths(paths) {
            if (!paths || paths.length === 0) return;
            selectedPaths = paths;
            document.getElementById('cfg-selection-info').textContent =
                paths.length === 1 ? '1 item selected' : (paths.length + ' items selected');
            validateConfig();
            switchView('view-config');
        }

        // --- Config validation ---
        function validateConfig() {
            const minEl = document.getElementById('cfg-min');
            const maxEl = document.getElementById('cfg-max');
            const resEl = document.getElementById('cfg-res');
            const errBox = document.getElementById('cfg-error');
            const startBtn = document.getElementById('start-btn');

            minEl.classList.remove('invalid');
            maxEl.classList.remove('invalid');
            resEl.classList.remove('invalid');

            const min = parseFloat(minEl.value);
            const max = parseFloat(maxEl.value);
            const res = resEl.value.trim() === '' ? 0 : parseFloat(resEl.value);

            let error = null;

            if (isNaN(min) || min < 1) { error = 'Min size must be at least 1 KB.'; minEl.classList.add('invalid'); }
            else if (isNaN(max) || max < 2) { error = 'Max size must be at least 2 KB.'; maxEl.classList.add('invalid'); }
            else if (max <= min) { error = 'Max size must be greater than min size.'; maxEl.classList.add('invalid'); minEl.classList.add('invalid'); }
            else if (max > 500000) { error = 'Max size is unreasonably large (limit 500,000 KB).'; maxEl.classList.add('invalid'); }
            else if (isNaN(res) || res < 0) { error = 'Resolution limit cannot be negative.'; resEl.classList.add('invalid'); }

            if (error) {
                errBox.textContent = error;
                errBox.style.display = 'block';
                startBtn.disabled = true;
                return false;
            }
            errBox.style.display = 'none';
            startBtn.disabled = false;
            return true;
        }

        ['cfg-min', 'cfg-max', 'cfg-res'].forEach(id => {
            document.getElementById(id).addEventListener('input', validateConfig);
        });

        function startProcessing() {
            if (!validateConfig() || selectedPaths.length === 0) return;

            const minKb = parseFloat(document.getElementById('cfg-min').value);
            const maxKb = parseFloat(document.getElementById('cfg-max').value);
            const resVal = document.getElementById('cfg-res').value.trim();
            const maxRes = resVal === '' ? 0 : parseInt(resVal, 10);
            const format = document.getElementById('cfg-format').value;

            document.getElementById('stack-list').innerHTML = '<div class="stack-empty" id="stack-empty-msg">Results will appear here as files finish processing…</div>';
            document.getElementById('terminal-output').innerHTML = '';
            document.getElementById('process-footer').style.display = 'none';
            document.getElementById('open-folder-btn').style.display = 'none';
            const cancelBtn = document.getElementById('cancel-btn');
            cancelBtn.style.display = 'inline-flex';
            cancelBtn.disabled = false;
            cancelBtn.textContent = 'Cancel';
            document.getElementById('prog-bar').style.width = '0%';
            document.getElementById('proc-title').textContent = 'Preparing';
            document.getElementById('proc-subtitle').textContent = 'Scanning files…';
            document.getElementById('prog-file').textContent = '';

            switchView('view-process');
            pywebview.api.start_processing(selectedPaths, minKb, maxKb, maxRes, format);
        }

        function cancelProcessing() {
            const btn = document.getElementById('cancel-btn');
            btn.textContent = 'Cancelling…';
            btn.disabled = true;
            pywebview.api.cancel_processing();
        }

        function setScanning(msg) {
            document.getElementById('proc-title').textContent = 'Preparing';
            document.getElementById('proc-subtitle').textContent = msg;
        }

        function setCurrentFile(name, sizeKb) {
            document.getElementById('prog-file').textContent = 'Processing: ' + name + ' (' + sizeKb + ' KB)';
        }

        function setProgress(done, total) {
            const pct = total > 0 ? Math.round((done / total) * 100) : 0;
            document.getElementById('prog-bar').style.width = pct + '%';
            document.getElementById('proc-title').textContent = 'Processing ' + done + ' of ' + total;
            document.getElementById('proc-subtitle').textContent = pct + '% complete';
        }

        function addStackEntry(entry) {
            const emptyMsg = document.getElementById('stack-empty-msg');
            if (emptyMsg) emptyMsg.remove();

            const list = document.getElementById('stack-list');
            let cls = 'fail';
            if (entry.status === 'Pass') cls = 'pass';
            if (entry.status === 'Closest') cls = 'warn';

            const detail = entry.status === 'Fail' ? (entry.msg || 'Failed') : (entry.out_path || entry.msg || '');

            const row = document.createElement('div');
            row.className = 'stack-item status-' + cls;
            row.innerHTML =
                '<div class="stack-main">' +
                    '<span class="stack-name" title="' + escapeHtml(entry.name) + '">' + escapeHtml(entry.name) + '</span>' +
                    '<span class="stack-badge b-' + cls + '">' + escapeHtml(entry.status) + '</span>' +
                '</div>' +
                '<div class="stack-sizes">' + escapeHtml(entry.old_kb) + ' → ' + escapeHtml(entry.new_kb) + '</div>' +
                '<div class="stack-path" title="' + escapeHtml(detail) + '">' + escapeHtml(detail) + '</div>';

            list.appendChild(row);
            list.scrollTop = list.scrollHeight;
        }

        function appendTerminal(line, level) {
            const out = document.getElementById('terminal-output');
            const div = document.createElement('div');
            div.className = 'term-line term-' + (level || 'info');
            div.textContent = line;
            out.appendChild(div);
            out.scrollTop = out.scrollHeight;
            while (out.children.length > 2000) out.removeChild(out.firstChild);
        }

        function toggleTerminal() {
            terminalVisible = !terminalVisible;
            document.getElementById('terminal-wrap').classList.toggle('hidden', !terminalVisible);
            document.getElementById('stack-wrap').classList.toggle('hidden', terminalVisible);
            document.getElementById('terminal-toggle').classList.toggle('active', terminalVisible);
        }

        function copyTerminal() {
            const text = document.getElementById('terminal-output').innerText;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(flashCopied).catch(() => fallbackCopy(text));
            } else {
                fallbackCopy(text);
            }
        }

        function fallbackCopy(text) {
            const ta = document.createElement('textarea');
            ta.value = text;
            ta.style.position = 'fixed';
            ta.style.opacity = '0';
            document.body.appendChild(ta);
            ta.focus();
            ta.select();
            try { document.execCommand('copy'); flashCopied(); } catch (e) { /* clipboard unavailable */ }
            document.body.removeChild(ta);
        }

        function flashCopied() {
            const btn = document.querySelector('.mini-btn');
            if (!btn) return;
            const old = btn.textContent;
            btn.textContent = 'Copied!';
            setTimeout(() => { btn.textContent = old; }, 1200);
        }

        function finishProcessing(summary) {
            document.getElementById('proc-title').textContent = summary.cancelled ? 'Cancelled' : 'Complete';
            document.getElementById('proc-subtitle').textContent =
                summary.passed + ' passed · ' + summary.closest + ' closest match · ' + summary.failed + ' failed · ' + summary.elapsed + 's';
            document.getElementById('prog-file').textContent = '';
            document.getElementById('cancel-btn').style.display = 'none';
            document.getElementById('process-footer').style.display = 'flex';

            const openBtn = document.getElementById('open-folder-btn');
            if (summary.outDir) {
                lastOutDir = summary.outDir;
                openBtn.style.display = 'inline-flex';
            } else {
                lastOutDir = null;
                openBtn.style.display = 'none';
            }
        }

        function openOutputFolder() {
            if (lastOutDir) pywebview.api.open_output_folder(lastOutDir);
        }

        function resetApp() {
            selectedPaths = [];
            document.getElementById('stack-list').innerHTML = '';
            document.getElementById('terminal-output').innerHTML = '';
            document.getElementById('prog-bar').style.width = '0%';
            switchView('view-dropzone');
        }

        validateConfig();
    </script>
</body>
</html>
"""


# ==========================================
# 2. PYWEBVIEW API BRIDGE
# ==========================================
class CompressorAPI:
    def __init__(self):
        self.window = None
        self.cancel_event = threading.Event()

    # ---- low-level JS bridge helpers, all failure-safe ----
    def _js_call(self, func, *args):
        if not self.window:
            return
        try:
            payload = json.dumps(list(args))
            self.window.evaluate_js(f"window.{func}.apply(null, {payload})")
        except Exception as e:
            print(f"[JS-BRIDGE ERROR] {func}: {e}")

    def log(self, msg, level="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        try:
            print(line)
        except Exception:
            pass
        self._js_call("appendTerminal", line, level)

    # ---- file / folder selection ----
    def browse_files(self):
        try:
            result = self.window.create_file_dialog(
                webview.OPEN_DIALOG,
                allow_multiple=True,
                file_types=(
                    "Image Files (*.jpg;*.jpeg;*.png;*.webp;*.bmp;*.gif;*.tiff;*.tif)",
                    "All files (*.*)",
                ),
            )
            if result:
                self._js_call("handlePaths", list(result))
        except Exception as e:
            print(f"[DIALOG ERROR] {e}")
            self._js_call("showFatalError", "Could not open the file browser.")

    def browse_folder(self):
        try:
            result = self.window.create_file_dialog(webview.FOLDER_DIALOG)
            if result:
                self._js_call("handlePaths", list(result))
        except Exception as e:
            print(f"[DIALOG ERROR] {e}")
            self._js_call("showFatalError", "Could not open the folder browser.")

    def handle_native_drop(self, *args):
        # pywebview's dropped-event payload shape has varied across versions
        # (plain list of strings, list of file objects with a .path, or a dict).
        try:
            paths = []
            for a in args:
                if isinstance(a, str):
                    paths.append(a)
                elif isinstance(a, dict):
                    paths.extend(a.get("paths") or a.get("files") or [])
                elif isinstance(a, (list, tuple)):
                    for item in a:
                        if isinstance(item, str):
                            paths.append(item)
                        elif hasattr(item, "path"):
                            paths.append(item.path)
                elif hasattr(a, "path"):
                    paths.append(a.path)
            paths = [p for p in paths if p]
            if paths:
                self._js_call("handlePaths", paths)
        except Exception as e:
            print(f"[DROP ERROR] {e}")

    def open_link(self, url):
        try:
            webbrowser.open(url)
        except Exception as e:
            print(f"[LINK ERROR] {e}")

    def open_output_folder(self, path):
        try:
            if not path or not os.path.isdir(path):
                return
            if sys.platform.startswith("win"):
                os.startfile(path)  # noqa: S606 - user-triggered, local path only
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.log(f"Could not open folder: {e}", "error")

    # ---- processing lifecycle ----
    def cancel_processing(self):
        self.cancel_event.set()
        self.log("Cancel requested — finishing the current file, then stopping.", "warn")

    def start_processing(self, paths, min_kb, max_kb, max_res, out_format):
        try:
            min_kb = float(min_kb)
            max_kb = float(max_kb)
            max_res = int(float(max_res or 0))
        except (TypeError, ValueError):
            self._js_call("showFatalError", "Invalid configuration values received.")
            return

        if not paths:
            self._js_call("showFatalError", "No files or folders selected.")
            return
        if min_kb < 1 or max_kb < 2 or max_kb <= min_kb or max_res < 0:
            self._js_call("showFatalError", "Configuration error: check your size and resolution values.")
            return
        if out_format not in ("JPEG", "PNG", "WEBP", "BMP"):
            out_format = "JPEG"

        self.cancel_event.clear()
        threading.Thread(
            target=self._run_batch_safely,
            args=(paths, min_kb, max_kb, max_res, out_format),
            daemon=True,
        ).start()

    def _run_batch_safely(self, paths, min_kb, max_kb, max_res, out_format):
        try:
            self._run_batch(paths, min_kb, max_kb, max_res, out_format)
        except Exception as e:
            tb = traceback.format_exc()
            print(f"CRITICAL ERROR IN BATCH THREAD:\n{tb}")
            _write_crash(tb)
            self._js_call("appendTerminal", f"CRITICAL ENGINE FAILURE: {e}", "error")
            self._js_call("showProcessError", f"Engine failure: {str(e)[:80]}. Open Terminal to see full details.")
            self._js_call(
                "finishProcessing",
                {"total": 0, "passed": 0, "closest": 0, "failed": 0, "elapsed": 0, "cancelled": False, "outDir": None},
            )

    def _run_batch(self, paths, min_kb, max_kb, max_res, out_format):
        start_time = time.time()
        min_bytes = int(min_kb * 1024)
        max_bytes = int(max_kb * 1024)

        self.log("Starting batch process.")
        self.log(f"Config: {min_kb}KB - {max_kb}KB | max resolution: {max_res or 'none'} | format: {out_format}")

        self._js_call("setScanning", f"Scanning {len(paths)} selected item(s)…")

        def _scan_progress(done, total_scan):
            self._js_call("setScanning", f"Validating file {done}/{total_scan}…")

        valid_images = collect_valid_images(paths, on_progress=_scan_progress)
        self.log(f"Found {len(valid_images)} valid image(s) after scan.")

        total = len(valid_images)
        if total == 0:
            self.log("No valid image files found in the selection.", "error")
            self._js_call("showFatalError", "No valid image files found in the selection.")
            return

        self.log(f"{total} valid image(s) discovered. Processing…")

        used_paths = set()
        output_dirs = set()
        passed = closest = failed = 0
        cancelled = False

        for i, img_path in enumerate(valid_images, 1):
            if self.cancel_event.is_set():
                cancelled = True
                self.log("Processing cancelled by user.", "warn")
                break

            name = os.path.basename(img_path)
            try:
                orig_kb = os.path.getsize(img_path) / 1024
            except OSError:
                orig_kb = 0.0

            self._js_call("setCurrentFile", name, round(orig_kb, 1))
            self._js_call("setProgress", i - 1, total)
            self.log(f"Processing {name} ({orig_kb:.1f} KB)")

            try:
                out_dir = os.path.join(os.path.dirname(img_path) or ".", OUTPUT_FOLDER_NAME)
                os.makedirs(out_dir, exist_ok=True)
                res = process_single_image(img_path, out_dir, min_bytes, max_bytes, max_res, out_format, used_paths)
            except PermissionError:
                res = {"name": name, "old_kb": f"{orig_kb:.1f} KB", "new_kb": "-", "out_path": "",
                       "status": "Fail", "msg": "Permission denied creating output folder."}
            except Exception as e:
                res = {"name": name, "old_kb": f"{orig_kb:.1f} KB", "new_kb": "-", "out_path": "",
                       "status": "Fail", "msg": f"Unexpected error: {str(e)[:40]}"}
                self.log(f"UNEXPECTED ERROR on {name}:\n{traceback.format_exc()}", "error")

            if res["status"] == "Pass":
                passed += 1
                self.log(f"{name}: {res['old_kb']} -> {res['new_kb']} (Pass) -> {res['out_path']}", "ok")
            elif res["status"] == "Closest":
                closest += 1
                self.log(f"{name}: {res['old_kb']} -> {res['new_kb']} (Closest) -> {res['out_path']}", "warn")
            else:
                failed += 1
                self.log(f"{name}: FAILED - {res['msg']}", "error")

            if res.get("out_path"):
                output_dirs.add(os.path.dirname(res["out_path"]))

            self._js_call("addStackEntry", res)
            self._js_call("setProgress", i, total)

        elapsed = round(time.time() - start_time, 1)
        self.log(f"Batch finished in {elapsed}s — {passed} passed, {closest} closest, {failed} failed.")

        summary = {
            "total": total,
            "passed": passed,
            "closest": closest,
            "failed": failed,
            "elapsed": elapsed,
            "cancelled": cancelled,
            "outDir": next(iter(output_dirs)) if len(output_dirs) == 1 else None,
        }
        self._js_call("finishProcessing", summary)


# ==========================================
# 3. APPLICATION ENTRY POINT
# ==========================================
if __name__ == "__main__":
    api = CompressorAPI()

    window = None
    try:
        window = webview.create_window(
            title="OnlyImgCompressorYouNeed",
            html=HTML_CONTENT,
            js_api=api,
            width=850,
            height=650,
            min_size=(750, 580),
            background_color="#f5f5f7",
        )
        api.window = window

        if hasattr(window, "events") and hasattr(window.events, "dropped"):
            try:
                window.events.dropped += api.handle_native_drop
            except Exception as e:
                print(f"Could not bind native drop event: {e}")

        webview.start(debug=os.environ.get("OIC_DEBUG") == "1")

    except Exception as e:
        err_text = f"Failed to launch GUI: {e}\n{traceback.format_exc()}"
        print(err_text)
        _write_crash(err_text)
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "OnlyImgCompressorYouNeed — Startup Error",
                "The application window could not be started.\n\n"
                f"{e}\n\n"
                "On Linux, make sure webkit2gtk (or qtwebengine) is installed.\n\n"
                f"A detailed log was saved to:\n{_crash_log_path()}",
            )
            root.destroy()
        except Exception:
            pass
        sys.exit(1)
