"""Audio capture and isolated, lazy Whisper worker lifecycle."""
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import wave
from .paths import cache_directory, punctuation_directory


@dataclass
class Config:
    model: str = "medium"
    cache_dir: str = field(default_factory=cache_directory)
    punctuation_dir: str = field(default_factory=punctuation_directory)
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
        self._reader_process = None
        self._job = None

    @staticmethod
    def gpu_free_mb():
        try:
            result = subprocess.run(
                ["nvidia-smi", "--id=0", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3, check=True,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
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
            for stream in (self.process.stdin,self.process.stdout):
                try:stream.close()
                except OSError:pass  # A crashed worker can leave buffered pipe data.
        self.process = None
        self.device = None
        if self._job:
            self._job.close()
            self._job = None

    def _reply(self, timeout):
        if self._reader_process is not self.process:
            self._reader_process = self.process
            self._replies = queue.Queue()
            stream, channel = self.process.stdout, self._replies
            def read():
                try:
                    for line in stream:
                        channel.put(line)
                except (OSError, ValueError):
                    pass
                finally:
                    channel.put('')
            threading.Thread(target=read, daemon=True).start()
        try:
            line = self._replies.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError("Speech model timed out. Try a shorter recording.") from None
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
        command = ([str(Path(sys.executable).with_name('SaywardWorker.exe')), '--worker'] if getattr(sys, 'frozen', False)
                   else [sys.executable, '-u', '-m', 'dictation.worker'])
        self.process = subprocess.Popen(
            [*command, device, json.dumps(self.config.__dict__)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding='utf-8', bufsize=1, env=env,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
        if sys.platform == 'win32':
            from .windows_native import WorkerJob
            try:
                self._job = WorkerJob(self.process)
            except Exception:
                self.close()
                raise
        if self.stopping:
            self.close()
            raise RuntimeError('Dictation is shutting down.')
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
        stream, self.stream = self.stream, None
        try:
            if stream:
                try:stream.stop()
                finally:stream.close()
        finally:
            self.level = 0.0

    def cancel(self):
        try:self.cancel_stream()
        finally:self.chunks.clear()
