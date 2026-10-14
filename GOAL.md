# System dictation — voice feedback and transcript recovery

Status: active improvement milestone. Andrew confirmed the original app works on his live desktop. That running instance must remain undisturbed; changes and qualification use a separate checkout and VM.

Goal: Andrew can see microphone activity while dictating and recover any of his five most recent transcripts with the Forward thumb button.

Done when:
1. The recording tray icon reacts to real microphone intensity; sustained silence shows a check-mute message, and level feedback ends on stop/cancel.
2. Front thumb / Forward (button 9) pastes the selected completed transcript into the currently focused field without Enter or browser Forward navigation.
3. A revisitable tray history holds the five most recent successful transcripts in session memory, including results whose automatic paste failed. Selecting an older item changes the Forward-button paste target; empty recordings/errors do not replace prior items.
4. Existing Back-toggle, automatic paste, GPU/CPU fallback, focus protection, idle unloading and old configuration remain compatible. Speech/history are not saved to disk.
5. Targeted regressions and independent Mint VM workflows cover voice/silence feedback, bounded history and Forward recovery across native/browser/terminal fields. The live app is not restarted or changed under Andrew.

Excluded: history across restarts, hardware mute detection, changing automatic-paste defaults, Wayland/Windows/macOS, streaming transcription, voice commands, cloud STT, Tessera changes, general automation framework.

Proof: targeted behavior tests, real Whisper fixture transcription, VM mouse-toggle/audio/tray/paste/focus/restart/recovery checks, and source-blind exploratory qualification. Host activation is a user-run command under the host protection rule.

Original milestone proof remains in `VERIFICATION.md`. This update adds input feedback and recovery without reopening the verified STT engine.
