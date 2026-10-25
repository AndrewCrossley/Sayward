"""Frozen entry point dispatches workers before importing any UI."""
import os
import sys


def main():
    os.environ.setdefault('HF_HUB_DISABLE_TELEMETRY','1')
    os.environ.setdefault('HF_HUB_DISABLE_PROGRESS_BARS','1')
    # PyInstaller's windowed GUI sets these to None. Download libraries still
    # expect file-like streams; discard their console output, never log speech.
    for name in ('stdout','stderr'):
        if getattr(sys,name) is None:
            setattr(sys,name,open(os.devnull,'w',encoding='utf-8'))
    if sys.argv[1:2] == ['--worker']:
        # Windowed frozen programs have no standard streams. The worker exe
        # is built console-enabled and launched hidden with redirected pipes.
        from .worker import main as worker
        try:
            worker(sys.argv[2:])
        except Exception as exc:
            import json
            print(json.dumps({'error':str(exc)}), flush=True)
            raise SystemExit(1)
        return
    if sys.platform == 'win32':
        from .windows_app import main as windows
        windows()
    else:
        from .app import main as linux
        linux()


if __name__ == '__main__':
    main()
