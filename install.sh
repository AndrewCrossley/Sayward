#!/bin/bash
# Run deliberately by the desktop owner. The agent tests this only in the VM.
set -euo pipefail
dictation_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$dictation_root"
command -v uv >/dev/null || { echo 'uv is required.' >&2; exit 1; }
/usr/bin/python3 -c 'import gi; gi.require_version("Gtk", "3.0"); gi.require_version("AyatanaAppIndicator3", "0.1"); from gi.repository import Gtk, AyatanaAppIndicator3' || {
    echo 'Missing desktop packages: python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 libportaudio2. Install them before retrying.' >&2
    exit 1
}
if [[ ! -d .venv ]]; then uv venv --python /usr/bin/python3 --system-site-packages; fi
if command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name --format=csv,noheader >/dev/null 2>&1; then
    uv sync --frozen --extra gpu --python /usr/bin/python3
else
    uv sync --frozen --python /usr/bin/python3
fi
mkdir -p "$HOME/.config/system-dictation" "$HOME/.cache/system-dictation" "$HOME/.config/autostart" "$HOME/.local/bin"
if [[ ! -e "$HOME/.cache/system-dictation/models" ]]; then
    if [[ -d "$HOME/projects/tessera/.whisper-cache/models--Systran--faster-whisper-medium" ]]; then
        ln -s "$HOME/projects/tessera/.whisper-cache" "$HOME/.cache/system-dictation/models"
    else
        mkdir -p "$HOME/.cache/system-dictation/models"
    fi
fi
if [[ ! -e "$HOME/.config/system-dictation/config.json" ]]; then
    .venv/bin/python -c 'from dictation.core import Config; import json; from pathlib import Path; p=Path.home()/".config/system-dictation/config.json"; p.write_text(json.dumps(Config().__dict__, indent=2)+"\n"); p.chmod(0o600)'
fi
# Reuse the existing cached revision; download only if setup needs weights.
.venv/bin/python - <<'PY'
from dictation.core import Config
from huggingface_hub import snapshot_download
from huggingface_hub.errors import LocalEntryNotFoundError
from pathlib import Path
c = Config.load(Path.home()/'.config/system-dictation/config.json')
if not Path(c.model).is_dir():
    args = dict(repo_id='Systran/faster-whisper-'+c.model, cache_dir=c.cache_dir,
                allow_patterns=['config.json','model.bin','tokenizer.json','vocabulary.*'])
    try:
        cached = Path(snapshot_download(**args, local_files_only=True))
        if not all((cached/name).is_file() for name in ['config.json','model.bin','tokenizer.json']):
            raise LocalEntryNotFoundError('Model cache is incomplete')
    except LocalEntryNotFoundError:
        snapshot_download(**args)
PY
chmod +x bin/dictation
ln -sfn "$dictation_root/bin/dictation" "$HOME/.local/bin/system-dictation"
ln -sfn "$dictation_root/bin/dictation" "$HOME/.local/bin/sayward"
DICTATION_INSTALL_ROOT="$dictation_root" .venv/bin/python - <<'PY'
import os
from pathlib import Path
root = os.environ['DICTATION_INSTALL_ROOT']
if any(c in root for c in '\n\r'):
    raise SystemExit('Unsupported install path')
escaped = (root + '/bin/dictation').replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
content = '[Desktop Entry]\nType=Application\nName=System Dictation\nComment=Back thumb button toggles private local dictation\nExec="'+escaped+'"\nTerminal=false\nX-GNOME-Autostart-enabled=true\nX-GNOME-Autostart-Delay=5\n'
(Path.home()/'.config/autostart/system-dictation.desktop').write_text(content)
PY
echo 'Installed. Starts at desktop login (after reboot too). To start now:'
printf '%q\n' "$dictation_root/bin/dictation"
