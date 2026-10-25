import sys
from types import SimpleNamespace
from dictation import launcher


def test_windowed_startup_supplies_safe_streams_before_download_libraries(monkeypatch):
    previous=sys.stdout,sys.stderr
    opened=[];called=[]
    def gui():
        sys.stdout.write('public model progress')
        sys.stderr.write('public download diagnostic')
        called.append(True)
    monkeypatch.setattr(sys,'platform','win32')
    monkeypatch.setattr(sys,'argv',['Sayward.exe'])
    monkeypatch.setitem(sys.modules,'dictation.windows_app',SimpleNamespace(main=gui))
    try:
        sys.stdout=sys.stderr=None
        launcher.main()
        opened=[sys.stdout,sys.stderr]
        assert called and all(stream is not None for stream in opened)
    finally:
        sys.stdout,sys.stderr=previous
        for stream in opened:stream.close()
