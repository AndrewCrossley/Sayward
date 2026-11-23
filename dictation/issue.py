"""Optional issue recording (screen + voice + input) through an external `record-issue` CLI.

Sayward only drives the recorder; it never records screen or input itself. The contract is
`record-issue start|stop` plus `$RECORD_ISSUE_ROOT/.active` (present while a recording is
live; it holds the bundle directory, whose session.json has the start `epoch`). Without the
CLI, or off Linux X11, the feature does not exist and Sayward behaves exactly as before.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from .core import input_level


def find_recorder(config):
    if not sys.platform.startswith("linux"):
        return None
    configured = os.path.expanduser(config.issue_recorder) if config.issue_recorder else ""
    if configured:
        return configured if os.access(configured, os.X_OK) else None
    return shutil.which("record-issue")


class IssueRecorder:
    def __init__(self, command, root=None):
        self.command = command
        self.root = Path(root or os.environ.get("RECORD_ISSUE_ROOT") or Path.home() / ".local/share/issue-sessions")
        self.last_bundle = None
        self.warnings = []  # recorder health warnings from the last start

    def live(self):
        """(bundle_dir, started_epoch, max_seconds, mic_source) of the live recording, or None."""
        try:
            bundle = (self.root / ".active").read_text().strip()
        except OSError:
            return None
        if not bundle:
            return None
        try:
            session = json.loads((Path(bundle) / "session.json").read_text())
            epoch, max_s = float(session["epoch"]), int(session.get("max_s") or 0)
            mic = str(session.get("mic") or "default")
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            epoch, max_s, mic = None, 0, "default"
        return bundle, epoch, max_s, mic

    def _run(self, action, timeout):
        try:
            done = subprocess.run([self.command, action], stdin=subprocess.DEVNULL, capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"record-issue {action} timed out") from None
        except OSError as exc:
            raise RuntimeError(f"record-issue {action} could not run: {exc}") from None
        lines = (done.stdout + done.stderr).strip().splitlines()
        if done.returncode:
            raise RuntimeError(lines[-1] if lines else f"record-issue {action} failed ({done.returncode})")
        return done.stdout.splitlines(), done.stderr.splitlines()

    def start(self):
        # A recorder that fails its health check still leaves the others running (exit 0).
        _, errors = self._run("start", 60)
        self.warnings = [line.removeprefix("WARNING: ").split("; see ")[0] for line in errors if line.startswith("WARNING:")]
        return self.live()

    def stop(self):
        for line in self._run("stop", 600)[0]:
            if line.startswith("bundle: "):
                self.last_bundle = line[len("bundle: "):].strip()
        return self.last_bundle


class LevelMonitor:
    """Input level for the tray glow while an issue recording is live; keeps no audio."""
    def __init__(self):
        self.stream = None
        self.level = 0.0
        self.level_updated_at = self.last_signal = 0.0

    @property
    def running(self):
        return self.stream is not None

    def start(self):
        import sounddevice as sd
        self.level = 0.0
        self.level_updated_at = self.last_signal = time.monotonic()

        def receive(data, frames, timing, status):
            self.level = input_level(data)
            self.level_updated_at = time.monotonic()
            if self.level > 0.08:
                self.last_signal = self.level_updated_at

        stream = sd.InputStream(samplerate=16000, channels=1, dtype="int16", callback=receive)
        try:
            stream.start()
        except Exception:
            stream.close()
            raise
        self.stream = stream

    def stop(self):
        stream, self.stream = self.stream, None
        self.level = 0.0
        if stream:
            try:
                stream.stop()
            finally:
                stream.close()
