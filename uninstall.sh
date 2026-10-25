#!/bin/bash
set -euo pipefail
dictation_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo 'Quit Sayward / System Dictation from its tray menu first.'
for name in sayward system-dictation; do
    launcher="$HOME/.local/bin/$name"
    if [[ -L "$launcher" && "$(readlink -f "$launcher")" == "$dictation_root/bin/dictation" ]]; then
        rm -- "$launcher"
    fi
done
startup="$HOME/.config/autostart/system-dictation.desktop"
escaped=$(printf '%s' "$dictation_root/bin/dictation" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g' -e 's/`/\\`/g' -e 's/\$/\\$/g' -e 's/%/%%/g')
if [[ -f "$startup" ]] && grep -Fqx -- "Exec=\"$escaped\"" "$startup"; then
    rm -- "$startup"
fi
echo 'Removed this checkout’s startup entry and launchers. Configuration, model cache and source remain.'
