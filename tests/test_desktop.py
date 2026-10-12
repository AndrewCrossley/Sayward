import types
import pytest
pytest.importorskip('gi')
pytest.importorskip('Xlib')
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from dictation.desktop import Desktop, xtest


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
