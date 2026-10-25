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
gi.require_version("GdkX11", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, GLib, GdkX11, AyatanaAppIndicator3
from .core import Config, Engine, Recorder, TranscriptHistory
from .desktop import Desktop
from .session import Session


class App(Session):
    def __init__(self, config):
        runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/tmp/dictation-{os.getuid()}"))
        runtime.mkdir(mode=0o700, exist_ok=True)
        self.lock = open(runtime / "system-dictation.lock", "a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Sayward is already running.")
        super().__init__(config, Desktop(config.button, config.paste_button), GLib.idle_add)
        self.practice_window = None
        self.history_window = None
        self.history_refreshing = False
        self.meter_level, self.meter_frame = 0.0, None
        self.recording_message = ""
        self.meter_message = None
        self.indicator = AyatanaAppIndicator3.Indicator.new(
            "system-dictation", self.icon("idle"), AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        self.menu = Gtk.Menu()
        self.status_item = self.item("Ready — Back thumb button to record", sensitive=False)
        self.toggle_item = self.item("Start recording", lambda _: self.toggle())
        self.cancel_item = self.item("Cancel recording", lambda _: self.cancel())
        self.paste_item = self.item("Paste selected transcript (Forward)", lambda _: GLib.timeout_add(300, self.paste_last))
        self.item("Recent transcripts (last 5)", lambda _: self.open_history())
        self.item("Copy selected transcript", lambda _: self.copy_last())
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
        GLib.timeout_add(100, self.meter)
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
        if state == "recording":
            self.recording_message = message
            self.meter_frame = None
            self.meter_message = None
        self.status_item.set_label(message)
        self.indicator.set_icon_full(self.icon(state), message)
        self.indicator.set_title("Sayward — " + message)
        self.toggle_item.set_label("Stop and transcribe" if state == "recording" else "Start recording")
        self.toggle_item.set_sensitive(state != "working")
        self.cancel_item.set_sensitive(state == "recording")
        self.paste_item.set_sensitive(bool(self.history.text) and state not in ("recording", "working"))
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


    def meter(self):
        if self.closed:
            return False
        if self.state != "recording":
            self.meter_level, self.meter_frame = 0.0, None
            return True
        now = time.monotonic()
        raw = self.recorder.level if now - self.recorder.level_updated_at < 0.4 else 0.0
        self.meter_level = max(raw, self.meter_level * 0.72)
        frame = min(11, round(self.meter_level * 11))
        quiet = now - self.recorder.last_signal >= 2
        message = "Recording — no mic input; check mute" if quiet else self.recording_message
        # Update GTK only here, never from PortAudio's real-time callback.
        if frame != self.meter_frame:
            path = Path(__file__).parent.parent / "icons" / f"recording-{frame}.svg"
            self.indicator.set_icon_full(str(path), message)
            self.meter_frame = frame
        if message != self.meter_message:
            self.status_item.set_label(message)
            self.indicator.set_title("Sayward — " + message)
            if self.practice_window:
                self.practice_status.set_text(message)
            self.meter_message = message
        return True







    def copy_last(self):
        from gi.repository import Gdk
        if self.history.text:
            cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            cb.set_text(self.history.text, -1)
            cb.store()
            self.set_state(self.state, "Selected transcript copied to clipboard")

    def open_history(self):
        if self.history_window:
            stamp = GdkX11.x11_get_server_time(self.history_window.get_window())
            self.history_window.present_with_time(stamp)
            return
        window = Gtk.Window(title="Sayward — Recent transcripts")
        window.set_default_size(640, 480)
        # Measure wrapped labels at a usable width before GTK chooses the height.
        window.set_size_request(640, -1)
        window.set_position(Gtk.WindowPosition.CENTER)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=16)
        window.add(box)
        guide = Gtk.Label(label="Select a transcript, return to your text field, then press the front thumb / Forward button to paste.\nThe newest result is selected automatically. History lasts for this session only.")
        guide.set_line_wrap(True)
        guide.set_max_width_chars(76)
        guide.set_xalign(0)
        box.pack_start(guide, False, False, 0)
        self.history_empty = Gtk.Label(label="No transcripts yet. Record speech with the Back thumb button.")
        box.pack_start(self.history_empty, False, False, 0)
        self.history_list = Gtk.ListBox()
        self.history_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.history_list.connect("row-selected", self.select_history)
        box.pack_start(self.history_list, False, False, 0)
        self.history_preview = Gtk.TextView(editable=False, cursor_visible=False)
        self.history_preview.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.history_preview.get_accessible().set_name("Selected transcript preview")
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.set_min_content_height(96)
        scroll.set_max_content_height(220)
        scroll.set_propagate_natural_height(True)
        scroll.add(self.history_preview)
        box.pack_start(scroll, True, True, 0)
        close = Gtk.Button(label="Close history")
        close.connect("clicked", lambda _: window.destroy())
        box.pack_start(close, False, False, 0)
        window.connect("destroy", lambda _: setattr(self, "history_window", None))
        self.history_window = window
        self.refresh_history()
        window.show_all()
        self.history_empty.set_visible(not self.history.items)
        stamp = GdkX11.x11_get_server_time(window.get_window())
        window.present_with_time(stamp)

    def refresh_history(self):
        if not self.history_window:
            return
        self.history_refreshing = True
        try:
            for row in self.history_list.get_children():
                self.history_list.remove(row)
            for index, text in enumerate(self.history.items):
                summary = " ".join(text.split())
                if len(summary) > 86:
                    summary = summary[:83] + "…"
                label = Gtk.Label(label=f"{index + 1}. {summary}", xalign=0, margin=8)
                label.set_line_wrap(True)
                self.history_list.add(label)
            self.history_list.show_all()
            if self.history.items:
                self.history_list.select_row(self.history_list.get_row_at_index(self.history.selected))
            self.history_preview.get_buffer().set_text(self.history.text)
            self.history_empty.set_visible(not self.history.items)
        finally:
            self.history_refreshing = False

    def select_history(self, widget, row):
        if row is None or self.history_refreshing:
            return
        self.history.select(row.get_index())
        self.history_preview.get_buffer().set_text(self.history.text)
        self.paste_item.set_sensitive(self.state not in ("recording", "working"))




    def help(self):
        if self.practice_window:
            stamp = GdkX11.x11_get_server_time(self.practice_window.get_window())
            self.practice_window.present_with_time(stamp)
            return
        window = Gtk.Window(title="Sayward — How to use / Practice")
        window.set_default_size(600, 380)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin=20)
        window.add(box)
        label = Gtk.Label(label=(
            "1. Put your cursor in any text field.\n"
            "2. Click the Back thumb button once, then speak. The red mic glows with your input level.\n"
            "3. Click it again. The amber icon means transcribing; keep the field focused.\n"
            "4. Your words are pasted at the cursor. GPU is preferred; CPU is automatic.\n\n"
            "Try it in the box below. Start/Stop does the same thing as the mouse button.\n"
            "To paste again, focus the field and press the front thumb / Forward button.\n"
            "Choose older results through Recent transcripts in the tray (last five, this session).\n"
            "A dim icon and No mic input message mean check your microphone or mute switch.\n"
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
        # Tray actions arrive over D-Bus without a GTK mouse-event timestamp.
        # Supply fresh X11 time so Cinnamon accepts this user-requested focus.
        stamp = GdkX11.x11_get_server_time(window.get_window())
        window.present_with_time(stamp)
        entry.grab_focus()

    def quit(self):
        if self.closed:
            return False
        self.shutdown()
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.PASSIVE)
        Gtk.main_quit()
        return False


def main():
    config_path = Path(os.environ.get("DICTATION_CONFIG", Path.home() / ".config/system-dictation/config.json"))
    app = App(Config.load(config_path))
    Gtk.main()


if __name__ == "__main__":
    main()
