import pytest
from dictation.session import Session as App
from dictation.core import TranscriptHistory, Config
from types import SimpleNamespace


@pytest.mark.parametrize('state', ['recording', 'working'])
def test_late_idle_unload_does_not_reset_active_operation(state):
    app = App.__new__(App)
    app.state = state
    changes = []
    app.set_state = lambda *args: changes.append(args)
    app.unloaded()
    assert app.state == state
    assert not changes


def test_failed_auto_paste_still_keeps_new_result_and_forward_uses_selected_text():
    app = App.__new__(App)
    app.config = Config()
    app.history = TranscriptHistory()
    app.history.add('Older words')
    app.target = 1
    app.state = 'working'
    app.refresh_history = lambda: None
    app.cue = lambda _: None
    def status(state, _):
        app.state = state
    app.set_state = status
    def reject(*_):
        raise RuntimeError('Focus changed')
    app.desktop = SimpleNamespace(paste=reject)
    app.pending = ('Latest words', 'cpu')
    app.punctuation_auto_paste = True
    app.closed = False
    app.clear_submission()
    app.punctuated('Latest words.', None)
    assert app.history.items == ['Latest words.', 'Older words']
    app.history.select(1)
    calls = []
    app.desktop = SimpleNamespace(focus=lambda: 42, paste=lambda *args: calls.append(args))
    app.paste_last()
    assert calls == [('Older words ', 42)]


def test_empty_or_failed_transcription_does_not_erase_selected_history():
    app = App.__new__(App)
    app.config = Config()
    app.history = TranscriptHistory()
    app.history.add('Keep this')
    app.set_state = lambda *_: None
    app.cue = lambda _: None
    app.finished(('', 'cpu'), None)
    app.finished(None, 'model failure')
    assert app.history.text == 'Keep this'


def test_button_events_dispatch_separately_without_starting_recording_on_forward(monkeypatch):
    app = App.__new__(App)
    app.closed = False
    app.config = Config()
    app.last_press = {}
    app.clear_submission()
    app.desktop = SimpleNamespace(events=lambda: [8, 9, 9])
    calls = []
    app.toggle = lambda: calls.append('record')
    app.paste_last = lambda: calls.append('paste')
    assert app.poll()
    assert calls == ['record', 'paste']


def test_silent_meter_warns_and_live_input_restores_recording_status(monkeypatch):
    pytest.importorskip('gi')
    pytest.importorskip('Xlib')
    from dictation.app import App
    from dictation import app as app_module
    monkeypatch.setattr(app_module.time, 'monotonic', lambda: 100)
    app = App.__new__(App)
    app.closed = False
    app.state = 'recording'
    app.recorder = SimpleNamespace(level=0, level_updated_at=100, last_signal=90)
    app.meter_level, app.meter_frame, app.meter_message = 0, None, None
    app.recording_message = 'Recording — CPU model ready'
    app.practice_window = None
    messages, icons = [], []
    app.status_item = SimpleNamespace(set_label=messages.append)
    app.indicator = SimpleNamespace(set_icon_full=lambda path, message: icons.append(path), set_title=lambda _: None)
    assert app.meter()
    assert 'check mute' in messages[-1] and icons[-1].endswith('recording-0.svg')
    app.recorder.level, app.recorder.last_signal = 0.8, 100
    app.meter()
    assert messages[-1] == 'Recording — CPU model ready'
    assert not icons[-1].endswith('recording-0.svg')
    app.state = 'idle'
    count = len(icons)
    app.meter()
    assert app.meter_level == 0 and len(icons) == count
