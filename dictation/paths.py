"""Native locations; existing Linux configuration/cache remain compatible."""
import os
from pathlib import Path
import sys


def data_directory():
    return Path(os.environ.get('LOCALAPPDATA', str(Path.home()/'AppData/Local'))) / 'Sayward'


def cache_directory():
    return str(data_directory()/'models') if sys.platform == 'win32' else str(Path.home()/'.cache/system-dictation/models')


def config_path():
    default = data_directory()/'config.json' if sys.platform == 'win32' else Path.home()/'.config/system-dictation/config.json'
    return Path(os.environ.get('DICTATION_CONFIG', str(default)))


def assets():
    return Path(__file__).resolve().parent.parent
