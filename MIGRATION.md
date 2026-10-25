# Platform inventory and compatibility

Linux GTK/X11 stays in place. Windows gets Win32 mouse/clipboard/focus handling and Tk/pystray presentation. A shared Session owns recording/transcription/recovery state; both presentations use the same audio/model/history authority.

Graphify inventories are in ignored evidence/graph-*.txt, with no truncation. Engine._reply callers: Engine._start, Engine._transcribe, test FixtureEngine._start. Engine._start callers: prepare and transcribe. Config consumers include startup, worker and fixtures. App operation callers are tray actions, poll, tick, practice Start/Stop, executor callbacks and quit. These operations move together into Session. GTK rendering/history/help stay intentional Linux presentation.

| Concern | Linux | Windows | Authority |
| --- | --- | --- | --- |
| Audio/model/history/lifecycle | retained | shared | core.py and session.py |
| Worker transport | queue-backed pipes | queue-backed pipes | Engine; Windows selectors cannot wait on pipes |
| Worker launch | Python module | frozen worker dispatch or Python module | worker_command and launcher |
| Mouse/focus/paste | X11 retained | Win32 hook and Unicode clipboard | OS Desktop adapter |
| Levels/tray/help | GTK | Tk and native tray | presentation |
| Config/cache | existing system-dictation locations | LOCALAPPDATA/Sayward | paths.py |
| Singleton | existing flock | named mutex | startup |
| Parent exit | Linux death signal | Windows kill-on-close Job Object | worker lifecycle |
| Install/startup | shell/desktop login | frozen executable/Inno Setup | installers |

Existing Linux settings/cache/lock intentionally remain compatible. Windows has no prior state to migrate. History is session-only. Frozen worker dispatch happens before GUI startup. Supported states include first launch, recording/working/error, cancel/retry, silence, changed focus, selected history, rapid presses, unload, Quit/relaunch, install/uninstall and available DPI scales. Negative checks prevent Enter/submission, changed-focus insertion, duplicate listeners, worker restart during shutdown and network inference.
