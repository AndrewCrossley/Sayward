# Sayward — Windows installer and Linux parity

Status: qualified, release publication pending, 2026-10-24. Private repository: AndrewCrossley/Sayward. Original installations stay untouched.

Goal: Andrew can install Sayward on Windows and use the private local dictation workflow already available on Mint X11.

Done when:
1. The dedicated private repository retains standalone dictation history and documents the name check.
2. Windows x64 has a standalone per-user installer, Start-menu entry, optional login startup, model setup and uninstall. Python is bundled; model/config are retained on uninstall.
3. Both OSs support Back recording toggle, immediate capture, input feedback/silence warning, guarded automatic insertion, Forward recovery, five-result session history, practice/help, cancel, unload and Quit.
4. Shared offline workers retain GPU admission, CUDA failure-to-CPU retry and idle unloading. Windows uses CUDA when compatible CUDA/cuDNN libraries exist, otherwise CPU. Audio is temporary and history is memory-only.
5. Meaningful engine/controller tests pass; real Windows installer and Mint workflows are exercised in admin-verified VMs. Artifacts, recovery instructions and limits are published.

Excluded: cloud assistant, punctuation/spacing changes, Tessera migration, macOS, Wayland, ARM Windows, signing-certificate purchases, arbitrary elevated/secure targets. Windows 10/11 x64 and Mint Cinnamon X11 were exercised; Windows NVIDIA hardware remains explicitly untested.

Proof: protocol/controller regressions; native input/clipboard tests; installer install/launch/startup/uninstall; browser/native/terminal transcription and recovery; level feedback; cancel/restart/model setup error recovery. No host GUI or installed-app changes.
