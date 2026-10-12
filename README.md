# System Dictation

Private local dictation for Andrew's Linux Mint Cinnamon **X11** desktop, using the same faster-whisper / Whisper medium engine as old Tessera (`scripts/local-whisper-stt.py`). Tessera itself is untouched.

Run once from a terminal:

```bash
cd /home/andrew/projects/system-dictation
./install.sh
./bin/dictation
```

The installer creates a desktop-login autostart entry. After subsequent boots, the tray listener starts when you sign into Cinnamon. The model stays unloaded until the first dictation. You do not need a root/system service: microphone, tray and focused-cursor access belong to the desktop session.

Place the cursor in a text field and click **Back thumb / mouse button 8**. Recording begins immediately while the model loads in parallel. Red tray icon means recording. Click again to stop; amber means transcribing. Keep the target focused until text is pasted. The app consumes the bound button, so it will not navigate Back while active. Quit restores ordinary button behavior.

GPU 0 is preferred when at least 3 GiB of VRAM is free. CUDA uses int8/float16; CPU uses int8, with 12 threads. Low free VRAM, CUDA initialization errors, allocation failures or a GPU worker crash trigger CPU processing of the same recording. The model remains warm for 120 seconds after use, then the subprocess exits and releases its memory. Recording automatically stops at 180 seconds. Extra presses during transcription are ignored.

Tray menu: Start/Stop, Cancel recording, Paste last result, Copy last result, How to use / Practice, Sound cues, Unload model now and Quit. Results remain in memory for recovery. Changing focus while transcription runs prevents automatic paste into the new window. Paste last result acts on the field focused after the menu closes. Keyboard modifiers must be released before pasting.

Text insertion uses the clipboard and Shift+Insert, so it supports normal editable fields, browsers and Linux terminals without pressing Enter. **Dictation replaces both clipboard and primary selection.** Applications that block paste, password/secure fields, games, remote-desktop targets and Wayland are outside the supported scope. The insertion cursor stays under the application's control; do not switch input fields while transcription runs. A different field in the same X11 window cannot always be distinguished.

Configuration: `~/.config/system-dictation/config.json`. Change it while the app is stopped. `button`, `idle_seconds`, `gpu_min_free_mb`, `language`, `sound`, and other defaults are readable there. Empty language enables automatic language detection. The medium model is reused from Tessera's existing cache when available; otherwise setup downloads it once. GPU libraries are private Python dependencies, so no host NVIDIA driver or system CUDA installation is modified. The worker uses cached files only and disables Hugging Face network/telemetry. Audio is a mode-0600 temporary WAV, deleted after processing; transcripts are not logged or written to disk.

To disable: Quit from the tray, then `./uninstall.sh`. It removes startup and the launcher, preserving configuration/source/model files. Cinnamon's Startup Applications can also disable the entry. Do not move/delete this project directory while its autostart entry is enabled.

Verification and material limitations are recorded in `VERIFICATION.md`. This project does not provide voice commands or stream partial words.
