# Verification — 2026-10-12

Implementation is local to this project. Old Tessera remains unchanged. Its donor path is `scripts/local-whisper-stt.py` and the `/api/stt` local-Whisper branch: faster-whisper, cached medium model, beam size 5, VAD, CPU int8 and CUDA error fallback.

Fresh read-only hardware inspection confirmed Intel i7-13700K / 24 threads, 62 GiB RAM, RTX 3080 / 10240 MiB VRAM / compute capability 8.6, NVIDIA driver 595.99.02 and Linux kernel 7.0.0-38-generic. Transient utilization was not promoted to a durable hardware specification.

## Model and lifecycle evidence

The public OpenAI Whisper `tests/jfk.flac` fixture is 11.0 seconds. With this project's locked environment and existing Tessera model cache, the actual RTX 3080 CUDA worker correctly transcribed the expected phrase in 2.75 seconds including worker startup. Free VRAM was 8993 MiB before, 7759 MiB with the model loaded, and 8993 MiB after worker exit. A configured admission threshold above available VRAM selected CPU and correctly transcribed the same file in 4.07 seconds. These are single-fixture observations, not general speed guarantees. Both were headless project-native checks; no host window/app/listener was started.

Fifteen targeted tests pass. They exercise GPU admission, initialization/inference failure, GPU process crash, retry/reuse/reaping, shutdown refusal, private WAV permissions, immediate capture, cancellation, overflow rejection, bounded recording memory, idle-unload callbacks during active work, and changed focus during clipboard preparation. Reproduce with `uv run --no-sync python -m pytest tests -q`.

The locked PyAV version is 16.0.1 because faster-whisper 1.2.1 still passes an argument removed in PyAV 19. The failure was reproduced during real transcription and then repaired. Upstream evidence: [faster-whisper issue 1589](https://github.com/SYSTRAN/faster-whisper/issues/1589).

## OS evidence

Disposable `mint-worker`, instance `lab-mint-worker-04`, 4096 MiB, Linux Mint 22.3 Cinnamon X11. `sudo -n true` verified guest administrator authority. All visuals stayed in the private VM GUI harness. Public fixture audio only; no user credentials or private recordings copied.

Actual installer passed with locked dependencies and a local model directory. Generated desktop-login autostart entry was exercised by a full VM reboot: boot ID changed from `64379c5a-6e29-447f-8bc6-609d73e1f62f` to `88a5c7d1-c888-4694-a262-f4c6f2830679`; the listener started automatically, used 49220 KiB RSS and had no Whisper worker before the first recording. The installed launcher symlink resolved correctly; a second launch was rejected without disturbing the first listener.

The VM fixture uses a Pulse/PipeWire null sink plus a proper remapped virtual microphone, selected as the OS default. Direct FLAC playback through this VM's paplay produced incorrectly timed audio (1.878 seconds for an 11-second file), so initial source-blind no-speech failures were invalid harness evidence. Decoding it to mono 16 kHz PCM WAV repaired the fixture: playback 11.058 seconds, captured 209208 frames, actual Recorder+Whisper output matched the expected speech. The app's recording format was already PCM WAV.

Independent source-blind reports and screenshots are retained under `evidence/source-blind/`. The original failed run remains for audit. Final runtime candidate is `b019593d05dfbabbfb6a02884a980c004a46b1d8`; [final source-blind report](/home/andrew/projects/system-dictation/evidence/source-blind/REPORT-b019593.md) is PASS for the tested Mint Cinnamon X11 workflow scope, with no reproducible defect remaining. Coverage combines the full preceding run and final focused checks: native practice and Firefox dictation, consuming Back instead of navigating, ignoring extra presses during processing, cancellation and reuse, changed-focus prevention, last-result recovery into xed and terminal, Copy recovery, and terminal insertion without Enter/submission. Fresh/existing/hidden/minimized practice-guide foreground behavior was repeated successfully. Fifteen tests passed in the actual final VM environment too.

## Removal and cleanup

The original combined cleanup command returned a failure without its full output, and the first disposable overlay was released before that result was inspected. Removal was therefore verified again in a fresh admin-verified 4096 MiB Mint worker (reused instance name `lab-mint-worker-04`, new lease `140f311df44644198ecddb80498de1b2`), using only copied public dependencies/model files. Actual install created the launcher and startup entry; actual uninstall removed both. Full SHA-256 comparisons confirmed configuration and model contents were preserved, source remained and no dictation process was running. [Removal proof](/home/andrew/projects/system-dictation/evidence/qualification/uninstall-proof.log). The retained `qa/verify-uninstall.sh` refuses physical-host execution.

First lease `f649235a8a56406da7d9663df8a06a90` was released, its private GUI harness stopped and disposable overlay removed. Second lease `140f311df44644198ecddb80498de1b2` was also released and its disposable overlay removed after the successful removal proof was exported. Screenshots, source-blind reports, runtime log and removal proof are exported to this project's `evidence/`; original model files and live desktop settings remain untouched. Duplicate public dependency/model transfer archives were cleaned up; the ready project environment and small public audio fixture remain.

## Supported scope and limits

Mint Cinnamon X11 ordinary editable fields are the supported surface. GPU computation was checked on the real RTX 3080; OS input/tray/audio/paste were checked in the VM. Physical mouse mapping, Andrew's microphone/acoustics, speaker sound cues and applications outside the tested fields still require first use on his desktop. Wayland, Windows/macOS, applications that block paste, secure/password fields and remote desktop/game input are excluded.

Insertion replaces the clipboard and primary selection. Changed X11 focus protects against pasting into a different window; a different field in the same browser window may share the same X11 focus identity, so keep the desired field focused while processing. Audio is removed after processing; the result stays in memory and clipboard for recovery. The host listener/autostart entry is not activated by the agent under Andrew's host-protection instructions. Activation instructions are in README.md.
