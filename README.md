# System Dictation

Private local dictation for Andrew's Linux Mint Cinnamon **X11** desktop, using the same faster-whisper / Whisper medium engine as old Tessera (`scripts/local-whisper-stt.py`). Tessera itself is untouched.

For this update, first **Quit the current System Dictation from its tray menu** when you are ready to switch. Run the new copy from a desktop terminal:

```bash
cd /home/andrew/projects/system-dictation-feedback
./install.sh
./bin/dictation
```

The installer creates a desktop-login autostart entry. After subsequent boots, the tray listener starts when you sign into Cinnamon. The model stays unloaded until the first dictation. You do not need a root/system service: microphone, tray and focused-cursor access belong to the desktop session.

This checkout is separate from the original working app, so preparing the update does not reload or restart it. Installation repoints the login launcher to this directory. Keep this directory while its startup entry is enabled. Configuration and the existing model cache are preserved; history starts empty in the new session.

Place the cursor in a text field and click **Back thumb / mouse button 8**. Recording begins immediately while the model loads in parallel. The red mic icon glows brighter and its small level bars rise with microphone intensity. A dim icon with **No mic input; check mute** after two seconds means little or no sound is reaching the app. This measures incoming audio, not the physical mute switch or whether words are intelligible. Click Back again to stop; amber means transcribing. Keep the target focused until text is pasted.

**Front thumb / Forward / mouse button 9** pastes the selected completed transcript at your current cursor, even if automatic insertion went into a non-editable area. It works when idle or showing an error; presses while recording/transcribing are ignored. The app consumes both thumb buttons while running, so neither navigates the browser. Quit restores normal Back and Forward.

GPU 0 is preferred when at least 3 GiB of VRAM is free. CUDA uses int8/float16; CPU uses int8, with 12 threads. Low free VRAM, CUDA initialization errors, allocation failures or a GPU worker crash trigger CPU processing of the same recording. The model remains warm for 120 seconds after use, then the subprocess exits and releases its memory. Recording automatically stops at 180 seconds. Extra presses during transcription are ignored.

Tray menu: Start/Stop, Cancel recording, Paste selected transcript, Recent transcripts (last 5), Copy selected transcript, How to use / Practice, Sound cues, Unload model now and Quit. **Recent transcripts** opens a chooser with five newest-first rows and a full preview. Select a row, close the chooser, focus your destination and click Forward to paste it. A new successful transcription selects the newest row automatically; an empty/failed recording leaves existing history intact. Results whose automatic insertion was blocked are included. This cache stays in memory only and clears on Quit/restart.

Changing focus while transcription runs prevents automatic paste into the new window. The tray paste action acts on the field focused after the menu closes. Keyboard modifiers must be released before pasting. Paste/copy actions use the selected transcript, rather than whatever another program last put on the clipboard.

Text insertion uses the clipboard and Shift+Insert, so it supports normal editable fields, browsers and Linux terminals without pressing Enter. **Dictation replaces both clipboard and primary selection.** Applications that block paste, password/secure fields, games, remote-desktop targets and Wayland are outside the supported scope. The insertion cursor stays under the application's control; do not switch input fields while transcription runs. A different field in the same X11 window cannot always be distinguished.

Configuration: `~/.config/system-dictation/config.json`. Change it while the app is stopped. `button`, `paste_button`, `idle_seconds`, `gpu_min_free_mb`, `language`, `sound`, and other defaults are readable there. Old configurations gain Forward button 9 by default; if recording was already assigned to 9, paste defaults to 8. Empty language enables automatic language detection. The medium model is reused from Tessera's existing cache when available; otherwise setup downloads it once. GPU libraries are private Python dependencies, so no host NVIDIA driver or system CUDA installation is modified. The worker uses cached files only and disables Hugging Face network/telemetry. Audio is a mode-0600 temporary WAV, deleted after processing; transcripts are not logged or written to disk.

To disable: Quit from the tray, then `./uninstall.sh`. It removes startup and the launcher, preserving configuration/source/model files. Cinnamon's Startup Applications can also disable the entry. Do not move/delete this project directory while its autostart entry is enabled.

Verification and material limitations are recorded in `VERIFICATION.md`. This project does not provide voice commands or stream partial words.
