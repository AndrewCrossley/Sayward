#!/bin/bash
set -euo pipefail
echo 'Quit System Dictation from its tray menu first.'
rm -f "$HOME/.config/autostart/system-dictation.desktop"
if [[ -L "$HOME/.local/bin/system-dictation" ]]; then rm "$HOME/.local/bin/system-dictation"; fi
echo 'Removed login startup and launcher. Configuration, model cache and source remain.'
