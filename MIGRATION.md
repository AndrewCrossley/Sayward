# Platform inventory and compatibility

Linux GTK/X11 stays in place. Windows gets Win32 mouse/clipboard/focus handling and Tk/pystray presentation. A shared Session owns recording/transcription/recovery state; both presentations use the same audio/model/history authority.

Graphify inventories are in ignored evidence/graph-*.txt, with no truncation. Engine._reply callers: Engine._start, Engine._transcribe, test FixtureEngine._start. Engine._start callers: prepare and transcribe. Config consumers include startup, worker and fixtures. App operation callers are tray actions, poll, tick, practice Start/Stop, executor callbacks and quit. These operations move together into Session. GTK rendering/history/help stay intentional Linux presentation.

| Concern | Linux | Windows | Authority |
| --- | --- | --- | --- |
| Audio/model/history/lifecycle | retained | shared | core.py and session.py |
| Worker transport | queue-backed pipes | queue-backed pipes | Engine; Windows selectors cannot wait on pipes |
| Worker launch | Python module | frozen worker dispatch or Python module | Engine._start and launcher |
| Mouse/focus/paste | X11 retained | Win32 hook and Unicode clipboard | OS Desktop adapter |
| Levels/tray/help | GTK | Tk and native tray | presentation |
| Config/cache | existing system-dictation locations | LOCALAPPDATA/Sayward | paths.py |
| Singleton | existing flock | named mutex | startup |
| Parent exit | Linux death signal | Windows kill-on-close Job Object | worker lifecycle |
| Install/startup | shell/desktop login | frozen executable/Inno Setup | installers |

Existing Linux settings/cache/lock intentionally remain compatible. Windows has no prior state to migrate. History is session-only. Frozen worker dispatch happens before GUI startup. Supported states include first launch, recording/working/error, cancel/retry, silence, changed focus, selected history, rapid presses, unload, Quit/relaunch, install/uninstall and available DPI scales. Negative checks prevent unrequested Enter/submission, changed-focus insertion, duplicate listeners, worker restart during shutdown and network inference.

Windows tray recovery intentionally uses Forward after focusing the destination, or Copy selected transcript. A tray Paste action was removed after native testing showed the menu can keep focus on its hidden owner rather than the editor. Linux keeps its existing delayed tray-paste behavior. This avoids adding automatic foreground restoration or guessing which previous field should receive text.

Punctuation milestone (2026-11-03): Session.finished now retains raw recognition in a single session-only pending slot; Punctuator.restore runs off the UI thread and validates unchanged wording before Session.punctuated can commit history or paste. Both views share these callbacks and insertion_text. History remains clean; prose Copy/automatic/Forward insertion adds one trailing space, while recognizable literal code/links/paths stay verbatim. Failed processing leaves previous history/selection intact. Back or explicit Retry handles pending dictation; tray Retry only creates a completed result, requiring the user to focus the destination and press Forward. Discard and Quit clear pending memory. No raw transcript is serialized or logged.

Both frontends expose Punctuation setup, Retry and Discard; existing help is updated. Config gains a backward-compatible punctuation_dir default outside the Linux speech-cache symlink. The pinned ONNX model is CPU-only, loaded lazily and released with the shared model-unload/shutdown path. Only explicit setup/install can download public weights; runtime accepts verified local files. Cross-process OS locking protects atomic model installation and safe removal of partial files left by an interrupted setup. Old direct-raw-to-history/paste completion is retired in both frontends; no cloud/assistant path is introduced.

Optional submission (2026-11-04): Back mouse events carry original OS timestamps through both adapters into Session. A second stop press within 0.75 seconds requests one guarded Enter after completed paste. Single stop, GUI/tray Start/Stop and Forward remain paste-only. A separate short stop-click consumption guard survives fast silence/errors so a second stop cannot accidentally start a new capture. Queued input is drained before completion delivery; focus/modifiers are checked again after clipboard delivery and before Enter. No persisted preference or alternate history authority is introduced. Existing configuration, local models, recovery, and clipboard behavior remain compatible.
