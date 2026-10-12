"""Tray-only dictation app. Heavy work never runs in the GTK event loop."""
import concurrent.futures
import fcntl
import os
from pathlib import Path
import signal
import subprocess
import time
import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, GLib, AyatanaAppIndicator3
from .core import Config, Engine, Recorder
from .desktop import Desktop


class App:
    def __init__(self, config):
        runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/dictation-{os.getuid()}"))
        runtime.mkdir(mode=0o700, exist_ok=True)
        self.lock = open(runtime / "system-dictation.lock", "a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("System Dictation is already running.")
        self.config = config
        self.desktop = Desktop(config.button)
        self.recorder = Recorder(config)
        self.engine = Engine(config)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.state, self.started = "idle", 0
        self.last_result, self.target = "", None
        self.closed = False
        self.idle_deadline = 0
        self.last_press = 0
        self.practice_window = None
        self.indicator = AyatanaAppIndicator3.Indicator.new(
            "system-dictation", self.icon("idle"), AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        self.menu = Gtk.Menu()
        self.status_item = self.item("Ready — Back thumb button to record", sensitive=False)
        self.toggle_item = self.item("Start recording", lambda _: self.toggle())
        self.cancel_item = self.item("Cancel recording", lambda _: self.cancel())
        self.paste_item = self.item("Paste last result", lambda _: GLib.timeout_add(300, self.paste_last))
        self.item("Copy last result", lambda _: self.copy_last())
        self.item("How to use / Practice", lambda _: self.help())
        sounds = Gtk.CheckMenuItem(label="Sound cues")
        sounds.set_active(config.sound)
        sounds.connect("toggled", lambda item: setattr(self.config, "sound", item.get_active()))
        self.menu.append(sounds)
        self.item("Unload model now", lambda _: self.unload())
        self.item("Quit", lambda _: self.quit())
        self.menu.show_all()
        self.indicator.set_menu(self.menu)
        self.set_state("idle", "Ready — Back thumb button to record")
        GLib.timeout_add(20, self.poll)
        GLib.timeout_add_seconds(1, self.tick)
        for sig in (signal.SIGTERM, signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, self.quit)

    def icon(self, state):
        return str(Path(__file__).parent.parent / "icons" / f"{state}.svg")

    def item(self, label, callback=None, sensitive=True):
        item = Gtk.MenuItem(label=label)
        item.set_sensitive(sensitive)
        if callback:
            item.connect("activate", callback)
        self.menu.append(item)
        return item

    def set_state(self, state, message):
        if self.closed:
            return False
        self.state = state
        self.status_item.set_label(message)
        self.indicator.set_icon_full(self.icon(state), message)
        self.indicator.set_title("System Dictation — " + message)
        self.toggle_item.set_label("Stop and transcribe" if state == "recording" else "Start recording")
        self.toggle_item.set_sensitive(state != "working")
        self.cancel_item.set_sensitive(state == "recording")
        self.paste_item.set_sensitive(bool(self.last_result) and state not in ("recording", "working"))
        if self.practice_window:
            self.practice_status.set_text(message)
            self.practice_toggle.set_label(self.toggle_item.get_label())
            self.practice_toggle.set_sensitive(state != "working")
        return False

    def cue(self, event):
        if not self.config.sound:
            return
        sound = Path(__file__).parent.parent / "sounds" / f"{event}.wav"
        try:
            subprocess.Popen(["paplay", str(sound)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass

    def poll(self):
        if self.closed:
            return False
        for _ in range(self.desktop.events()):
            now = time.monotonic()
            if now - self.last_press >= 0.3:
                self.last_press = now
                self.toggle()
        return True

    def toggle(self):
        if self.state == "working":
            return
        if self.state == "recording":
            try:
                audio = self.recorder.stop()
            except Exception as exc:
                self.set_state("error", str(exc))
                return
            self.target = self.desktop.focus()
            self.set_state("working", "Transcribing — please keep this text field focused")
            self.cue("stop")
            self.submit(lambda: self.engine.transcribe(audio), self.finished, audio)
            return
        try:
            self.recorder.start()
        except Exception:
            self.set_state("error", "Microphone unavailable — check desktop sound input and try again")
            return
        self.started = time.monotonic()
        self.idle_deadline = 0
        self.set_state("recording", "Recording — click Back thumb button again to transcribe")
        self.cue("start")
        self.submit(self.engine.prepare, self.prepared)

    def submit(self, work, callback, audio=None):
        def run():
            try:
                value, error = work(), None
            except Exception as exc:
                value, error = None, str(exc)
            finally:
                if audio:
                    Path(audio).unlink(missing_ok=True)
            if not self.closed:
                GLib.idle_add(callback, value, error)
        self.executor.submit(run)

    def prepared(self, device, error):
        if self.state == "recording":
            message = "Recording — " + ("model will retry after stop" if error else f"{device.upper()} model ready")
            self.set_state("recording", message)
        return False

    def finished(self, result, error):
        self.idle_deadline = time.monotonic() + self.config.idle_seconds
        if error:
            self.set_state("error", "Transcription failed — " + error)
            self.cue("error")
            return False
        text, device = result
        if not text:
            self.set_state("idle", f"No speech detected ({device.upper()}) — ready")
            return False
        self.last_result = text
        try:
            self.desktop.paste(text, self.target)
        except Exception as exc:
            self.set_state("error", str(exc))
            self.cue("error")
            return False
        self.set_state("idle", f"Text pasted ({device.upper()}) — ready")
        self.cue("done")
        return False

    def cancel(self):
        if self.state == "recording":
            self.recorder.cancel()
            self.idle_deadline = time.monotonic() + self.config.idle_seconds
            self.set_state("idle", "Recording cancelled — ready")

    def paste_last(self):
        if self.last_result and self.state not in ("recording", "working"):
            try:
                self.desktop.paste(self.last_result, self.desktop.focus())
                self.set_state("idle", "Last result pasted — ready")
            except Exception as exc:
                self.set_state("error", str(exc))
        return False

    def copy_last(self):
        from gi.repository import Gdk
        if self.last_result:
            cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            cb.set_text(self.last_result, -1)
            cb.store()
            self.set_state(self.state, "Last result copied to clipboard")

    def unload(self):
        if self.state in ("recording", "working"):
            return
        self.idle_deadline = 0
        self.submit(self.engine.close, lambda *_: self.set_state("idle", "Model unloaded — ready"))

    def tick(self):
        if self.closed:
            return False
        now = time.monotonic()
        if self.state == "recording" and now - self.started >= self.config.max_record_seconds:
            self.toggle()
        elif self.state not in ("recording", "working") and self.idle_deadline and now >= self.idle_deadline:
            self.unload()
        return True

    def help(self):
        if self.practice_window:
            self.practice_window.present()
            return
        window = Gtk.Window(title="System Dictation — How to use / Practice")
        window.set_default_size(600, 380)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin=20)
        window.add(box)
        label = Gtk.Label(label=(
            "1. Put your cursor in any text field.\n"
            "2. Click the Back thumb button once, then speak. The red tray icon means recording.\n"
            "3. Click it again. The amber icon means transcribing; keep the field focused.\n"
            "4. Your words are pasted at the cursor. GPU is preferred; CPU is automatic.\n\n"
            "Try it in the box below. Start/Stop does the same thing as the mouse button.\n"
            "If focus changes, use Paste last result or Copy last result in the tray.\n"
            "Dictation replaces the clipboard. Audio is temporary and speech stays local."
        ))
        label.set_line_wrap(True)
        label.set_xalign(0)
        box.pack_start(label, False, False, 0)
        entry = Gtk.Entry()
        entry.set_placeholder_text("Practice here: focus this box, click Back, and speak")
        box.pack_start(entry, False, False, 0)
        self.practice_toggle = Gtk.Button(label=self.toggle_item.get_label())
        self.practice_toggle.set_can_focus(False)
        self.practice_toggle.get_style_context().add_class("suggested-action")
        self.practice_toggle.set_tooltip_text("One click starts recording; the next click stops and transcribes.")
        self.practice_toggle.connect("clicked", lambda _: self.toggle())
        box.pack_start(self.practice_toggle, False, False, 0)
        self.practice_status = Gtk.Label(label=self.status_item.get_label())
        self.practice_status.set_line_wrap(True)
        box.pack_start(self.practice_status, False, False, 0)
        close = Gtk.Button(label="Close guide")
        close.connect("clicked", lambda _: window.destroy())
        box.pack_start(close, False, False, 0)
        window.connect("destroy", lambda _: setattr(self, "practice_window", None))
        self.practice_window = window
        window.show_all()
        entry.grab_focus()

    def quit(self):
        if self.closed:
            return False
        self.closed = True
        self.recorder.cancel()
        self.engine.stopping = True
        if self.engine.process:
            self.engine.process.terminate()
        self.executor.submit(self.engine.close)
        self.executor.shutdown(wait=False)
        self.desktop.close()
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.PASSIVE)
        Gtk.main_quit()
        return False


def main():
    config_path = Path(os.environ.get("DICTATION_CONFIG", Path.home() / ".config/system-dictation/config.json"))
    app = App(Config.load(config_path))
    Gtk.main()


if __name__ == "__main__":
    main()
