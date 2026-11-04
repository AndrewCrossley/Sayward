from types import SimpleNamespace
from threading import Event
import pytest
from dictation.core import Config
from dictation.session import Session


@pytest.fixture
def app():
    changes=[];pastes=[];done=Event()
    desktop=SimpleNamespace(focus=lambda:42,paste=lambda *args:pastes.append(args),close=lambda:None)
    instance=Session(Config(),desktop,lambda callback,*args:callback(*args))
    instance.changes=changes;instance.pastes=pastes;instance.done=done
    instance.refresh_history=lambda:None
    instance.cue=lambda _:None
    def state(value,message):
        instance.state=value;changes.append((value,message))
        if value in ('idle','error'):done.set()
    instance.set_state=state
    instance.punctuator=SimpleNamespace(restore=lambda raw:raw[0].upper()+raw[1:]+'.',close=lambda:None)
    yield instance
    instance.shutdown()
    instance.executor.shutdown(wait=True)


def finish(app,text='hello world',target=17):
    app.target=target;app.state='working';app.done.clear()
    app.finished((text,'cpu'),None)
    assert app.done.wait(3)


def test_shared_pipeline_commits_one_validated_result_and_forward_separator(app):
    finish(app)
    assert app.history.items==['Hello world.'] and app.pending is None
    assert app.pastes==[('Hello world. ',17)]
    app.paste_last()
    assert app.pastes[-1]==('Hello world. ',42)
    assert app.history.text=='Hello world.'


def test_punctuation_failure_keeps_raw_and_selected_history_then_retry_needs_no_audio(app):
    app.history.add('Earlier result.');app.history.add('Selected result.');app.history.select(1)
    def fail(_):raise RuntimeError('Weights unavailable')
    app.punctuator.restore=fail
    finish(app,'keep these exact words')
    assert app.pending==('keep these exact words','cpu')
    assert app.history.text=='Earlier result.' and app.pastes==[]
    # Forward retains its existing meaning: selected, already completed history.
    app.paste_last()
    assert app.pastes==[('Earlier result. ',42)]
    app.punctuator.restore=lambda raw:'Keep these exact words.'
    app.engine.transcribe=lambda *_:pytest.fail('Retry must not repeat speech recognition')
    app.done.clear();app.retry_punctuation()
    assert app.done.wait(3)
    assert app.pending is None and app.history.text=='Keep these exact words.'
    assert app.pastes==[('Earlier result. ',42)]
    app.paste_last()
    assert app.pastes[-1]==('Keep these exact words. ',42)


def test_word_changing_result_is_rejected_before_history_clipboard_or_insertion(app):
    app.punctuator.restore=lambda _: 'Different words.'
    finish(app,'keep my words')
    assert app.pending==('keep my words','cpu')
    assert not app.history.items and not app.pastes and app.state=='error'


def test_missing_original_target_is_not_replaced_with_later_focus(app):
    calls=[]
    app.desktop.focus=lambda:pytest.fail('Original automatic target must not be recaptured')
    app.desktop.paste=lambda *args:calls.append(args)
    finish(app,target=None)
    assert calls==[('Hello world. ',None)]


def test_back_retries_pending_words_without_starting_a_new_capture(app):
    app.pending=('hello world','cpu');app.state='error'
    app.recorder.start=lambda:pytest.fail('Saved dictation must not be overwritten')
    app.toggle()
    assert app.done.wait(3)
    assert app.pending is None and app.pastes==[('Hello world. ',42)]


def test_download_completion_preserves_active_recording_or_processing(app):
    for state in ('recording','working'):
        app.state=state;app.changes.clear()
        app.punctuation_downloaded(None)
        assert app.state==state and app.changes==[]


def test_asr_completion_during_download_stays_recoverable_and_unlocks(app):
    app.punctuation_downloading=True
    finish(app,'saved during download')
    assert app.state=='error' and app.pending==('saved during download','cpu') and not app.pastes
    app.punctuation_downloaded(None)
    app.done.clear();app.retry_punctuation()
    assert app.done.wait(3)
    assert app.history.text=='Saved during download.' and not app.pastes


def test_discard_and_quit_clear_only_unprocessed_session_memory(app):
    app.pending=('saved words','cpu');app.state='error';app.history.add('Completed.')
    app.discard_pending()
    assert app.pending is None and app.history.text=='Completed.'
    app.pending=('other words','cpu');app.shutdown()
    assert app.pending is None and app.closed
