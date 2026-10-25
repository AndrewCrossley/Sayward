"""Shared dictation lifecycle; views marshal callbacks onto their UI thread."""
import concurrent.futures
from pathlib import Path
import time
from .core import Engine, Recorder, TranscriptHistory


class Session:
    def __init__(self, config, desktop, dispatch):
        self.config, self.desktop, self.dispatch = config, desktop, dispatch
        self.recorder, self.engine = Recorder(config), Engine(config)
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.state, self.started = 'idle', 0
        self.history, self.target = TranscriptHistory(), None
        self.closed = False
        self.idle_deadline = 0
        self.last_press = {}
        self.meter_level, self.meter_frame = 0.0, None
        self.recording_message = ''
        self.meter_message = None

    def poll(self):
        if self.closed:
            return False
        for button in self.desktop.events():
            now = time.monotonic()
            if now - self.last_press.get(button, 0) >= 0.3:
                self.last_press[button] = now
                if button == self.config.button:
                    self.toggle()
                elif button == self.config.paste_button:
                    self.paste_last()
        return True

    def toggle(self):
        if self.state == "working":
            return
        if self.state == "recording":
            try:
                audio = self.recorder.stop()
            except Exception as exc:
                self.set_state("error", str(exc))
                return
            self.target = self.desktop.focus()
            self.set_state("working", "Transcribing — please keep this text field focused")
            self.cue("stop")
            self.submit(lambda: self.engine.transcribe(audio), self.finished, audio)
            return
        try:
            self.recorder.start()
        except Exception:
            self.set_state("error", "Microphone unavailable — check desktop sound input and try again")
            return
        self.started = time.monotonic()
        self.meter_level = 0.0
        self.idle_deadline = 0
        self.set_state("recording", "Recording — click Back thumb button again to transcribe")
        self.cue("start")
        self.submit(self.engine.prepare, self.prepared)

    def submit(self, work, callback, audio=None):
        def run():
            try:
                value, error = work(), None
            except Exception as exc:
                value, error = None, str(exc)
            finally:
                if audio:
                    Path(audio).unlink(missing_ok=True)
            if not self.closed:
                self.dispatch(callback, value, error)
        self.executor.submit(run)

    def prepared(self, device, error):
        if self.state == "recording":
            message = "Recording — " + ("model will retry after stop" if error else f"{device.upper()} model ready")
            self.set_state("recording", message)
        return False

    def finished(self, result, error):
        self.idle_deadline = time.monotonic() + self.config.idle_seconds
        if error:
            self.set_state("error", "Transcription failed — " + error)
            self.cue("error")
            return False
        text, device = result
        if not text:
            self.set_state("idle", f"No speech detected ({device.upper()}) — ready")
            return False
        self.history.add(text)
        self.refresh_history()
        try:
            self.desktop.paste(text, self.target)
        except Exception as exc:
            self.set_state("error", str(exc))
            self.cue("error")
            return False
        self.set_state("idle", f"Text pasted ({device.upper()}) — ready")
        self.cue("done")
        return False

    def cancel(self):
        if self.state == "recording":
            self.idle_deadline = time.monotonic() + self.config.idle_seconds
            try:
                self.recorder.cancel()
                self.set_state("idle", "Recording cancelled — ready")
            except Exception as error:
                self.set_state('error','Capture stopped — '+str(error))

    def paste_last(self):
        if self.history.text and self.state not in ("recording", "working"):
            try:
                self.desktop.paste(self.history.text, self.desktop.focus())
                self.set_state("idle", "Selected transcript pasted — ready")
            except Exception as exc:
                self.set_state("error", str(exc))
        return False

    def unload(self):
        if self.state in ("recording", "working"):
            return
        self.idle_deadline = 0
        self.submit(self.engine.close, self.unloaded)

    def unloaded(self, *_):
        # A click may start a fresh recording while the unload task completes.
        if self.state not in ("recording", "working"):
            self.set_state("idle", "Model unloaded — ready")
        return False

    def tick(self):
        if self.closed:
            return False
        now = time.monotonic()
        if self.state == "recording" and now - self.started >= self.config.max_record_seconds:
            self.toggle()
        elif self.state not in ("recording", "working") and self.idle_deadline and now >= self.idle_deadline:
            self.unload()
        return True


    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self.engine.stopping = True
        try:self.recorder.cancel()
        except Exception:pass  # Shutdown must still release hooks and the worker.
        if self.engine.process:
            self.engine.process.terminate()
        self.executor.submit(self.engine.close)
        self.executor.shutdown(wait=False)
        self.desktop.close()
