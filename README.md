# Sayward

Private mouse-toggle dictation for **Windows x64** and **Linux Mint Cinnamon X11**. Speech recognition runs locally with faster-whisper. Press Back to start recording, press it again to stop and transcribe, and use Forward to recover a completed transcript.

Punctuation is required for ordinary prose. Version 0.2.0 currently passes through the recognition model's punctuation, which can be inconsistent; this is the active defect tracked in `GOAL.md`. The proposed local correction is in `PUNCTUATION-PLAN.md` and awaits agreement before runtime changes.

## Windows installer

Download [Sayward 0.2.0 for Windows x64](https://github.com/AndrewCrossley/Sayward/releases/tag/v0.2.0) from this private repository's Releases page. Run it for your user account; Python is included. The optional installer checkbox starts Sayward when you sign in. Open Sayward from the Start menu. The microphone tray icon may appear inside Windows' hidden-icons arrow; drag it into view if desired. Use the tray's practice guide for a first recording. If input stays silent, check the OS default microphone, mute and microphone permissions.

First launch opens **Model setup**. Choose a model and click **Download selected model**, or choose an existing faster-whisper model folder. Medium (~1.5 GB) is the original quality setting; smaller models are faster on CPU. Setup downloads public model files from Hugging Face. No Hugging Face account is required. After setup, recording/transcription need no internet and audio is never sent to a service.

The installer is unsigned, so Windows may show an unknown-publisher/SmartScreen warning. Published installers have SHA-256 checksums. No driver, system CUDA installation, browser extension or cloud account is installed.

Configuration and downloaded models live in `%LOCALAPPDATA%\Sayward`. Uninstall through Windows Settings or the Start-menu uninstall entry; login startup and installed program files are removed, while configuration/model downloads are retained.

Windows 11 and Windows 10 x64 were exercised in clean, admin-verified VMs, including ordinary-user dictation, recovery and installer lifecycle. ARM Windows, secure desktops and elevated/password fields are unsupported. Run Sayward as an ordinary user; it does not elevate to type into protected apps.

## Linux

Install `uv` and the desktop prerequisites: Python 3 GI/GTK3, Ayatana AppIndicator3, libportaudio2 and Pulse/PipeWire `paplay`. In this checkout run:

```bash
./install.sh
./bin/dictation
```

If the original System Dictation is running, deliberately Quit it from its tray before switching. Agents do not restart Andrew's installed copy. The installer retains the original `system-dictation` configuration/cache/lock and startup filename for compatibility, avoiding duplicate listeners. It also installs the `sayward` launcher. Keep this source directory while login startup points to it.

On an NVIDIA system the Linux installer adds private CUDA/cuDNN Python packages; CPU-only installs avoid those downloads. Windows uses compatible [NVIDIA CUDA 12/cuDNN 9 libraries](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/README.md#gpu) when already installed and available in the DLL search path, otherwise CPU automatically. No system driver is changed. GPU admission requires 3 GiB free VRAM; low memory or CUDA initialization/inference failure retries the same recording on CPU. Models unload after 120 seconds idle.

## Everyday use

1. Focus an ordinary text field. Click rear thumb / Back (logical button 8), then speak. Capture starts immediately while the model loads in parallel.
2. The red mic glows with incoming audio intensity. Sustained silence shows **No mic input; check mute**. This measures audio, not the physical mute switch or intelligible speech.
3. Click Back again. Amber means transcribing; keep the target focused until insertion completes. Extra presses while working are ignored.
4. Front thumb / Forward (button 9) pastes the selected completed transcript again. Both buttons are consumed while Sayward runs; Quit restores browser navigation.
5. Tray → **Recent transcripts (last 5)** shows newest-first history and a full preview. Select an older item, close history, focus a destination and press Forward. Selection alone never pastes. New results select the newest item. Failed automatic insertion still retains its result; empty/error recordings leave prior history intact.

Tray → **How to use / Practice** offers a highlighted Start/Stop button and a real practice field. Close and revisit it at any time. On Windows, Alt+R in the practice guide also toggles capture. Windows additionally offers **Model setup** for revisiting downloads or choosing a model folder. Cancel, Copy, Unload model and Quit are available through the tray.

History lives only in memory and clears on Quit/restart. Audio is a temporary recording deleted after processing. No transcript is logged. Dictation replaces the clipboard (and Linux primary selection). Insertion does not send Enter. Avoid multi-line commands in terminals: terminals may interpret pasted newlines. Windows uses Ctrl+V; Linux uses Shift+Insert.

On Windows, focus the destination and press Forward for recovery; the tray offers a shortcut hint and Copy selected transcript. Windows tray menus take focus, so they do not offer a separate Paste action. Linux retains its delayed tray Paste action.

A changed native window/control focus prevents automatic insertion; recover with Forward. Different fields within one browser/native window cannot always be distinguished, so keep the intended field focused. Applications that block clipboard insertion, games, remote desktops, Wayland and arbitrary secure fields are outside scope.

## Development

Linux: `uv sync` (add `--extra gpu` for private NVIDIA libraries), then `uv run --no-sync python -m pytest tests -q`. GUI/OS qualification uses isolated VMs.

Windows: install Python 3.12 including Tcl/Tk, uv and Inno Setup 6; run `packaging/build-windows.ps1`. PyInstaller builds a windowed GUI plus a console worker, sharing one runtime directory. The worker runs hidden with redirected pipes, isolated by a kill-on-close Windows Job Object. Output is `dist/installer/Sayward-Setup-0.2.0-x64.exe`. The frozen package bundles its MSVC runtime DLLs; a source-only Python environment needs the corresponding runtime dependencies in its DLL search path. In a disposable interactive Windows VM, set `SAYWARD_NATIVE_TESTS=1` to include real Win32 clipboard/hook/singleton tests.

CI builds installer candidates as draft Releases; qualification is required before publishing a release. See `GOAL.md`, `MIGRATION.md`, `NAME-CHECK.md`, `VERIFICATION.md` and `qa/regressions.json`. Original standalone Git history is retained; the old Tessera preservation checkpoint remains separate. AI-assistant/cloud integration remains outside scope. Release 0.2.0 predates the current required-punctuation milestone.
