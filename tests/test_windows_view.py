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


def test_copy_failure_does_not_unlock_inflight_punctuation():
    from dictation.windows_app import WindowsApp
    app=WindowsApp.__new__(WindowsApp)
    app.closed=False;app.state='working'
    app.history=SimpleNamespace(text='Earlier result.')
    def busy(_):raise OSError('Clipboard is busy')
    app.desktop=SimpleNamespace(copy=busy)
    changes=[];app.set_state=lambda *args:changes.append(args)
    app.copy_last()
    assert changes[0][0]=='working'


def test_failed_settings_write_preserves_previous_config(monkeypatch,tmp_path):
    from dictation import windows_app
    from dictation.core import Config
    path=tmp_path/'config.json';previous='{"model":"medium"}\n';path.write_text(previous)
    monkeypatch.setattr(windows_app,'config_path',lambda:path)
    def disk_full(value,stream,**kwargs):
        stream.write('{')
        raise OSError('disk full')
    monkeypatch.setattr(windows_app.json,'dump',disk_full)
    app=windows_app.WindowsApp.__new__(windows_app.WindowsApp);app.config=Config()
    with pytest.raises(OSError,match='disk full'):app.save()
    assert path.read_text()==previous and not list(tmp_path.glob('config-*.tmp'))


def test_cached_model_uses_the_same_offline_file_selection_as_inference(monkeypatch,tmp_path):
    from dictation.windows_app import model_ready
    from dictation.core import Config
    from faster_whisper import utils
    from huggingface_hub.errors import IncompleteSnapshotError
    import huggingface_hub
    for name in ('config.json','model.bin','tokenizer.json','vocabulary.txt'):
        (tmp_path/name).write_text('public fixture')
    def cached(repo_id,**kwargs):
        # A model-only cache has no README/.gitattributes; the Hub requires
        # an explicit file selection to accept that partial repository.
        if not kwargs.get('allow_patterns'):
            raise IncompleteSnapshotError('README.md absent')
        assert kwargs['local_files_only'] is True
        return str(tmp_path)
    monkeypatch.setattr(huggingface_hub,'snapshot_download',cached)
    config=Config(model='tiny',cache_dir=str(tmp_path/'cache'))
    assert model_ready(config)
    (tmp_path/'model.bin').unlink()
    assert not model_ready(config)


def test_incomplete_download_keeps_the_previous_usable_model(monkeypatch):
    from dictation import windows_app
    from dictation.core import Config
    app=windows_app.WindowsApp.__new__(windows_app.WindowsApp)
    app.downloading=True;app.config=Config(model='medium');app.ready_model=True
    app.setup_window=None
    changes=[];app.set_state=lambda *args:changes.append(args)
    app.save=lambda:pytest.fail('An incomplete model must not replace saved configuration')
    monkeypatch.setattr(windows_app,'model_ready',lambda _:False)
    app.download_finished('tiny',None)
    assert app.config.model=='medium' and app.ready_model and not app.downloading
    assert changes[0][0]=='error'
