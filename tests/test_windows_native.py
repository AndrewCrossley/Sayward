import sys
import time
import ctypes as C
import os
import pytest

pytestmark=pytest.mark.skipif(sys.platform!='win32' or os.environ.get('SAYWARD_NATIVE_TESTS')!='1',reason='Requires an interactive disposable Windows desktop; set SAYWARD_NATIVE_TESTS=1 in VM')


def test_native_clipboard_preserves_unicode_and_both_mouse_buttons_are_consumed():
    from dictation.windows_native import Desktop,U,W,Input,InputUnion,MouseInput
    desktop=Desktop(8,9)
    try:
        desktop.copy('Public words — 日本語 🙂')
        U.GetClipboardData.argtypes=[W.UINT];U.GetClipboardData.restype=W.HANDLE
        from dictation.windows_native import K
        assert U.OpenClipboard(desktop.clipboard_window)
        try:
            handle=U.GetClipboardData(13);pointer=K.GlobalLock(handle)
            try:assert C.wstring_at(pointer)=='Public words — 日本語 🙂'
            finally:K.GlobalUnlock(handle)
        finally:U.CloseClipboard()
        for button in (1,2):
            events=(Input*2)(Input(type=0,value=InputUnion(mi=MouseInput(data=button,flags=0x80))),Input(type=0,value=InputUnion(mi=MouseInput(data=button,flags=0x100))))
            assert U.SendInput(2,events,C.sizeof(Input))==2
        time.sleep(0.15)
        events=desktop.events()
        assert [button for button,_ in events]==[8,9]
        assert all(0 <= time.monotonic()-at < 2 for _,at in events)
    finally:desktop.close()


def test_native_focus_change_never_injects_keys(monkeypatch):
    from dictation.windows_native import Desktop,U
    desktop=Desktop.__new__(Desktop)
    state=[(1,2)]
    desktop.focus=lambda:state[0]
    desktop.copy=lambda _:state.__setitem__(0,(1,3))
    calls=[]
    monkeypatch.setattr(U,'SendInput',lambda *args:calls.append(args))
    with pytest.raises(RuntimeError,match='Focus changed'):desktop.paste('public words',(1,2))
    assert not calls


def test_singleton_refuses_second_listener_and_releases_on_close():
    from dictation.windows_native import Singleton
    first=Singleton()
    try:
        with pytest.raises(RuntimeError,match='already running'):Singleton()
    finally:first.close()
    second=Singleton();second.close()
