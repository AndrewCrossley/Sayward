# Sayward

Private mouse-toggle dictation for **Windows x64** and **Linux Mint Cinnamon X11**. Speech recognition runs locally with faster-whisper. Press Back to start recording, press it again to stop and transcribe, and use Forward to recover a completed transcript.

Punctuation is required for ordinary prose. Release 0.3.0 adds fully local punctuation restoration before history or insertion, with word-preservation validation and one trailing separating space for prose. Windows 10 and Mint workflows passed native qualification; Windows 11 model setup passed, with full 0.3.0 audio qualification still incomplete. See `GOAL.md` for current status.

## Windows installer

Download [Sayward 0.3.0 for Windows x64](https://github.com/AndrewCrossley/Sayward/releases/tag/v0.3.0) from this private repository's Releases page. Run it for your user account; Python is included. The optional installer checkbox starts Sayward when you sign in. Open Sayward from the Start menu. The microphone tray icon may appear inside Windows' hidden-icons arrow; drag it into view if desired. Use the tray's practice guide for a first recording. If input stays silent, check the OS default microphone, mute and microphone permissions.

First launch opens **Model setup**. Choose a model and click **Download selected model**, or choose an existing faster-whisper model folder. Medium (~1.5 GB) is the original quality setting; smaller models are faster on CPU. Setup downloads public model files from Hugging Face. No Hugging Face account is required. Punctuation setup then downloads its separate local model (~300 MB). Both setup dialogs can be reopened from the tray. Once installed, recognition and punctuation need no internet; audio/text are never sent to a service.

The installer is unsigned, so Windows may show an unknown-publisher/SmartScreen warning. Published installers have SHA-256 checksums. No driver, system CUDA installation, browser extension or cloud account is installed.

Configuration and downloaded models live in `%LOCALAPPDATA%\Sayward`. Uninstall through Windows Settings or the Start-menu uninstall entry; login startup and installed program files are removed, while configuration/model downloads are retained.

Release 0.3.0 ordinary-user dictation, punctuation, Copy/Forward recovery and Quit/relaunch passed on Windows 10 x64 in an admin-verified VM. Windows 11 final model download/setup passed, but its new audio workflow remains unqualified; see VERIFICATION.md. Historical 0.2.0 lifecycle evidence is retained separately. ARM Windows, secure desktops and elevated/password fields are unsupported. Run Sayward as an ordinary user; it does not elevate to type into protected apps.

## Linux

Install `uv` and the desktop prerequisites: Python 3 GI/GTK3, Ayatana AppIndicator3, libportaudio2 and Pulse/PipeWire `paplay`. In this checkout run:

```bash
./install.sh
./bin/dictation
```

If the original System Dictation is running, deliberately Quit it from its tray before switching. Agents do not restart Andrew's installed copy. The installer explicitly sets up the punctuation weights (~300 MB on first install), then retains the original `system-dictation` configuration/cache/lock and startup filename for compatibility, avoiding duplicate listeners. It also installs the `sayward` launcher. Keep this source directory while login startup points to it.

On an NVIDIA system the Linux installer adds private CUDA/cuDNN Python packages; CPU-only installs avoid those downloads. Windows uses compatible [NVIDIA CUDA 12/cuDNN 9 libraries](https://github.com/SYSTRAN/faster-whisper/blob/v1.2.1/README.md#gpu) when already installed and available in the DLL search path, otherwise CPU automatically. No system driver is changed. GPU admission requires 3 GiB free VRAM; low memory or CUDA initialization/inference failure retries the same recording on CPU. Models unload after 120 seconds idle.

## Everyday use

1. Focus an ordinary text field. Click rear thumb / Back (logical button 8), then speak. Capture starts immediately while the model loads in parallel.
2. The red mic glows with incoming audio intensity. Sustained silence shows **No mic input; check mute**. This measures audio, not the physical mute switch or intelligible speech.
3. Click Back again. Amber means transcribing; keep the target focused until insertion completes. Extra presses while working are ignored.
4. Front thumb / Forward (button 9) pastes the selected completed transcript again. Both buttons are consumed while Sayward runs; Quit restores browser navigation.
5. Tray → **Recent transcripts (last 5)** shows newest-first history and a full preview. Select an older item, close history, focus a destination and press Forward. Selection alone never pastes. New results select the newest item. Failed automatic insertion still retains its result; empty/error recordings leave prior history intact.

Completed prose gets punctuation and conservative sentence casing while its words, numbers and identifiers are preserved. History shows clean text; automatic insertion, Copy and Forward add one trailing ASCII space so two new dictations do not join together. Recognizable literal JSON, code/calls, commands with flags, paths and bare links remain as recognized without an extra separator. Inline code stays intact; a final bare link in prose may be quoted to keep the sentence mark outside its address. This does not inspect text around your cursor or repair old text already in the field.

If punctuation fails, unprocessed dictation stays in memory and is not automatically pasted. Open **Punctuation setup** to download/repair files, then choose **Retry punctuation for saved dictation**. Tray Retry completes it into history; focus the destination and press Forward. Back/the practice button can instead retry into the current field. Forward continues to paste selected completed history. **Discard saved unprocessed dictation** clears the failed attempt; Quit clears all session memory. Silence adds no punctuation or history entry.

Tray → **How to use / Practice** offers a highlighted Start/Stop button and a real practice field. Close and revisit it at any time. On Windows, Alt+R in the practice guide also toggles capture. Windows additionally offers **Model setup** for revisiting downloads or choosing a model folder. Cancel, Copy, Unload model and Quit are available through the tray.

History lives only in memory and clears on Quit/restart. Audio is a temporary recording deleted after processing. No transcript is logged. Dictation replaces the clipboard (and Linux primary selection). Insertion does not send Enter. Avoid multi-line commands in terminals: terminals may interpret pasted newlines. Windows uses Ctrl+V; Linux uses Shift+Insert.

On Windows, focus the destination and press Forward for recovery; the tray offers a shortcut hint and Copy selected transcript. Windows tray menus take focus, so they do not offer a separate Paste action. Linux retains its delayed tray Paste action.

A changed native window/control focus prevents automatic insertion; recover with Forward. Different fields within one browser/native window cannot always be distinguished, so keep the intended field focused. Applications that block clipboard insertion, games, remote desktops, Wayland and arbitrary secure fields are outside scope.

## Development

Linux: `uv sync` (add `--extra gpu` for private NVIDIA libraries), then `uv run --no-sync python -m pytest tests -q`. GUI/OS qualification uses isolated VMs.

Windows: install Python 3.12 including Tcl/Tk, uv and Inno Setup 6; run `packaging/build-windows.ps1`. PyInstaller builds a windowed GUI plus a console worker, sharing one runtime directory. The worker runs hidden with redirected pipes, isolated by a kill-on-close Windows Job Object. Output is `dist/installer/Sayward-Setup-0.3.0-x64.exe`. The frozen package bundles its MSVC runtime DLLs; a source-only Python environment needs the corresponding runtime dependencies in its DLL search path. In a disposable interactive Windows VM, set `SAYWARD_NATIVE_TESTS=1` to include real Win32 clipboard/hook/singleton tests.

CI builds installer candidates as draft Releases; qualification is required before publishing a release. See `GOAL.md`, `MIGRATION.md`, `NAME-CHECK.md`, `VERIFICATION.md` and `qa/regressions.json`. Original standalone Git history is retained; the old Tessera preservation checkpoint remains separate. AI-assistant/cloud integration remains outside scope. Release 0.2.0 predates the current required-punctuation milestone.

Punctuation uses pinned, integrity-checked Horizon-Labs ONNX files on CPU through the existing runtime. Inferred punctuation can still need manual editing for ambiguous language. Changed wording is rejected. Set `SAYWARD_PUNCTUATION_MODEL` to verified local weights for the offline model corpus test.
