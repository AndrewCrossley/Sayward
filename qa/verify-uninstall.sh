#!/bin/bash
# Disposable Mint worker only; public dependencies/model archives are fixtures.
set -euo pipefail
if ! systemd-detect-virt --vm >/dev/null 2>&1; then
    echo 'This verification script runs only in a disposable VM.' >&2
    exit 2
fi
test -f "$HOME/candidate.tar.gz"
test -f "$HOME/public-python-env.tar"
test -f "$HOME/medium-model.tar"
sudo -n true
echo guest-admin-ok
dictation_root="$HOME/system-dictation"
mkdir -p "$dictation_root/.venv" "$HOME/medium-model" "$HOME/.config/system-dictation" "$HOME/.local/bin"
tar -xzf "$HOME/candidate.tar.gz" -C "$dictation_root"
tar -xf "$HOME/public-python-env.tar" -C "$dictation_root/.venv"
tar -xf "$HOME/medium-model.tar" -C "$HOME/medium-model"
chmod +x "$HOME/uv"
ln -sfn "$HOME/uv" "$HOME/.local/bin/uv"
export PATH="$HOME/.local/bin:$PATH"
cd "$dictation_root"
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from dictation.core import Config
c = Config(model=str(Path.home()/'medium-model'))
p = Path.home()/'.config/system-dictation/config.json'
p.write_text(json.dumps(c.__dict__))
p.chmod(0o600)
PY
dictation_config_hash="$(sha256sum "$HOME/.config/system-dictation/config.json")"
dictation_model_hash="$(sha256sum "$HOME/medium-model/model.bin")"
./install.sh
test -f "$HOME/.config/autostart/system-dictation.desktop"
test "$(readlink -f "$HOME/.local/bin/system-dictation")" = "$dictation_root/bin/dictation"
test "$(sha256sum "$HOME/.config/system-dictation/config.json")" = "$dictation_config_hash"
echo installed-launcher-and-startup-verified
./uninstall.sh
test ! -e "$HOME/.config/autostart/system-dictation.desktop"
test ! -e "$HOME/.local/bin/system-dictation"
test "$(sha256sum "$HOME/.config/system-dictation/config.json")" = "$dictation_config_hash"
test "$(sha256sum "$HOME/medium-model/model.bin")" = "$dictation_model_hash"
test -f "$dictation_root/dictation/app.py"
if pgrep -f "^$dictation_root/.venv/bin/python .*dictation\.(app|worker)"; then
    echo unexpected-dictation-process >&2
    exit 1
fi
echo uninstall-verified-startup-and-launcher-removed-config-model-source-preserved
