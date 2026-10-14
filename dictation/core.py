"""Audio capture and isolated, lazy Whisper worker lifecycle."""
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time
import wave


@dataclass
class Config:
    model: str = "medium"
    cache_dir: str = str(Path.home() / ".cache/system-dictation/models")
    button: int = 8
    paste_button: int = 9
    gpu_min_free_mb: int = 3072
    gpu_running_reserve_mb: int = 512
    threads: int = 12
    idle_seconds: int = 120
    max_record_seconds: int = 180
    language: str = "en"
    sound: bool = True

    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text()) if Path(path).exists() else {}
        if "paste_button" not in data and data.get("button") == 9:
            data["paste_button"] = 8
        cfg = cls(**data)
        if not 6 <= cfg.button <= 32 or not 6 <= cfg.paste_button <= 32:
            raise ValueError("Choose an extra mouse button between 6 and 32.")
        if cfg.button == cfg.paste_button:
            raise ValueError("Recording and paste need different mouse buttons.")
        if cfg.idle_seconds < 1 or not 1 <= cfg.max_record_seconds <= 600:
            raise ValueError("Invalid idle or recording duration.")
        return cfg


class Engine:
    """Use only from a single serial executor; CUDA crashes cannot kill the tray."""
    def __init__(self, config, free_memory=None):
        self.config = config
        self.process = None
        self.device = None
        self.stopping = False
        self.free_memory = free_memory or self.gpu_free_mb

    @staticmethod
    def gpu_free_mb():
        try:
            result = subprocess.run(
                ["nvidia-smi", "--id=0", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3, check=True,
            )
            return int(result.stdout.strip())
        except (OSError, ValueError, subprocess.SubprocessError):
            return 0

    def close(self):
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
            self.process.stdin.close()
            self.process.stdout.close()
        self.process = None
        self.device = None

    def _reply(self, timeout):
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout):
                raise RuntimeError("Speech model timed out. Try a shorter recording.")
            line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("Speech worker stopped unexpectedly.")
        reply = json.loads(line)
        if "error" in reply:
            raise RuntimeError(reply["error"])
        return reply

    def _start(self, device):
        self.close()
        if self.stopping:
            raise RuntimeError("Dictation is shutting down.")
        env = dict(os.environ, HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1")
        self.process = subprocess.Popen(
            [sys.executable, "-u", "-m", "dictation.worker", device, json.dumps(self.config.__dict__)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1, env=env,
        )
        self._reply(180)
        self.device = device

    def prepare(self):
        if self.stopping:
            raise RuntimeError("Dictation is shutting down.")
        if self.process and self.process.poll() is None:
            if self.device != "cuda" or self.free_memory() >= self.config.gpu_running_reserve_mb:
                return self.device
        device = "cuda" if self.free_memory() >= self.config.gpu_min_free_mb else "cpu"
        try:
            self._start(device)
        except Exception:
            self.close()
            if device != "cuda" or self.stopping:
                raise
            try:
                self._start("cpu")
            except Exception:
                self.close()
                raise
        return self.device

    def transcribe(self, audio):
        self.prepare()
        try:
            return self._transcribe(audio)
        except Exception:
            was_gpu = self.device == "cuda"
            self.close()
            if not was_gpu or self.stopping:
                raise
            try:
                self._start("cpu")
                return self._transcribe(audio)
            except Exception:
                self.close()
                raise

    def _transcribe(self, audio):
        self.process.stdin.write(json.dumps({"audio": str(audio)}) + "\n")
        self.process.stdin.flush()
        result = self._reply(300)
        return result["text"], self.device


def input_level(data):
    """Normalized RMS meter for signed 16-bit PCM; describes input, not speech."""
    import numpy as np
    if not data.size:
        return 0.0
    samples = data.astype(np.float32) / 32768.0
    rms = math.sqrt(float(np.mean(samples * samples)))
    if rms <= 0:
        return 0.0
    return max(0.0, min(1.0, (20 * math.log10(rms) + 60) / 48))


class TranscriptHistory:
    """Five completed transcripts, newest first, never persisted."""
    def __init__(self):
        self.items = []
        self.selected = 0

    @property
    def text(self):
        return self.items[self.selected] if self.items else ""

    def add(self, text):
        text = text.strip()
        if text:
            self.items = [text, *self.items][:5]
            self.selected = 0

    def select(self, index):
        if not 0 <= index < len(self.items):
            raise ValueError("This transcript is no longer in the recent history.")
        self.selected = index


class Recorder:
    def __init__(self, config):
        self.config = config
        self.stream = None
        self.chunks = []
        self.frames = 0
        self.problem = None
        self.level = 0.0
        self.level_updated_at = self.last_signal = 0.0

    def start(self):
        import sounddevice as sd
        self.chunks, self.frames, self.problem = [], 0, None
        self.level = 0.0
        self.level_updated_at = self.last_signal = time.monotonic()

        def receive(data, frames, timing, status):
            self.level = input_level(data)
            self.level_updated_at = time.monotonic()
            if self.level > 0.08:
                self.last_signal = self.level_updated_at
            if status:
                self.problem = "Microphone overflow or interruption. Please record again."
            if self.frames + frames <= self.config.max_record_seconds * 16000:
                self.chunks.append(data.copy())
                self.frames += frames

        self.stream = sd.InputStream(samplerate=16000, channels=1, dtype="int16", callback=receive)
        try:
            self.stream.start()
        except Exception:
            self.stream.close()
            self.stream = None
            raise

    def stop(self):
        import numpy as np
        self.cancel_stream()
        if self.problem:
            self.chunks.clear()
            raise RuntimeError(self.problem)
        if not self.chunks:
            raise RuntimeError("No microphone audio was captured.")
        data = np.concatenate(self.chunks)
        self.chunks.clear()
        fd, path = tempfile.mkstemp(prefix="dictation-", suffix=".wav")
        os.close(fd)
        try:
            with wave.open(path, "wb") as out:
                out.setnchannels(1)
                out.setsampwidth(2)
                out.setframerate(16000)
                out.writeframes(data.tobytes())
        except Exception:
            Path(path).unlink(missing_ok=True)
            raise
        return path

    def cancel_stream(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.level = 0.0

    def cancel(self):
        self.cancel_stream()
        self.chunks.clear()
