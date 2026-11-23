"""Shared dictation lifecycle; views marshal callbacks onto their UI thread."""
import concurrent.futures
from pathlib import Path
import time
import threading
from .core import Engine, Recorder, TranscriptHistory
from .punctuation import Punctuator, download_model, insertion_text, validate_words

# Back-press chooser: pointer travel (X pixels) and time window that decide it.
CHOOSER_DOWN_PX, CHOOSER_UP_PX, CHOOSER_SECONDS = 90, 40, 1.2


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
        self.recording_target = None
        self.closed = False
        self.stop_guard_at = None
        # Optional issue recording; a view sets an IssueRecorder when the CLI exists.
        self.issue, self.issue_live, self.issue_busy = None, None, False
        # A stop whose finalize failed leaves an unfinished bundle that only `stop` recovers.
        self.issue_unfinished = False
        self.chooser = None
        self.clear_submission()
        self.idle_deadline = 0
        self.last_press = {}
        self.meter_level, self.meter_frame = 0.0, None
        self.recording_message = ''
        self.meter_message = None

    def poll(self):
        if self.closed:
            return False
        # stop() can block briefly. Drain again before delivery so clicks that
        # arrived during that call retain their original intent and timestamps.
        while events := self.desktop.events():
            for button, pressed_at in events:
                if button == self.config.button and self.stop_guard_at is not None and 0 <= pressed_at - self.stop_guard_at <= 0.75:
                    if self.can_request_enter(pressed_at):
                        self.toggle(allow_submit=True, pressed_at=pressed_at)
                    # Even a fast failure/silent result must consume the second
                    # stop click, rather than accidentally starting a capture.
                    continue
                if pressed_at - self.last_press.get(button, 0) >= 0.3:
                    self.last_press[button] = pressed_at
                    if button == self.config.button:
                        starting = self.state not in ("recording", "working")
                        self.toggle(allow_submit=True, pressed_at=pressed_at)
                        if starting and self.state == "recording":
                            self.open_chooser()
                    elif button == self.config.paste_button:
                        # Forward does nothing during a capture, so Back then Forward
                        # is free to mean "switch this capture to issue recording".
                        if self.state == "recording" and self.issue and not self.issue_busy:
                            self.issue_from_capture()
                        else:
                            self.paste_last()
        self.track_chooser()
        self.advance_delivery()
        return True

    def open_chooser(self):
        if not self.issue or self.issue_busy or not self.config.back_chooser:
            return
        try:
            x, y = self.desktop.pointer()
        except Exception:
            return
        self.chooser = (x, y, time.monotonic())
        self.show_chooser(x, y, bool(self.issue_live))

    def track_chooser(self):
        if not self.chooser:
            return
        _, y0, opened = self.chooser
        if self.state != "recording":
            return self.close_chooser()
        try:
            _, y = self.desktop.pointer()
        except Exception:
            return self.close_chooser()
        # Expiry first: a late poll must not turn movement after the window into a switch.
        if time.monotonic() - opened >= CHOOSER_SECONDS or y0 - y >= CHOOSER_UP_PX:
            self.close_chooser()
        elif y - y0 >= CHOOSER_DOWN_PX:
            self.issue_from_capture()

    def close_chooser(self):
        if self.chooser:
            self.chooser = None
            self.hide_chooser()

    def issue_from_capture(self):
        """Discard the dictation capture just started and toggle issue recording instead."""
        self.close_chooser()
        if not self.issue or self.issue_busy or self.state != "recording":
            return
        self.cancel()
        self.issue_toggle()

    def issue_toggle(self):
        if not self.issue or self.issue_busy or self.closed:
            return
        stopping = bool(self.issue_live) or self.issue_unfinished
        work = self.issue.stop if stopping else self.issue.start
        self.issue_busy = True
        self.issue_changed()

        def run():
            try:
                value, error = work(), None
            except Exception as exc:
                value, error = None, str(exc)
            if not self.closed:
                self.dispatch(self.issue_done, stopping, value, error)
        threading.Thread(target=run, daemon=True).start()

    def issue_done(self, stopping, value, error):
        self.issue_busy = False
        # The CLI drops .active before finalizing, and start refuses an unfinished bundle:
        # either failure means the next toggle must run stop again.
        self.issue_unfinished = bool(error) and (stopping or "unfinished" in error)
        self.refresh_issue(force=True)
        if self.state not in ("recording", "working"):
            if error:
                self.set_state("error", f"Issue recording {'stop' if stopping else 'start'} failed — {error}")
            else:
                self.set_state("idle", "Issue bundle saved — tray: Copy issue bundle path" if stopping
                               else "Issue recording — screen, voice and input; Back then Forward stops it")
        return False

    def refresh_issue(self, force=False):
        if not self.issue:
            return
        live = self.issue.live()
        changed = bool(live) != bool(self.issue_live)
        self.issue_live = live
        if changed or force:
            self.issue_changed()

    def show_chooser(self, x, y, live):
        """Views draw the Back chooser near the pointer without taking focus."""

    def hide_chooser(self):
        """Views remove the Back chooser."""

    def issue_changed(self):
        """Views update their issue-recording indicators."""

    def before_capture(self):
        """Views release anything holding the microphone before dictation opens it."""

    def clear_submission(self):
        self.stop_click_at = None
        self.submit_requested = False
        self.delivery = None
        self.enter_due = None
        self.enter_target = None

    def can_request_enter(self, pressed_at=None):
        at = time.monotonic() if pressed_at is None else pressed_at
        return self.stop_click_at is not None and 0 <= at - self.stop_click_at <= 0.75

    def toggle(self, allow_submit=False, pressed_at=None):
        if self.closed:
            return
        if allow_submit and self.state == 'working' and self.can_request_enter(pressed_at):
            self.submit_requested = True
            self.stop_click_at = None
            self.set_state('working', 'Paste + Enter requested — keep this text field focused')
            return
        if self.state == "working":
            return
        if self.pending and self.state != 'recording':
            return self.retry_punctuation(paste=True)
        if self.state == "recording":
            self.clear_submission()
            stopped_at = time.monotonic() if pressed_at is None else pressed_at
            self.stop_guard_at = stopped_at if allow_submit else None
            try:
                self.target = self.desktop.focus()
                audio = self.recorder.stop()
            except Exception as exc:
                try:
                    self.recorder.cancel()
                except Exception:
                    pass  # Still report the original stop/focus error.
                self.idle_deadline = time.monotonic() + self.config.idle_seconds
                self.set_state("error", str(exc))
                return
            if allow_submit:
                self.stop_click_at = stopped_at
            self.set_state("working", "Transcribing — click Back again within 0.75s for paste + Enter" if allow_submit else "Transcribing — keep this text field focused")
            self.cue("stop")
            self.submit(lambda: self.engine.transcribe(audio), self.finished, audio)
            return
        self.clear_submission()
        self.stop_guard_at = None
        try:
            self.recording_target = self.desktop.focus()
            self.before_capture()
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
            self.clear_submission()
            self.set_state("error", "Transcription failed — " + error)
            self.cue("error")
            return False
        text, device = result
        if not text:
            self.clear_submission()
            self.set_state("idle", f"No speech detected ({device.upper()}) — ready")
            return False
        self.pending = (text, device)
        if self.punctuation_downloading:
            self.clear_submission()
            self.set_state('error', 'Dictation saved while punctuation downloads — use Retry punctuation when ready')
        else:
            self._punctuate(paste=True, target=self.target)
        return False

    def retry_punctuation(self, paste=False, target=None):
        if not self.pending or self.state in ('recording', 'working') or self.punctuation_downloading:
            return False
        if paste and target is None:
            target = self.desktop.focus()
        self.clear_submission()
        return self._punctuate(paste, target)

    def _punctuate(self, paste, target):
        self.target = target
        self.punctuation_auto_paste = paste
        self.idle_deadline = 0
        self.set_state('working', 'Adding punctuation locally — '+('paste + Enter requested; ' if self.submit_requested else '')+'keep this text field focused')
        raw, _ = self.pending
        self.submit(lambda: self.punctuator.restore(raw), self.punctuated)
        return False

    def punctuated(self, text, error):
        self.idle_deadline = time.monotonic() + self.config.idle_seconds
        if not self.pending:
            return False
        if error:
            self.clear_submission()
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
            self.clear_submission()
            self.set_state('idle', 'Punctuation ready — focus your text field and press Forward')
            return False
        self.delivery = (text, device, self.target)
        # Drain OS click timestamps in poll before delivery: a queued second
        # click can precede this completion even when the UI processed it later.
        if self.stop_click_at is None and not self.submit_requested:
            self.advance_delivery()
        return False

    def advance_delivery(self):
        if self.closed:
            return
        now = time.monotonic()
        if self.delivery and (self.stop_click_at is None or now - self.stop_click_at > 0.75):
            text, device, target = self.delivery
            self.delivery = None
            # A stalled UI cannot reconstruct the focus at an earlier mouse
            # event. Automatic submission therefore also requires its origin.
            if self.submit_requested and (not self.recording_target or self.recording_target != target):
                self.clear_submission()
                self.set_state('error', 'Destination changed while recording — result saved; focus your field and press Forward')
                self.cue('error')
                return
            try:
                self.desktop.paste(insertion_text(text), target)
            except Exception as exc:
                self.clear_submission()
                self.set_state('error', str(exc))
                self.cue('error')
                return
            if self.submit_requested:
                # Let the destination consume its clipboard paste on the next
                # UI turns, then recheck focus/modifiers before a separate Enter.
                self.enter_target, self.enter_due = target, time.monotonic() + 0.15
                self.set_state('working', 'Text pasted — sending Enter')
            else:
                self.clear_submission()
                self.set_state('idle', f'Text pasted ({device.upper()}) — ready')
                self.cue('done')
        if self.enter_due is not None and now >= self.enter_due:
            target = self.enter_target
            self.clear_submission()
            try:
                self.desktop.enter(target)
            except Exception as exc:
                self.set_state('error', 'Text pasted; Enter not sent — '+str(exc))
                self.cue('error')
                return
            self.set_state('idle', 'Text pasted and Enter sent — ready')
            self.cue('done')

    def discard_pending(self):
        if self.state not in ('recording', 'working'):
            self.clear_submission()
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
            self.clear_submission()
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
        if not self.issue_busy:
            self.refresh_issue()
        now = time.monotonic()
        if self.state == "recording" and now - self.started >= self.config.max_record_seconds:
            self.toggle(allow_submit=False)
        elif self.state not in ("recording", "working") and self.idle_deadline and now >= self.idle_deadline:
            self.unload()
        return True


    def shutdown(self):
        if self.closed:
            return
        self.closed = True
        self.chooser = None
        self.clear_submission()
        self.pending = None
        self.engine.stopping = True
        try:self.recorder.cancel()
        except Exception:pass  # Shutdown must still release hooks and the worker.
        if self.engine.process:
            self.engine.process.terminate()
        self.executor.submit(self.close_models)
        self.executor.shutdown(wait=False)
        self.desktop.close()
