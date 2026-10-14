"""Provision a public five-item cache before a focused, source-blind VM run."""
import subprocess
from pathlib import Path
assert subprocess.run(['systemd-detect-virt', '--vm'], capture_output=True).returncode == 0
from dictation.app import App, Gtk
from dictation.core import Config

app = App(Config.load(Path.home()/'.config/system-dictation/config.json'))
for text in [
    'Transcript number two. Bananas are yellow.\n' + '\n'.join(f'Public long-preview paragraph {i}: the selected transcript can be scrolled and pasted.' for i in range(30)),
    'Transcript number three. The ocean is blue.',
    'Transcript number four. The forest is green.',
    'Transcript number five. Snow is white.',
    'Transcript number six. Oranges are orange.',
]:
    app.history.add(text)
app.set_state('idle', 'Public history fixture — ready')
Gtk.main()
