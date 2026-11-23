"""Optional issue recording: CLI contract, Back chooser and Back-then-Forward, without a display."""
import json
import os
import threading
from types import SimpleNamespace
import pytest
from dictation.core import Config
from dictation.issue import IssueRecorder, find_recorder
from dictation.session import CHOOSER_DOWN_PX, CHOOSER_SECONDS, CHOOSER_UP_PX, Session

FAKE_CLI = r'''#!/usr/bin/env bash
set -eu
root="$RECORD_ISSUE_ROOT"
case "$1" in
  start)
    [ ! -f "$root/.active" ] || { echo "record-issue: already recording: $(cat "$root/.active")" >&2; exit 1; }
    d="$root/20261122-120000"; mkdir -p "$d"
    echo '{"version": 1, "epoch": 1795400000.5, "max_s": 1800}' > "$d/session.json"
    echo "$d" > "$root/.active"; echo "recording -> $d" ;;
  stop)
    [ -f "$root/.active" ] || { echo "record-issue: not recording" >&2; exit 1; }
    d=$(cat "$root/.active"); rm "$root/.active"; echo "bundle: $d"; echo "next: process $d" ;;
esac
'''


@pytest.fixture
def cli(tmp_path, monkeypatch):
    script = tmp_path / "record-issue"
    script.write_text(FAKE_CLI)
    script.chmod(0o700)
    root = tmp_path / "sessions"
    root.mkdir()
    monkeypatch.setenv("RECORD_ISSUE_ROOT", str(root))
    return script, root


def test_recorder_is_found_only_from_config_or_path_and_only_on_linux(cli, tmp_path, monkeypatch):
    script, _ = cli
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr("dictation.issue.sys.platform", "linux")
    assert find_recorder(Config()) == str(script)
    assert find_recorder(Config(issue_recorder=str(script))) == str(script)
    assert find_recorder(Config(issue_recorder=str(tmp_path / "missing"))) is None
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert find_recorder(Config()) is None
    monkeypatch.setattr("dictation.issue.sys.platform", "win32")
    assert find_recorder(Config(issue_recorder=str(script))) is None


def test_cli_contract_start_live_stop(cli):
    script, root = cli
    issue = IssueRecorder(str(script))
    assert issue.root == root and issue.live() is None
    bundle, epoch, max_s = issue.start()
    assert bundle == str(root / "20261122-120000") and epoch == 1795400000.5 and max_s == 1800
    with pytest.raises(RuntimeError, match="already recording"):
        issue.start()
    assert issue.stop() == bundle and issue.last_bundle == bundle and issue.live() is None
    with pytest.raises(RuntimeError, match="not recording"):
        issue.stop()


def test_live_survives_a_missing_or_corrupt_session_file(cli):
    script, root = cli
    (root / ".active").write_text(str(root / "gone") + "\n")
    assert IssueRecorder(str(script)).live() == (str(root / "gone"), None, 0)


def test_config_update_keeps_other_keys(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"model": "small", "button": 8}))
    Config.update_file(path, back_chooser=False)
    assert json.loads(path.read_text()) == {"model": "small", "button": 8, "back_chooser": False}
    assert Config.load(path).back_chooser is False
    assert [p.name for p in tmp_path.iterdir()] == ["config.json"]


class FakeIssue:
    def __init__(self):
        self.live_value, self.calls, self.last_bundle = None, [], None

    def live(self):
        return self.live_value


@pytest.fixture
def app(monkeypatch):
    clock = [100.0]; events = []; actions = []; pointer = [500, 400]
    monkeypatch.setattr("dictation.session.time.monotonic", lambda: clock[0])
    def consume():
        batch = events[:]; events.clear(); return batch
    desktop = SimpleNamespace(events=consume, focus=lambda: 42, pointer=lambda: tuple(pointer),
                              paste=lambda text, target: actions.append(("paste", text, target)),
                              enter=lambda target: actions.append(("enter", target)), close=lambda: None)
    instance = Session(Config(), desktop, lambda callback, *args: callback(*args))
    instance.clock, instance.events, instance.actions, instance.pointer = clock, events, actions, pointer
    instance.cue = lambda _: None; instance.refresh_history = lambda: None
    instance.set_state = lambda value, message: (setattr(instance, "state", value), setattr(instance, "message", message))
    instance.recorder.start = lambda: actions.append(("record",))
    instance.recorder.stop = lambda: "unused-public-fixture.wav"
    instance.recorder.cancel = lambda: actions.append(("cancel",))
    instance.submit = lambda work, callback, audio=None: None
    instance.show_chooser = lambda x, y, live: actions.append(("chooser", x, y, live))
    instance.hide_chooser = lambda: actions.append(("hide",))
    instance.issue_toggle = lambda: actions.append(("issue",))
    instance.issue = FakeIssue()
    yield instance
    instance.shutdown(); instance.executor.shutdown(wait=True)


def press(app, button, at):
    app.clock[0] = at; app.events[:] = [(button, at)]; app.poll(); app.events.clear()


def test_back_starts_dictation_at_once_and_opens_chooser_at_pointer(app):
    press(app, 8, 100.0)
    assert app.state == "recording" and app.actions == [("record",), ("chooser", 500, 400, False)]


def test_moving_down_switches_the_capture_to_issue_recording(app):
    press(app, 8, 100.0)
    app.pointer[1] += CHOOSER_DOWN_PX - 1; app.clock[0] = 100.5; app.poll()
    assert app.state == "recording" and ("issue",) not in app.actions
    app.pointer[1] += 1; app.poll()
    assert app.actions[-3:] == [("hide",), ("cancel",), ("issue",)]
    assert app.state == "idle" and app.chooser is None


@pytest.mark.parametrize("move,wait", [(-CHOOSER_UP_PX, 0.1), (0, CHOOSER_SECONDS)])
def test_moving_up_or_waiting_keeps_plain_dictation(app, move, wait):
    press(app, 8, 100.0)
    app.pointer[1] += move; app.clock[0] = 100 + wait; app.poll()
    app.pointer[1] += 500; app.poll()
    assert app.state == "recording" and app.chooser is None
    assert ("issue",) not in app.actions and ("cancel",) not in app.actions and app.actions[-1] == ("hide",)


def test_stopping_dictation_closes_the_chooser(app):
    press(app, 8, 100.0); press(app, 8, 100.4)
    assert app.state == "working" and app.chooser is None and ("hide",) in app.actions


def test_back_then_forward_during_capture_toggles_issue_recording(app):
    press(app, 8, 100.0); press(app, 9, 100.3)
    assert app.actions[-2:] == [("cancel",), ("issue",)] and app.state == "idle"


def test_chooser_can_be_switched_off_but_the_chord_remains(app):
    app.config.back_chooser = False
    press(app, 8, 100.0)
    assert app.actions == [("record",)]
    press(app, 9, 100.3)
    assert app.actions[-1] == ("issue",)


def test_without_the_recorder_back_and_forward_are_unchanged(app):
    app.issue = None
    press(app, 8, 100.0); press(app, 9, 100.3); press(app, 9, 101.0)
    assert app.actions == [("record",)] and app.state == "recording"


def test_forward_while_idle_still_pastes_history(app):
    app.history.add("Hello world.")
    press(app, 9, 100.0)
    assert app.actions == [("paste", "Hello world. ", 42)]


def test_double_stop_submission_is_unaffected_by_issue_recording(app):
    app.issue.live_value = ("bundle", 1.0, 1800); app.issue_live = app.issue.live_value
    press(app, 8, 100.0); press(app, 8, 101.0); press(app, 8, 101.2)
    assert app.submit_requested and ("issue",) not in app.actions


def test_issue_toggle_runs_off_the_ui_thread_and_reports(app, cli):
    script, root = cli
    del app.issue_toggle  # use the real implementation
    app.issue = IssueRecorder(str(script))
    changed, done = [], threading.Event()
    app.issue_changed = lambda: changed.append((bool(app.issue_live), app.issue_busy))
    original = app.issue_done
    app.issue_done = lambda *args: (original(*args), done.set())
    app.state = "idle"
    app.issue_toggle()
    assert done.wait(10)
    assert app.issue_live and not app.issue_busy and changed[0] == (False, True) and changed[-1] == (True, False)
    assert app.state == "idle" and "Issue recording" in app.message
    done.clear(); app.issue_toggle()
    assert done.wait(10)
    assert app.issue_live is None and app.issue.last_bundle and "bundle saved" in app.message
    (root / ".active").write_text("x")  # an unfinished bundle the CLI refuses to replace
    app.issue_live = None
    done.clear(); app.issue_toggle()
    assert done.wait(10)
    assert app.state == "error" and "already recording" in app.message


def test_tick_follows_recordings_started_elsewhere(app):
    changed = []
    app.issue_changed = lambda: changed.append(bool(app.issue_live))
    app.state = "idle"
    app.issue.live_value = ("bundle", 1.0, 1800); app.tick()
    app.tick()
    app.issue.live_value = None; app.tick()
    assert changed == [True, False]
