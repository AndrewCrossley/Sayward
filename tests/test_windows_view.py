import queue
import sys
from types import SimpleNamespace
import pytest

pytestmark=pytest.mark.skipif(sys.platform!='win32',reason='Windows view; no actual UI is created')


def test_callback_failure_keeps_dispatch_alive_and_quit_reachable():
    from dictation.windows_app import WindowsApp
    app=WindowsApp.__new__(WindowsApp)
    app.closed=False;app.state='idle';app.callbacks=queue.Queue()
    timers=[];errors=[]
    app.root=SimpleNamespace(after=lambda *args:timers.append(args))
    app.set_state=lambda state,message:errors.append((state,message))
    app.poll=lambda:None
    def fail():raise OSError('Configuration is read-only')
    app.callbacks.put((fail,()))
    app.pump()
    assert len(timers)==1 and errors[0][0]=='error'
    app.callbacks.put((lambda:setattr(app,'closed',True),()))
    app.pump()
    assert app.closed and len(timers)==1


@pytest.mark.parametrize('state',['recording','working'])
def test_settings_error_preserves_active_capture_or_transcription(state):
    from dictation.windows_app import WindowsApp
    app=WindowsApp.__new__(WindowsApp)
    app.closed=False;app.state=state
    changes=[];app.set_state=lambda *args:changes.append(args)
    app.report_error(OSError('disk full'))
    assert changes[0][0]==state


def test_failed_completion_unlocks_controls_for_recovery():
    from dictation.windows_app import WindowsApp
    app=WindowsApp.__new__(WindowsApp)
    app.closed=False;app.state='working'
    changes=[];app.set_state=lambda *args:changes.append(args)
    app.report_error(OSError('view failure'),completed=True)
    assert changes[0][0]=='error'
