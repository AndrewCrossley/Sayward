"""Gesture timing and failure isolation, without a microphone or desktop."""
from types import SimpleNamespace
import pytest
from dictation.core import Config
from dictation.session import Session


@pytest.fixture
def app(monkeypatch):
    clock=[100.0];events=[];actions=[];jobs=[]
    monkeypatch.setattr('dictation.session.time.monotonic',lambda:clock[0])
    desktop=SimpleNamespace(events=lambda: list(events),focus=lambda:42,
        paste=lambda text,target:actions.append(('paste',text,target)),
        enter=lambda target:actions.append(('enter',target)),close=lambda:None)
    instance=Session(Config(),desktop,lambda *_:None)
    instance.clock,instance.events,instance.actions,instance.jobs=clock,events,actions,jobs
    instance.cue=lambda _:None;instance.refresh_history=lambda:None
    instance.set_state=lambda value,message:setattr(instance,'state',value)
    instance.recorder.start=lambda:actions.append(('record',))
    instance.recorder.stop=lambda:'unused-public-fixture.wav'
    instance.recorder.cancel=lambda:None
    instance.submit=lambda work,callback,audio=None:jobs.append((work,callback,audio))
    yield instance
    instance.shutdown();instance.executor.shutdown(wait=True)


def click(app,at):
    app.clock[0]=at;app.events[:]=[8];app.poll();app.events.clear()


def stop(app):
    app.state='recording';click(app,100.0)
    assert app.state=='working' and app.jobs[-1][2]=='unused-public-fixture.wav'


def result(app,text='Hello world.'):
    app.pending=('hello world','cpu');app.punctuation_auto_paste=True
    app.punctuated(text,None)


@pytest.mark.parametrize('delay',[0.01,0.10,0.299,0.30,0.749,0.75])
def test_double_stop_bypasses_start_debounce_and_enters_exactly_once(app,delay):
    stop(app);click(app,100+delay)
    assert app.submit_requested and not app.actions
    result(app)
    assert app.actions==[('paste','Hello world. ',42)]
    app.clock[0]+=0.151;app.poll();app.poll()
    assert app.actions==[('paste','Hello world. ',42),('enter',42)]
    assert app.state=='idle' and not app.submit_requested


def test_fast_completion_waits_for_second_click_instead_of_starting_new_capture(app):
    stop(app);app.clock[0]=100.04;result(app)
    assert not app.actions and app.state=='working'
    click(app,100.20)
    assert app.actions==[('paste','Hello world. ',42)] and not app.jobs[1:]
    app.clock[0]=100.36;app.poll()
    assert app.actions[-1]==('enter',42)


def test_single_stop_has_only_a_bounded_window_and_forward_never_enters(app):
    stop(app);result(app)
    app.clock[0]=100.751;app.poll()
    assert app.actions==[('paste','Hello world. ',42)] and app.state=='idle'
    app.clock[0]=101;app.paste_last();app.poll()
    assert app.actions==[('paste','Hello world. ',42)]*2


def test_late_stop_click_during_processing_does_not_submit_or_record(app):
    stop(app);click(app,100.751)
    result(app);app.clock[0]=102;app.poll()
    assert app.actions==[('paste','Hello world. ',42)]


def test_double_start_is_still_debounced(app):
    click(app,100);click(app,100.1)
    assert app.state=='recording' and app.actions==[('record',)]


@pytest.mark.parametrize('failure',['silent','asr','punctuation','word-change','paste'])
def test_failures_clear_submission_and_forward_is_only_paste(app,failure):
    app.history.add('Earlier result.');stop(app);click(app,100.1)
    if failure=='silent':app.finished(('', 'cpu'),None)
    elif failure=='asr':app.finished(None,'ASR failed')
    elif failure=='punctuation':
        app.pending=('hello world','cpu');app.punctuated(None,'Missing model')
    elif failure=='word-change':result(app,'Changed words.')
    else:
        app.desktop.paste=lambda *_:(_ for _ in ()).throw(RuntimeError('Focus changed'))
        result(app)
    app.clock[0]=102;app.poll()
    assert not app.actions and not app.submit_requested and app.enter_due is None
    app.desktop.paste=lambda text,target:app.actions.append(('paste',text,target))
    app.paste_last();app.poll()
    assert len(app.actions)==1 and app.actions[0][0]=='paste'


def test_punctuation_retry_cannot_inherit_submission(app):
    stop(app);click(app,100.1);app.pending=('hello world','cpu')
    app.punctuated(None,'Missing model');app.retry_punctuation(paste=True)
    app.punctuated('Hello world.',None)
    app.clock[0]=102;app.poll()
    assert app.actions==[('paste','Hello world. ',42)]


def test_enter_focus_failure_keeps_completed_history_and_never_retries_enter(app):
    stop(app);click(app,100.1);result(app)
    app.desktop.enter=lambda _:(_ for _ in ()).throw(RuntimeError('Focus changed'))
    app.clock[0]=101;app.poll();app.poll()
    assert app.state=='error' and app.history.text=='Hello world.'
    assert app.actions==[('paste','Hello world. ',42)] and app.enter_due is None


def test_auto_stop_and_quit_do_not_send_enter(app):
    app.state='recording';app.started=0;app.config.max_record_seconds=10
    app.tick();click(app,100.1);result(app)
    assert app.actions==[('paste','Hello world. ',42)]
    app.actions.clear();app.clear_submission();app.state='recording'
    app.clock[0]=101;app.toggle();click(app,101.2);result(app);app.shutdown()
    app.clock[0]=103;assert not app.poll()
    assert app.actions==[('paste','Hello world. ',42)]


def test_enter_delay_starts_after_clipboard_preparation_returns(app):
    stop(app);click(app,100.1)
    def paste(text,target):app.clock[0]+=1;app.actions.append(('paste',text,target))
    app.desktop.paste=paste;result(app)
    app.poll();assert len(app.actions)==1
    app.clock[0]+=0.151;app.poll();assert app.actions[-1]==('enter',42)
