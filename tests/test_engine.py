import json
import subprocess
import sys
import pytest
from dictation.core import Config, Engine


class FixtureEngine(Engine):
    """Real subprocess protocol, simulated CUDA errors without allocating VRAM."""
    def __init__(self, free, fail_load=False, fail_inference=False, crash=False):
        super().__init__(Config(), free_memory=lambda: free[0])
        self.fail_load, self.fail_inference, self.crash = fail_load, fail_inference, crash
        self.children, self.started = [], []

    def _start(self, device):
        self.close()
        self.started.append(device)
        script = (
            'import json, sys, os\n'
            f'device={device!r}\n'
            f'fail_load={self.fail_load!r}; fail_inference={self.fail_inference!r}; crash={self.crash!r}\n'
            'if device == "cuda" and fail_load:\n'
            ' print(json.dumps({"error":"CUDA out of memory"}), flush=True); sys.exit(1)\n'
            'print(json.dumps({"ready":device}), flush=True)\n'
            'for line in sys.stdin:\n'
            ' if device == "cuda" and crash: os._exit(134)\n'
            ' reply={"error":"CUDA allocation failed"} if device == "cuda" and fail_inference else {"text":"Test words."}\n'
            ' print(json.dumps(reply), flush=True)\n'
        )
        self.process = subprocess.Popen([sys.executable, '-u', '-c', script], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        self.children.append(self.process)
        self._reply(3)
        self.device = device


@pytest.mark.parametrize('fail_load,fail_inference,crash', [(True, False, False), (False, True, False), (False, False, True)])
def test_gpu_failure_retries_identical_job_on_cpu_and_reaps_gpu(fail_load, fail_inference, crash):
    engine = FixtureEngine([9000], fail_load, fail_inference, crash)
    try:
        assert engine.transcribe('audio.wav') == ('Test words.', 'cpu')
        assert engine.started == ['cuda', 'cpu']
        assert engine.children[0].poll() is not None
    finally:
        engine.close()
    assert all(p.poll() is not None for p in engine.children)


def test_low_memory_avoids_gpu_loading():
    engine = FixtureEngine([1000])
    try:
        assert engine.transcribe('audio.wav') == ('Test words.', 'cpu')
        assert engine.started == ['cpu']
    finally:
        engine.close()


def test_memory_pressure_after_warm_load_releases_gpu_before_cpu_retry():
    free = [9000]
    engine = FixtureEngine(free)
    try:
        assert engine.prepare() == 'cuda'
        free[0] = 100
        assert engine.transcribe('audio.wav') == ('Test words.', 'cpu')
        assert engine.children[0].poll() is not None
    finally:
        engine.close()


def test_worker_reused_then_unloaded_and_reloaded():
    engine = FixtureEngine([9000])
    try:
        assert engine.prepare() == 'cuda'
        engine.transcribe('one.wav')
        engine.transcribe('two.wav')
        assert engine.started == ['cuda']
        engine.close()
        assert engine.children[0].poll() is not None
        engine.transcribe('three.wav')
        assert engine.started == ['cuda', 'cuda']
    finally:
        engine.close()


def test_shutdown_never_restarts_gpu_or_cpu_worker():
    engine = FixtureEngine([9000])
    engine.stopping = True
    with pytest.raises(RuntimeError, match='shutting down'):
        engine.prepare()
    assert not engine.children


def test_invalid_primary_mouse_button_is_rejected(tmp_path):
    path = tmp_path/'config.json'
    path.write_text(json.dumps({'button':1}))
    with pytest.raises(ValueError, match='extra mouse button'):
        Config.load(path)
