"""Shared dictation lifecycle; views marshal callbacks onto their UI thread."""
import concurrent.futures
from pathlib import Path
import time
import threading
from .core import Engine, Recorder, TranscriptHistory
from .punctuation import Punctuator, download_model, insertion_text, validate_words


class Session:
    def __init__(self, config, desktop, dispatch):
        self.config, self.desktop, self.dispatch = config, desktop, dispatch
        self.recorder, self.engine = Recorder(config), Engine(config)
        self.punctuator = Punctuator(config.punctuation_dir)
        self.pending = None
        self.punctuation_downloading = False
        self.punctuation_setup_message = ''
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
        if self.pending and self.state != 'recording':
            return self.retry_punctuation(paste=True)
        if self.state == "recording":
            try:
                audio = self.recorder.stop()
            except Exception as exc:
                self.idle_deadline = time.monotonic() + self.config.idle_seconds
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
        self.pending = (text, device)
        if self.punctuation_downloading:
            self.set_state('error', 'Dictation saved while punctuation downloads — use Retry punctuation when ready')
        else:
            self._punctuate(paste=True, target=self.target)
        return False

    def retry_punctuation(self, paste=False, target=None):
        if not self.pending or self.state in ('recording', 'working') or self.punctuation_downloading:
            return False
        if paste and target is None:
            target = self.desktop.focus()
        return self._punctuate(paste, target)

    def _punctuate(self, paste, target):
        self.target = target
        self.punctuation_auto_paste = paste
        self.idle_deadline = 0
        self.set_state('working', 'Adding punctuation locally — keep this text field focused')
        raw, _ = self.pending
        self.submit(lambda: self.punctuator.restore(raw), self.punctuated)
        return False

    def punctuated(self, text, error):
        self.idle_deadline = time.monotonic() + self.config.idle_seconds
        if not self.pending:
            return False
        if error:
            self.set_state('error', 'Dictation saved — use Punctuation setup, then Retry punctuation (Back)')
            self.punctuation_setup_message = 'Punctuation failed: '+error
            self.punctuation_changed()
            self.cue('error')
            return False
        raw, device = self.pending
        try:
            validate_words(raw, text)
        except Exception as exc:
            return self.punctuated(None, str(exc))
        self.pending = None
        self.history.add(text)
        self.refresh_history()
        if not self.punctuation_auto_paste:
            self.set_state('idle', 'Punctuation ready — focus your text field and press Forward')
            return False
        try:
            self.desktop.paste(insertion_text(text), self.target)
        except Exception as exc:
            self.set_state("error", str(exc))
            self.cue("error")
            return False
        self.set_state("idle", f"Text pasted ({device.upper()}) — ready")
        self.cue("done")
        return False

    def discard_pending(self):
        if self.state not in ('recording', 'working'):
            self.pending = None
            self.set_state('idle', 'Saved unprocessed dictation discarded — ready')

    def download_punctuation(self):
        if self.state in ('recording', 'working') or self.punctuation_downloading:
            return
        self.punctuation_downloading = True
        self.punctuation_setup_message = 'Downloading local punctuation files (~300 MB). Keep Sayward open.'
        self.punctuation_changed()
        def run():
            try:
                download_model(self.config.punctuation_dir)
                error = None
            except Exception as exc:
                error = str(exc)
            if not self.closed:
                self.dispatch(self.punctuation_downloaded, error)
        threading.Thread(target=run, daemon=True).start()

    def punctuation_downloaded(self, error):
        self.punctuation_downloading = False
        self.punctuation_setup_message = ('Download failed — '+error) if error else 'Punctuation model ready. Speech and text stay local.'
        self.punctuation_changed()
        if self.state not in ('recording', 'working'):
            self.set_state('error' if error else 'idle', self.punctuation_setup_message+(' Use Retry punctuation (Back) for saved dictation.' if self.pending else ''))

    def punctuation_changed(self):
        """Presentations update their revisitable setup controls on the UI thread."""

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
                self.desktop.paste(insertion_text(self.history.text), self.desktop.focus())
                self.set_state("idle", "Selected transcript pasted — ready")
            except Exception as exc:
                self.set_state("error", str(exc))
        return False

    def unload(self):
        if self.state in ("recording", "working"):
            return
        self.idle_deadline = 0
        self.submit(self.close_models, self.unloaded)

    def close_models(self):
        try:
            self.engine.close()
        finally:
            self.punctuator.close()

    def unloaded(self, *_):
        # A click may start a fresh recording while the unload task completes.
        if self.state not in ("recording", "working"):
            self.set_state("idle", "Models unloaded — dictation saved; use Retry punctuation (Back)" if self.pending else "Models unloaded — ready")
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
        self.pending = None
        self.engine.stopping = True
        try:self.recorder.cancel()
        except Exception:pass  # Shutdown must still release hooks and the worker.
        if self.engine.process:
            self.engine.process.terminate()
        self.executor.submit(self.close_models)
        self.executor.shutdown(wait=False)
        self.desktop.close()
