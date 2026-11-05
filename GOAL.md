# Sayward — optional mouse submission

Status: active, 2026-11-04. Public visibility and the Linux native workflow are verified; Windows native qualification remains required. Andrew authorized making the existing repository public and double-clicking the Back thumb recording-stop button within 0.75 seconds to paste and press Enter, on Windows and Linux.

Goal: Andrew can publish/use Sayward independently and deliberately submit a dictation from the mouse, without changing ordinary paste/recovery behavior.

Done when:
1. Public repository retains existing Git history and releases after checking tracked history/release evidence for private data and credentials.
2. One stop click still pastes without Enter. A second Back thumb stop click within 0.75 seconds requests exactly one Enter for that recording; it never starts another capture. Recognition/punctuation continue immediately; exceptionally fast results wait only for the gesture window.
3. Enter follows validated punctuation and paste, with target/modifier checks repeated after clipboard delivery. Silence, failed processing/paste, changed focus, auto-stop, retries and Quit cannot leak an Enter request into another result. Forward stays paste-only.
4. Deterministic timing/error regressions and native Windows/Linux mouse/form workflows prove the behavior and visible feedback. Updated guide and installer explain the gesture; GUI/tray Start/Stop stays paste-only.

Excluded: cloud assistant, new mouse bindings, general rewriting, arbitrary editor-context capture and a configurable gesture system. No host installed app/service changes.

Proof: public GitHub metadata and local credential-signature/entropy scan; shared-session timing/failure tests; OS-boundary guards; disposable native form records text and Enter counts through real thumb events, plus recovery/Quit checks. Runtime-visible behavior needs isolated OS guests; ordinary source tests do not need to launch the app.

---

# Completed milestone — required punctuation

Status: complete / frozen, 2026-11-04. Release: https://github.com/AndrewCrossley/Sayward/releases/tag/v0.3.0. Andrew approved the fully local punctuation-only pass and narrow separator rule, with wording preserved on Windows and Linux. Design: PUNCTUATION-PLAN.md.

Goal: Andrew can dictate ordinary English prose and receive consistently punctuated text, including sentence boundaries and question marks, while speech and text processing remain local.

Done when:
1. A deliberately unpunctuated prose transcript gains appropriate sentence punctuation, including internal sentence boundaries; existing correct punctuation is retained without duplicate marks.
2. Processing preserves spoken wording, names, numbers, contractions and technical strings; it adds punctuation and permitted sentence casing rather than paraphrasing.
3. Automatic insertion, history, Copy and Forward recovery use the same completed result. Silent input stays empty; failed cleanup preserves recoverable text and clearly reports the failure instead of silently inserting an unprocessed result.
4. Short/long prose, statements/questions, consecutive recordings, existing punctuation, decimal values and protected strings have meaningful regressions. The agreed insertion-spacing rule is exercised separately from punctuation quality.
5. Offline operation and acceptable cleanup latency are demonstrated on CPU; real Windows and Mint workflows and the Windows installer are qualified before a new release is recommended.

Excluded: cloud processing, assistant/tool integration, general rewriting or spelling correction, arbitrary reading of surrounding editor contents, multilingual punctuation expansion and repository visibility changes. A standalone additional punctuation model must be disclosed during setup; no automatic upload of speech or text.

Proof: a before/after text corpus plus the existing generated-speech/virtual-microphone workflow, through native/browser text fields and Forward/history recovery. All five acceptance conditions are demonstrated on Windows 10 and Mint; the final runtime passed 83 tests with 11 Windows-only skips, real offline model corpus, independent source review and native installer/dictation/recovery/lifecycle checks. VERIFICATION.md records exact evidence and the nonblocking Windows 11 audio-qualification gap. Verified installer, checksums and qualification evidence are delivered in the 0.3.0 release. Host activation remains user-controlled.

Punctuation-free normal prose is a defect, not an accepted preference. Earlier punctuation deferrals apply only to the historical release below and do not override this requirement.

## Completed milestone — Windows installer and Linux parity

Status: complete / frozen, 2026-10-24. Published release: https://github.com/AndrewCrossley/Sayward/releases/tag/v0.2.0. Private repository: AndrewCrossley/Sayward. Original installations stay untouched.

Goal: Andrew can install Sayward on Windows and use the private local dictation workflow already available on Mint X11.

Done when:
1. The dedicated private repository retains standalone dictation history and documents the name check.
2. Windows x64 has a standalone per-user installer, Start-menu entry, optional login startup, model setup and uninstall. Python is bundled; model/config are retained on uninstall.
3. Both OSs support Back recording toggle, immediate capture, input feedback/silence warning, guarded automatic insertion, Forward recovery, five-result session history, practice/help, cancel, unload and Quit.
4. Shared offline workers retain GPU admission, CUDA failure-to-CPU retry and idle unloading. Windows uses CUDA when compatible CUDA/cuDNN libraries exist, otherwise CPU. Audio is temporary and history is memory-only.
5. Meaningful engine/controller tests pass; real Windows installer and Mint workflows are exercised in admin-verified VMs. Artifacts, recovery instructions and limits are published.

Excluded from release 0.2.0: cloud assistant, punctuation/spacing implementation, Tessera migration, macOS, Wayland, ARM Windows, signing-certificate purchases, arbitrary elevated/secure targets. This historical scope is superseded for punctuation by the active milestone above. Windows 10/11 x64 and Mint Cinnamon X11 were exercised; Windows NVIDIA hardware remains explicitly untested.

Proof: protocol/controller regressions; native input/clipboard tests; installer install/launch/startup/uninstall; browser/native/terminal transcription and recovery; level feedback; cancel/restart/model setup error recovery. No host GUI or installed-app changes.

Acceptance proof: standalone history retained; final per-user Windows installer and native CPU workflows qualified on Windows 10/11; Mint recording/recovery/install/reboot parity passed; common engine and real Linux CUDA/CPU fixture checks passed; release installer, checksums, qualification archive and recovery documentation published. All test leases released. Unsigned installer, actual Windows CUDA hardware and physical-device/sound audition are nonblocking documented limits.
