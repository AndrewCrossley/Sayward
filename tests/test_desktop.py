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


def test_both_thumb_buttons_are_consumed_and_unbound_on_close(monkeypatch):
    monkeypatch.setattr('dictation.desktop.time.monotonic',lambda:12.0)
    desktop = Desktop.__new__(Desktop)
    desktop.buttons = (8, 9)
    desktop.clock_ms,desktop.clock_at=10000,10.0
    events = [types.SimpleNamespace(type=X.ButtonPress, detail=8,time=10100),
              types.SimpleNamespace(type=X.ButtonRelease, detail=8),
              types.SimpleNamespace(type=X.ButtonPress, detail=9,time=11200),
              types.SimpleNamespace(type=X.ButtonPress, detail=1)]
    removed = []
    desktop.display = types.SimpleNamespace(pending_events=lambda: len(events), next_event=lambda: events.pop(0), sync=lambda: None, close=lambda: None)
    desktop.root = types.SimpleNamespace(ungrab_button=lambda button, _: removed.append(button))
    assert desktop.events() == [(8,10.1),(9,11.2)]
    desktop.close()
    assert removed == [8, 9]


@pytest.mark.parametrize('focus,mask',[(None,0),(11,0),(10,X.ControlMask),(10,X.ShiftMask),(10,X.Mod1Mask),(10,X.Mod3Mask),(10,X.Mod4Mask),(10,X.Mod5Mask)])
def test_enter_never_injects_into_changed_focus_or_with_modifiers(monkeypatch,focus,mask):
    desktop=Desktop.__new__(Desktop);desktop.focus=lambda:focus
    desktop.root=types.SimpleNamespace(query_pointer=lambda:types.SimpleNamespace(mask=mask))
    calls=[];monkeypatch.setattr(xtest,'fake_input',lambda *args:calls.append(args))
    with pytest.raises(RuntimeError):desktop.enter(10)
    assert calls==[]


def test_enter_is_one_return_pair_without_clipboard_or_paste_modifiers(monkeypatch):
    desktop=Desktop.__new__(Desktop);desktop.focus=lambda:10
    desktop.root=types.SimpleNamespace(query_pointer=lambda:types.SimpleNamespace(mask=X.LockMask | X.Mod2Mask))
    desktop.display=types.SimpleNamespace(keysym_to_keycode=lambda _:36,sync=lambda:None)
    calls=[];monkeypatch.setattr(xtest,'fake_input',lambda _,event,key:calls.append((event,key)))
    desktop.enter(10)
    assert calls==[(X.KeyPress,36),(X.KeyRelease,36)]


def test_x11_timestamp_wrap_preserves_queued_click_ages(monkeypatch):
    desktop=Desktop.__new__(Desktop);desktop.buttons=(8,9)
    desktop.clock_ms,desktop.clock_at=0xfffffff0,100.0
    monkeypatch.setattr('dictation.desktop.time.monotonic',lambda:102.0)
    pending=[types.SimpleNamespace(type=X.ButtonPress,detail=8,time=0xfffffff0),
             types.SimpleNamespace(type=X.ButtonPress,detail=8,time=0x0000043c)]
    desktop.display=types.SimpleNamespace(pending_events=lambda:len(pending),next_event=lambda:pending.pop(0))
    assert desktop.events()==[(8,100.0),(8,101.1)]


@pytest.mark.parametrize('mask',[X.Mod3Mask,X.Mod5Mask])
def test_paste_with_altgr_or_other_nonlock_modifier_never_changes_clipboard(monkeypatch,mask):
    desktop=Desktop.__new__(Desktop);desktop.focus=lambda:10
    desktop.root=types.SimpleNamespace(query_pointer=lambda:types.SimpleNamespace(mask=mask))
    monkeypatch.setattr(Gtk.Clipboard,'get',lambda *_:pytest.fail('Modifier guard must run before copying'))
    calls=[];monkeypatch.setattr(xtest,'fake_input',lambda *args:calls.append(args))
    with pytest.raises(RuntimeError,match='modifiers'):desktop.paste('Public words.',10)
    assert calls==[]
