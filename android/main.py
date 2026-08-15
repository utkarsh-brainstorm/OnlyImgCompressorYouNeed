"""
OnlyImgCompressorYouNeed — Android
Native Kivy UI (no WebView). Shares the same compression engine as desktop.
"""

from __future__ import annotations

import os
import threading
import time
import traceback

from kivy.app import App
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.recycleview import RecycleView
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivy.uix.screenmanager import Screen, ScreenManager, SlideTransition
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.utils import platform

from core import OUTPUT_FOLDER_NAME, collect_valid_images, process_single_image

# Soft daylight palette — light APK, calm phone UI
COLORS = {
    "bg": (0.965, 0.965, 0.969, 1),
    "surface": (1, 1, 1, 1),
    "text": (0.114, 0.114, 0.122, 1),
    "muted": (0.525, 0.525, 0.545, 1),
    "accent": (0.02, 0.443, 0.890, 1),
    "accent_press": (0.02, 0.38, 0.78, 1),
    "line": (0.824, 0.824, 0.843, 1),
    "ok": (0.20, 0.78, 0.35, 1),
    "warn": (1.0, 0.58, 0.0, 1),
    "fail": (1.0, 0.23, 0.19, 1),
    "chip": (0.91, 0.91, 0.93, 1),
}

Window.clearcolor = COLORS["bg"]

Builder.load_string(
    """
<ResultList>:
    viewclass: 'ResultRow'
    RecycleBoxLayout:
        default_size: None, dp(76)
        default_size_hint: 1, None
        size_hint_y: None
        height: self.minimum_height
        orientation: 'vertical'
        spacing: dp(8)
        padding: dp(2)
"""
)


def _try_filechooser(on_selection):
    """Android-safe picker via plyer; falls back to a simple path prompt on desktop."""
    try:
        from plyer import filechooser

        filechooser.open_file(
            title="Select images",
            filters=[("Images", "*.jpg", "*.jpeg", "*.png", "*.webp", "*.bmp", "*.gif", "*.tif", "*.tiff")],
            multiple=True,
            on_selection=on_selection,
        )
        return
    except Exception:
        pass

    # Desktop/dev fallback when plyer is unavailable
    from kivy.uix.popup import Popup

    box = BoxLayout(orientation="vertical", padding=dp(16), spacing=dp(10))
    tip = Label(
        text="Enter a folder or file path\n(Android builds use the system picker)",
        color=COLORS["muted"],
        halign="center",
    )
    tip.bind(size=lambda *_: setattr(tip, "text_size", tip.size))
    inp = TextInput(multiline=False, size_hint_y=None, height=dp(44), font_size=dp(15))
    row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
    popup = Popup(title="Path", content=box, size_hint=(0.9, None), height=dp(220))

    def ok(*_):
        path = inp.text.strip()
        popup.dismiss()
        if path:
            on_selection([path])

    row.add_widget(PillButton("Cancel", secondary=True, on_press=lambda *_: popup.dismiss()))
    row.add_widget(PillButton("Use path", on_press=ok))
    box.add_widget(tip)
    box.add_widget(inp)
    box.add_widget(row)
    popup.open()


def default_output_root() -> str:
    """Writable Pictures-style location on Android; cwd sibling on desktop."""
    if platform == "android":
        try:
            from android.storage import primary_external_storage_path  # type: ignore

            root = os.path.join(primary_external_storage_path(), "Pictures", OUTPUT_FOLDER_NAME)
            os.makedirs(root, exist_ok=True)
            return root
        except Exception:
            pass
        try:
            from jnius import autoclass  # type: ignore

            Environment = autoclass("android.os.Environment")
            pictures = Environment.getExternalStoragePublicDirectory(
                Environment.DIRECTORY_PICTURES
            ).getAbsolutePath()
            root = os.path.join(pictures, OUTPUT_FOLDER_NAME)
            os.makedirs(root, exist_ok=True)
            return root
        except Exception:
            pass
        app = App.get_running_app()
        root = os.path.join(app.user_data_dir, OUTPUT_FOLDER_NAME)
        os.makedirs(root, exist_ok=True)
        return root

    root = os.path.join(os.path.expanduser("~"), "Pictures", OUTPUT_FOLDER_NAME)
    os.makedirs(root, exist_ok=True)
    return root


class SoftPanel(BoxLayout):
    """Rounded surface without heavy card chrome."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.padding = kwargs.get("padding", (dp(18), dp(16)))
        self.spacing = kwargs.get("spacing", dp(12))
        with self.canvas.before:
            Color(*COLORS["surface"])
            self._bg = RoundedRectangle(radius=[dp(16)] * 4)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


class PillButton(ButtonBehavior, Label):
    def __init__(self, text="", secondary=False, danger=False, **kwargs):
        self.secondary = secondary
        self.danger = danger
        super().__init__(**kwargs)
        self.text = text
        self.bold = True
        self.font_size = dp(15)
        self.size_hint_y = None
        self.height = dp(48)
        self.halign = "center"
        self.valign = "middle"
        self.color = COLORS["text"] if secondary else (1, 1, 1, 1)
        with self.canvas.before:
            self._c = Color(*(COLORS["chip"] if secondary else (COLORS["fail"] if danger else COLORS["accent"])))
            self._bg = RoundedRectangle(radius=[dp(14)] * 4)
        self.bind(pos=self._sync, size=self._sync, text=self._fit)

    def _fit(self, *_):
        self.text_size = (self.width, None)

    def _sync(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size
        self.text_size = (self.width, self.height)

    def on_press(self):
        if self.secondary:
            self._c.rgba = (0.84, 0.84, 0.86, 1)
        elif self.danger:
            self._c.rgba = (0.85, 0.18, 0.15, 1)
        else:
            self._c.rgba = COLORS["accent_press"]

    def on_release(self):
        if self.secondary:
            self._c.rgba = COLORS["chip"]
        elif self.danger:
            self._c.rgba = COLORS["fail"]
        else:
            self._c.rgba = COLORS["accent"]


class ProgressTrack(Widget):
    value = NumericProperty(0.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(10)
        with self.canvas:
            Color(*COLORS["chip"])
            self._track = RoundedRectangle(radius=[dp(5)] * 4)
            Color(*COLORS["accent"])
            self._fill = RoundedRectangle(radius=[dp(5)] * 4)
        self.bind(pos=self._redraw, size=self._redraw, value=self._redraw)

    def _redraw(self, *_):
        self._track.pos = self.pos
        self._track.size = self.size
        w = max(0.0, min(1.0, float(self.value))) * self.width
        self._fill.pos = self.pos
        self._fill.size = (w, self.height)


class Field(BoxLayout):
    def __init__(self, label, default="", numeric=False, **kwargs):
        super().__init__(orientation="vertical", size_hint_y=None, height=dp(74), spacing=dp(4), **kwargs)
        self.add_widget(
            Label(
                text=label,
                color=COLORS["text"],
                bold=True,
                font_size=dp(13),
                size_hint_y=None,
                height=dp(20),
                halign="left",
                text_size=(None, None),
            )
        )
        self.input = TextInput(
            text=str(default),
            multiline=False,
            input_filter="float" if numeric else None,
            background_color=(0.98, 0.98, 0.98, 1),
            foreground_color=COLORS["text"],
            cursor_color=COLORS["accent"],
            padding=[dp(12), dp(12), dp(12), dp(12)],
            font_size=dp(16),
            size_hint_y=None,
            height=dp(46),
            write_tab=False,
        )
        self.add_widget(self.input)


class ResultRow(RecycleDataViewBehavior, BoxLayout):
    index = None

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", padding=(dp(12), dp(10)), size_hint_y=None, height=dp(72), **kwargs)
        self.spacing = dp(2)
        with self.canvas.before:
            Color(1, 1, 1, 1)
            self._bg = RoundedRectangle(radius=[dp(12)] * 4)
        self.title = Label(bold=True, color=COLORS["text"], font_size=dp(14), halign="left", valign="middle", size_hint_y=None, height=dp(22))
        self.meta = Label(color=COLORS["muted"], font_size=dp(12), halign="left", valign="middle", size_hint_y=None, height=dp(18))
        self.note = Label(color=COLORS["muted"], font_size=dp(11), halign="left", valign="middle", size_hint_y=None, height=dp(16))
        for w in (self.title, self.meta, self.note):
            w.bind(size=lambda inst, *_: setattr(inst, "text_size", (inst.width, None)))
            self.add_widget(w)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def refresh_view_attrs(self, rv, index, data):
        self.index = index
        status = data.get("status", "")
        color = {"Pass": COLORS["ok"], "Closest": COLORS["warn"], "Fail": COLORS["fail"]}.get(status, COLORS["muted"])
        self.title.text = data.get("name", "")
        self.title.color = COLORS["text"]
        self.meta.text = f"{data.get('old_kb', '-')}  →  {data.get('new_kb', '-')}   ·   {status}"
        self.meta.color = color
        self.note.text = data.get("msg") or data.get("out_path", "")
        return super().refresh_view_attrs(rv, index, data)


class ResultList(RecycleView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.viewclass = "ResultRow"
        self.data = []


# ---------- Screens ----------

class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = FloatLayout()
        col = BoxLayout(
            orientation="vertical",
            padding=(dp(22), dp(28), dp(22), dp(22)),
            spacing=dp(18),
            size_hint=(1, 1),
        )

        brand = Label(
            text="OnlyImg",
            font_size=dp(34),
            bold=True,
            color=COLORS["text"],
            size_hint_y=None,
            height=dp(42),
            halign="left",
        )
        brand.bind(size=lambda *_: setattr(brand, "text_size", brand.size))
        sub = Label(
            text="Compress to a size band.\nClosest match if exact isn’t possible.",
            font_size=dp(15),
            color=COLORS["muted"],
            size_hint_y=None,
            height=dp(48),
            halign="left",
        )
        sub.bind(size=lambda *_: setattr(sub, "text_size", sub.size))

        panel = SoftPanel(orientation="vertical", size_hint_y=None, height=dp(210))
        panel.add_widget(
            Label(
                text="Images",
                bold=True,
                color=COLORS["text"],
                font_size=dp(16),
                size_hint_y=None,
                height=dp(24),
            )
        )
        self.count_lbl = Label(
            text="Nothing selected yet",
            color=COLORS["muted"],
            font_size=dp(14),
            size_hint_y=None,
            height=dp(40),
            halign="left",
        )
        self.count_lbl.bind(size=lambda *_: setattr(self.count_lbl, "text_size", self.count_lbl.size))
        panel.add_widget(self.count_lbl)
        panel.add_widget(Widget())
        panel.add_widget(PillButton("Choose photos", on_press=self.pick))
        panel.add_widget(PillButton("Continue", secondary=True, on_press=self.go_config))

        col.add_widget(brand)
        col.add_widget(sub)
        col.add_widget(panel)
        col.add_widget(Widget())
        credit = Label(
            text="Smart engine · local only",
            color=COLORS["muted"],
            font_size=dp(12),
            size_hint_y=None,
            height=dp(20),
        )
        col.add_widget(credit)
        root.add_widget(col)
        self.add_widget(root)

    def on_pre_enter(self, *_):
        app = App.get_running_app()
        n = len(app.selected_paths)
        self.count_lbl.text = f"{n} item(s) selected" if n else "Nothing selected yet"

    def pick(self, *_):
        _try_filechooser(self._on_picked)

    @mainthread
    def _on_picked(self, selection):
        if not selection:
            return
        app = App.get_running_app()
        app.selected_paths = list(selection)
        self.count_lbl.text = f"{len(selection)} item(s) selected"

    def go_config(self, *_):
        app = App.get_running_app()
        if not app.selected_paths:
            self.count_lbl.text = "Pick at least one image or folder first"
            self.count_lbl.color = COLORS["fail"]
            return
        self.count_lbl.color = COLORS["muted"]
        self.manager.transition = SlideTransition(direction="left", duration=0.22)
        self.manager.current = "config"


class ConfigScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        wrap = BoxLayout(orientation="vertical", padding=(dp(22), dp(18)), spacing=dp(12))

        title = Label(
            text="Target sizes",
            bold=True,
            font_size=dp(24),
            color=COLORS["text"],
            size_hint_y=None,
            height=dp(36),
            halign="left",
        )
        title.bind(size=lambda *_: setattr(title, "text_size", title.size))
        wrap.add_widget(title)

        scroll = ScrollView(do_scroll_x=False, bar_width=dp(3))
        form = BoxLayout(orientation="vertical", spacing=dp(10), size_hint_y=None, padding=(0, 0, 0, dp(12)))
        form.bind(minimum_height=form.setter("height"))

        self.min_f = Field("Min size (KB)", "50", numeric=True)
        self.max_f = Field("Max size (KB)", "150", numeric=True)
        self.res_f = Field("Max resolution (px, 0 = none)", "1920", numeric=True)

        fmt_box = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(74), spacing=dp(4))
        fmt_box.add_widget(
            Label(text="Output format", bold=True, color=COLORS["text"], font_size=dp(13), size_hint_y=None, height=dp(20))
        )
        self.format = Spinner(
            text="JPEG",
            values=("JPEG", "PNG", "WEBP", "BMP"),
            size_hint_y=None,
            height=dp(46),
            background_color=COLORS["chip"],
            color=COLORS["text"],
            font_size=dp(15),
        )
        fmt_box.add_widget(self.format)

        hint = Label(
            text="If an image can’t hit the band exactly, the closest result is kept and marked Closest.",
            color=COLORS["muted"],
            font_size=dp(12),
            size_hint_y=None,
            height=dp(48),
            halign="left",
        )
        hint.bind(size=lambda *_: setattr(hint, "text_size", (hint.width, None)))

        self.err = Label(text="", color=COLORS["fail"], font_size=dp(13), size_hint_y=None, height=dp(22))

        for w in (self.min_f, self.max_f, fmt_box, self.res_f, hint, self.err):
            form.add_widget(w)
        scroll.add_widget(form)
        wrap.add_widget(scroll)

        actions = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        actions.add_widget(PillButton("Back", secondary=True, on_press=self.back))
        actions.add_widget(PillButton("Start", on_press=self.start))
        wrap.add_widget(actions)
        self.add_widget(wrap)

    def back(self, *_):
        self.manager.transition = SlideTransition(direction="right", duration=0.22)
        self.manager.current = "home"

    def start(self, *_):
        try:
            min_kb = float(self.min_f.input.text)
            max_kb = float(self.max_f.input.text)
            max_res = int(float(self.res_f.input.text or 0))
        except ValueError:
            self.err.text = "Check your numbers"
            return
        if min_kb < 1 or max_kb < 2 or max_kb <= min_kb or max_res < 0:
            self.err.text = "Min must be < max; resolution ≥ 0"
            return
        self.err.text = ""
        app = App.get_running_app()
        app.config_values = {
            "min_kb": min_kb,
            "max_kb": max_kb,
            "max_res": max_res,
            "format": self.format.text,
        }
        self.manager.transition = SlideTransition(direction="left", duration=0.22)
        self.manager.current = "process"


class ProcessScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cancel = threading.Event()
        self._worker = None

        root = BoxLayout(orientation="vertical", padding=(dp(18), dp(16)), spacing=dp(10))
        head = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        titles = BoxLayout(orientation="vertical")
        self.title_lbl = Label(text="Working", bold=True, font_size=dp(20), color=COLORS["text"], halign="left", size_hint_y=None, height=dp(28))
        self.sub_lbl = Label(text="Preparing…", font_size=dp(13), color=COLORS["muted"], halign="left", size_hint_y=None, height=dp(20))
        for t in (self.title_lbl, self.sub_lbl):
            t.bind(size=lambda inst, *_: setattr(inst, "text_size", inst.size))
            titles.add_widget(t)
        head.add_widget(titles)
        self.cancel_btn = PillButton("Stop", secondary=True, on_press=self.cancel)
        self.cancel_btn.size_hint_x = None
        self.cancel_btn.width = dp(88)
        head.add_widget(self.cancel_btn)

        self.bar = ProgressTrack()
        self.file_lbl = Label(text="", color=COLORS["muted"], font_size=dp(12), size_hint_y=None, height=dp(18), halign="left")
        self.file_lbl.bind(size=lambda *_: setattr(self.file_lbl, "text_size", self.file_lbl.size))

        self.results = ResultList()

        root.add_widget(head)
        root.add_widget(self.bar)
        root.add_widget(self.file_lbl)
        root.add_widget(self.results)
        self.add_widget(root)

    def on_enter(self, *_):
        self._cancel.clear()
        self.results.data = []
        self.bar.value = 0
        self.title_lbl.text = "Working"
        self.sub_lbl.text = "Scanning…"
        self.cancel_btn.disabled = False
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def cancel(self, *_):
        self._cancel.set()
        self.sub_lbl.text = "Stopping after current file…"

    def _run(self):
        app = App.get_running_app()
        cfg = app.config_values
        paths = app.selected_paths
        min_bytes = int(cfg["min_kb"] * 1024)
        max_bytes = int(cfg["max_kb"] * 1024)
        max_res = cfg["max_res"]
        out_format = cfg["format"]
        start = time.time()

        @mainthread
        def scan_prog(done, total):
            self.sub_lbl.text = f"Validating {done}/{total}"

        try:
            valid = collect_valid_images(paths, on_progress=scan_prog)
        except Exception as e:
            self._fail(str(e))
            return

        total = len(valid)
        if total == 0:
            self._fail("No valid images in selection")
            return

        out_root = default_output_root()
        used = set()
        passed = closest = failed = 0
        cancelled = False

        @mainthread
        def set_total():
            self.title_lbl.text = f"0 / {total}"
            self.sub_lbl.text = f"Saving to {out_root}"

        set_total()

        for i, path in enumerate(valid, 1):
            if self._cancel.is_set():
                cancelled = True
                break

            name = os.path.basename(path)
            try:
                orig_kb = os.path.getsize(path) / 1024
            except OSError:
                orig_kb = 0.0

            @mainthread
            def tick_start(n=name, kb=orig_kb, idx=i):
                self.file_lbl.text = f"{n}  ({kb:.1f} KB)"
                self.title_lbl.text = f"{idx - 1} / {total}"
                self.bar.value = (idx - 1) / float(total)

            tick_start()

            # Prefer sibling OnlyImg_Output when writable; else shared Pictures folder
            sibling = os.path.join(os.path.dirname(path) or ".", OUTPUT_FOLDER_NAME)
            try:
                os.makedirs(sibling, exist_ok=True)
                probe = os.path.join(sibling, ".write_test")
                with open(probe, "w") as f:
                    f.write("1")
                os.remove(probe)
                out_dir = sibling
            except Exception:
                out_dir = out_root

            try:
                res = process_single_image(path, out_dir, min_bytes, max_bytes, max_res, out_format, used)
            except Exception as e:
                res = {
                    "name": name,
                    "old_kb": f"{orig_kb:.1f} KB",
                    "new_kb": "-",
                    "out_path": "",
                    "status": "Fail",
                    "msg": str(e)[:60],
                }

            if res["status"] == "Pass":
                passed += 1
            elif res["status"] == "Closest":
                closest += 1
            else:
                failed += 1

            @mainthread
            def push(r=res, idx=i):
                self.results.data = list(self.results.data) + [dict(r)]
                self.title_lbl.text = f"{idx} / {total}"
                self.bar.value = idx / float(total)

            push()

        summary = {
            "total": total,
            "passed": passed,
            "closest": closest,
            "failed": failed,
            "elapsed": round(time.time() - start, 1),
            "cancelled": cancelled,
            "out_dir": out_root,
        }
        self._done(summary)

    @mainthread
    def _fail(self, msg):
        app = App.get_running_app()
        app.last_summary = {
            "total": 0,
            "passed": 0,
            "closest": 0,
            "failed": 1,
            "elapsed": 0,
            "cancelled": False,
            "out_dir": default_output_root(),
            "error": msg,
        }
        self.manager.transition = SlideTransition(direction="left", duration=0.22)
        self.manager.current = "done"

    @mainthread
    def _done(self, summary):
        App.get_running_app().last_summary = summary
        self.cancel_btn.disabled = True
        self.manager.transition = SlideTransition(direction="left", duration=0.22)
        self.manager.current = "done"


class DoneScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", padding=(dp(22), dp(28)), spacing=dp(14))
        self.headline = Label(
            text="Done",
            bold=True,
            font_size=dp(28),
            color=COLORS["text"],
            size_hint_y=None,
            height=dp(40),
            halign="left",
        )
        self.headline.bind(size=lambda *_: setattr(self.headline, "text_size", self.headline.size))
        self.body = Label(
            text="",
            font_size=dp(15),
            color=COLORS["muted"],
            size_hint_y=None,
            height=dp(120),
            halign="left",
            valign="top",
        )
        self.body.bind(size=lambda *_: setattr(self.body, "text_size", self.body.size))

        root.add_widget(self.headline)
        root.add_widget(self.body)
        root.add_widget(Widget())
        root.add_widget(PillButton("Compress more", on_press=self.again))
        root.add_widget(PillButton("Exit", secondary=True, on_press=lambda *_: App.get_running_app().stop()))
        self.add_widget(root)

    def on_pre_enter(self, *_):
        s = App.get_running_app().last_summary or {}
        if s.get("error"):
            self.headline.text = "Couldn’t run"
            self.body.text = s["error"]
            return
        verb = "Stopped" if s.get("cancelled") else "Finished"
        self.headline.text = verb
        self.body.text = (
            f"{s.get('passed', 0)} passed · {s.get('closest', 0)} closest · {s.get('failed', 0)} failed\n"
            f"{s.get('elapsed', 0)}s elapsed\n\n"
            f"Output folder:\n{s.get('out_dir', '')}"
        )

    def again(self, *_):
        app = App.get_running_app()
        app.selected_paths = []
        self.manager.transition = SlideTransition(direction="right", duration=0.22)
        self.manager.current = "home"


class OnlyImgApp(App):
    selected_paths: list
    config_values: dict
    last_summary: dict | None

    def build(self):
        self.title = "OnlyImgCompressorYouNeed"
        self.selected_paths = []
        self.config_values = {}
        self.last_summary = None
        self._ensure_android_permissions()

        sm = ScreenManager(transition=SlideTransition(duration=0.22))
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(ConfigScreen(name="config"))
        sm.add_widget(ProcessScreen(name="process"))
        sm.add_widget(DoneScreen(name="done"))
        return sm

    def _ensure_android_permissions(self):
        if platform != "android":
            return
        try:
            from android.permissions import Permission, request_permissions  # type: ignore

            request_permissions(
                [
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_MEDIA_IMAGES,
                ]
            )
        except Exception:
            traceback.print_exc()


if __name__ == "__main__":
    OnlyImgApp().run()
