import os
from pathlib import Path
import sys
import types
import wave
import numpy as np
import pytest
from dictation.core import Config, Recorder


def fixture_stream(monkeypatch, overflow=False):
    instances = []
    class Stream:
        def __init__(self, callback, **_):
            self.callback, self.stopped, self.closed = callback, False, False
            instances.append(self)
        def start(self):
            self.callback(np.full((1600,1), 3000, dtype='int16'), 1600, None, overflow)
        def stop(self):
            self.stopped = True
        def close(self):
            self.closed = True
    monkeypatch.setitem(sys.modules, 'sounddevice', types.SimpleNamespace(InputStream=Stream))
    return instances


def test_recording_captures_immediately_and_wav_is_private(monkeypatch):
    streams = fixture_stream(monkeypatch)
    recorder = Recorder(Config())
    recorder.start()
    assert recorder.frames == 1600
    assert recorder.level > 0
    audio = recorder.stop()
    try:
        if os.name == 'posix':
            assert os.stat(audio).st_mode & 0o777 == 0o600
        else:
            import tempfile
            assert Path(audio).parent == Path(tempfile.gettempdir())
        with wave.open(audio) as data:
            assert data.getnchannels() == 1
            assert data.getframerate() == 16000
            assert data.getnframes() == 1600
        assert streams[0].stopped and streams[0].closed
        assert not recorder.chunks
        assert recorder.level == 0
    finally:
        Path(audio).unlink()


def test_cancel_closes_capture_without_writing_audio(monkeypatch):
    streams = fixture_stream(monkeypatch)
    recorder = Recorder(Config())
    recorder.start()
    recorder.cancel()
    assert streams[0].stopped and streams[0].closed
    assert not recorder.chunks
    assert recorder.stream is None


def test_capture_error_does_not_transcribe_partial_audio(monkeypatch):
    streams = fixture_stream(monkeypatch, overflow=True)
    recorder = Recorder(Config())
    recorder.start()
    with pytest.raises(RuntimeError, match='overflow'):
        recorder.stop()
    assert streams[0].closed
    assert not recorder.chunks


def test_capture_duration_bounds_memory(monkeypatch):
    streams = fixture_stream(monkeypatch)
    recorder = Recorder(Config(max_record_seconds=1))
    recorder.start()
    for _ in range(30):
        streams[0].callback(np.zeros((1600,1), dtype='int16'), 1600, None, False)
    assert recorder.frames == 16000
    recorder.cancel()


def test_disconnect_still_closes_stream_and_discards_canceled_audio():
    recorder=Recorder(Config())
    closed=[]
    class Disconnected:
        def stop(self):raise RuntimeError('Device disconnected')
        def close(self):closed.append(True)
    recorder.stream=Disconnected();recorder.chunks=[b'private audio'];recorder.level=0.7
    with pytest.raises(RuntimeError,match='disconnected'):recorder.cancel()
    assert closed and recorder.stream is None and not recorder.chunks and recorder.level==0
