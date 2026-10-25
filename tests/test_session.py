from types import SimpleNamespace
import threading
import pytest
from dictation.core import Config, Engine
from dictation.session import Session


def test_completion_dispatches_to_view_and_removes_audio_before_callback(tmp_path):
    dispatched=[]
    session=Session(Config(),SimpleNamespace(close=lambda:None),lambda *args:dispatched.append(args))
    audio=tmp_path/'recording.wav';audio.write_bytes(b'public fixture')
    done=threading.Event()
    def work():done.set();return ('words','cpu')
    callback=lambda *_:None
    session.submit(work,callback,str(audio))
    assert done.wait(2)
    session.executor.shutdown(wait=True)
    assert not audio.exists()
    assert dispatched==[(callback,('words','cpu'),None)]
    session.engine.close()


def test_no_callbacks_or_worker_restarts_after_shutdown():
    session=Session(Config(),SimpleNamespace(close=lambda:None),lambda *_:pytest.fail('late UI callback'))
    session.shutdown()
    assert session.closed and session.engine.stopping
    with pytest.raises(RuntimeError,match='shutting down'):session.engine.prepare()


def test_worker_stdout_timeout_is_bounded():
    import subprocess,sys
    engine=Engine(Config())
    engine.process=subprocess.Popen([sys.executable,'-c','import time;time.sleep(5)'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True)
    try:
        with pytest.raises(RuntimeError,match='timed out'):engine._reply(0.05)
    finally:engine.close()


def test_frozen_command_targets_console_worker(monkeypatch):
    import subprocess,sys
    from dictation import core
    engine=Engine(Config());commands=[]
    monkeypatch.setattr(sys,'frozen',True,raising=False)
    monkeypatch.setattr(sys,'executable','/app/Sayward.exe')
    class Child:
        stdin=SimpleNamespace(close=lambda:None)
        stdout=SimpleNamespace(close=lambda:None)
        terminate=lambda _:None
        wait=lambda *_,**__:None
    monkeypatch.setattr(core.subprocess,'Popen',lambda args,**kwargs:commands.append(args) or Child())
    monkeypatch.setattr(engine,'_reply',lambda _: {'ready':'cpu'})
    # Avoid constructing a real Windows job in this command-construction check.
    monkeypatch.setattr(sys,'platform','linux')
    engine._start('cpu')
    assert commands[0][0].replace('\\','/')=='/app/SaywardWorker.exe'
    assert commands[0][1:3]==['--worker','cpu']
    engine.close()


def test_shutdown_releases_desktop_even_when_microphone_disappears():
    released=[]
    session=Session(Config(),SimpleNamespace(close=lambda:released.append(True)),lambda *_:None)
    session.recorder.cancel=lambda:(_ for _ in ()).throw(RuntimeError('disconnected'))
    session.shutdown()
    assert session.closed and session.engine.stopping and released


def test_quit_during_process_creation_reaps_child_without_waiting_for_ready(monkeypatch):
    from dictation import core
    import sys
    engine=Engine(Config());terminated=[]
    class Child:
        stdin=SimpleNamespace(close=lambda:None)
        stdout=SimpleNamespace(close=lambda:None)
        terminate=lambda _:terminated.append(True)
        wait=lambda *_,**__:None
    def create(*args,**kwargs):
        engine.stopping=True
        return Child()
    monkeypatch.setattr(core.subprocess,'Popen',create)
    monkeypatch.setattr(sys,'platform','linux')
    monkeypatch.setattr(engine,'_reply',lambda _:pytest.fail('Quit must not wait for model startup'))
    with pytest.raises(RuntimeError,match='shutting down'):engine._start('cpu')
    assert terminated and engine.process is None
