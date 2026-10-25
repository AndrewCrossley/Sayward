"""Frozen entry point dispatches workers before importing any UI."""
import os
import sys


def main():
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
