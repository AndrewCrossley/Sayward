"""X11 mouse grab and guarded clipboard paste; never uses shell interpolation."""
import os
import time
from Xlib import X, XK, display, error
from Xlib.ext import xtest


class Desktop:
    def __init__(self, button, paste_button=9):
        if os.environ.get("XDG_SESSION_TYPE", "x11") != "x11":
            raise RuntimeError("System Dictation currently needs an X11 desktop session.")
        self.display = display.Display()
        self.root = self.display.screen().root
        self.button = button
        self.buttons = (button, paste_button)
        errors = []
        for bound in self.buttons:
            self.root.grab_button(
                bound, X.AnyModifier, False, X.ButtonPressMask | X.ButtonReleaseMask,
                X.GrabModeAsync, X.GrabModeAsync, X.NONE, X.NONE,
                onerror=lambda err, request: errors.append(err),
            )
        self.display.sync()
        if errors:
            self.display.close()
            raise RuntimeError("This mouse button is already bound by another application.")

    def focus(self):
        focus = self.display.get_input_focus().focus
        return getattr(focus, "id", focus)

    def events(self):
        pressed = []
        while self.display.pending_events():
            ev = self.display.next_event()
            if ev.type == X.ButtonPress and ev.detail in self.buttons:
                pressed.append(ev.detail)
        return pressed

    def paste(self, text, target):
        from gi.repository import Gtk, Gdk
        if not target or target in (X.NONE, X.PointerRoot) or self.focus() != target:
            raise RuntimeError("Focus changed. Focus a text field and press Forward to paste the selected transcript.")
        if self.root.query_pointer().mask & (X.ShiftMask | X.ControlMask | X.Mod1Mask | X.Mod4Mask):
            raise RuntimeError("Release keyboard modifiers, then press Forward to paste the selected transcript.")
        selections = [Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD), Gtk.Clipboard.get(Gdk.SELECTION_PRIMARY)]
        for clipboard in selections:
            clipboard.set_text(text, -1)
            clipboard.store()
        # Shift+Insert pastes text in both normal fields and Linux terminals,
        # without using Return (which could submit a command).
        shift = self.display.keysym_to_keycode(XK.string_to_keysym("Shift_L"))
        insert = self.display.keysym_to_keycode(XK.string_to_keysym("Insert"))
        if not shift or not insert:
            raise RuntimeError("The keyboard has no Shift/Insert mapping; result is on the clipboard.")
        # Clipboard managers can take time; verify again just before input.
        if self.focus() != target:
            raise RuntimeError("Focus changed. Focus a text field and press Forward to paste the selected transcript.")
        xtest.fake_input(self.display, X.KeyPress, shift)
        xtest.fake_input(self.display, X.KeyPress, insert)
        xtest.fake_input(self.display, X.KeyRelease, insert)
        xtest.fake_input(self.display, X.KeyRelease, shift)
        self.display.sync()

    def close(self):
        for button in self.buttons:
            self.root.ungrab_button(button, X.AnyModifier)
        self.display.sync()
        self.display.close()

    def enter(self, target):
        if not target or target in (X.NONE, X.PointerRoot) or self.focus() != target:
            raise RuntimeError('Focus changed; Enter cancelled.')
        if self.root.query_pointer().mask & (X.ShiftMask | X.ControlMask | X.Mod1Mask | X.Mod4Mask):
            raise RuntimeError('Keyboard modifiers are held; Enter cancelled.')
        key = self.display.keysym_to_keycode(XK.string_to_keysym('Return'))
        if not key:
            raise RuntimeError('The keyboard has no Return mapping.')
        if self.focus() != target:
            raise RuntimeError('Focus changed; Enter cancelled.')
        xtest.fake_input(self.display, X.KeyPress, key)
        xtest.fake_input(self.display, X.KeyRelease, key)
        self.display.sync()
