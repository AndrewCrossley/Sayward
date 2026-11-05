import types
import pytest
pytest.importorskip('gi')
pytest.importorskip('Xlib')
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from dictation.desktop import Desktop, xtest, X


def test_focus_change_during_clipboard_preparation_sends_no_keys(monkeypatch):
    desktop = Desktop.__new__(Desktop)
    focus = [10]
    desktop.focus = lambda: focus[0]
    desktop.root = types.SimpleNamespace(query_pointer=lambda: types.SimpleNamespace(mask=0))
    desktop.display = types.SimpleNamespace(keysym_to_keycode=lambda _: 12)
    class Clipboard:
        def set_text(self, *_):
            focus[0] = 20
        def store(self):
            pass
    monkeypatch.setattr(Gtk.Clipboard, 'get', lambda _: Clipboard())
    events = []
    monkeypatch.setattr(xtest, 'fake_input', lambda *args: events.append(args))
    with pytest.raises(RuntimeError, match='Focus changed'):
        desktop.paste('words', 10)
    assert not events


def test_both_thumb_buttons_are_consumed_and_unbound_on_close():
    desktop = Desktop.__new__(Desktop)
    desktop.buttons = (8, 9)
    events = [types.SimpleNamespace(type=X.ButtonPress, detail=8),
              types.SimpleNamespace(type=X.ButtonRelease, detail=8),
              types.SimpleNamespace(type=X.ButtonPress, detail=9),
              types.SimpleNamespace(type=X.ButtonPress, detail=1)]
    removed = []
    desktop.display = types.SimpleNamespace(pending_events=lambda: len(events), next_event=lambda: events.pop(0), sync=lambda: None, close=lambda: None)
    desktop.root = types.SimpleNamespace(ungrab_button=lambda button, _: removed.append(button))
    assert desktop.events() == [8, 9]
    desktop.close()
    assert removed == [8, 9]


@pytest.mark.parametrize('focus,mask',[(None,0),(11,0),(10,X.ControlMask),(10,X.ShiftMask),(10,X.Mod4Mask)])
def test_enter_never_injects_into_changed_focus_or_with_modifiers(monkeypatch,focus,mask):
    desktop=Desktop.__new__(Desktop);desktop.focus=lambda:focus
    desktop.root=types.SimpleNamespace(query_pointer=lambda:types.SimpleNamespace(mask=mask))
    calls=[];monkeypatch.setattr(xtest,'fake_input',lambda *args:calls.append(args))
    with pytest.raises(RuntimeError):desktop.enter(10)
    assert calls==[]


def test_enter_is_one_return_pair_without_clipboard_or_paste_modifiers(monkeypatch):
    desktop=Desktop.__new__(Desktop);desktop.focus=lambda:10
    desktop.root=types.SimpleNamespace(query_pointer=lambda:types.SimpleNamespace(mask=0))
    desktop.display=types.SimpleNamespace(keysym_to_keycode=lambda _:36,sync=lambda:None)
    calls=[];monkeypatch.setattr(xtest,'fake_input',lambda _,event,key:calls.append((event,key)))
    desktop.enter(10)
    assert calls==[(X.KeyPress,36),(X.KeyRelease,36)]
