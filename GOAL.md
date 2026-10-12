# System dictation — active milestone

Goal: Andrew can dictate privately into focused text fields on his Mint Cinnamon X11 desktop using the Back thumb mouse button.

Done when:
1. A login-started tray listener uses button 8 as a consumed toggle; first click records immediately and loads Whisper in parallel, second stops and transcribes.
2. Tessera's faster-whisper medium pipeline works locally, preferring CUDA with conservative free-VRAM admission and automatic CPU int8 retry for GPU load/inference failures.
3. Text inserts at the focused cursor in native GUI, browser and terminal targets; changed focus or failed insertion preserves a recoverable result. Recording/processing/errors are visible; idle model memory is released.
4. Installation/startup/removal are reversible and tested in a disposable Mint VM. No host desktop app or service is started or changed by the agent.
5. Meaningful lifecycle/fallback tests and OS workflow evidence are retained, with GPU and physical microphone/mouse limitations stated honestly.

Excluded: Wayland/Windows/macOS, streaming transcription, voice commands, cloud STT, Tessera changes, general automation framework.

Proof: targeted behavior tests, real Whisper fixture transcription, VM mouse-toggle/audio/tray/paste/focus/restart/recovery checks, and source-blind exploratory qualification. Host activation is a user-run command under the host protection rule.
