"""Win32 injection guards run in CI without opening any windows."""
import sys
import pytest
pytestmark=pytest.mark.skipif(sys.platform!='win32',reason='Win32 API boundary')


@pytest.mark.parametrize('focus,modifier',[(None,0),((2,3),0),((1,2),0x8000)])
def test_enter_refuses_changed_focus_or_held_modifiers(monkeypatch,focus,modifier):
    from dictation.windows_native import Desktop,U
    desktop=Desktop.__new__(Desktop);desktop.focus=lambda:focus
    calls=[]
    monkeypatch.setattr(U,'GetAsyncKeyState',lambda _:modifier)
    monkeypatch.setattr(U,'SendInput',lambda *args:calls.append(args))
    with pytest.raises(RuntimeError):desktop.enter((1,2))
    assert calls==[]


def test_enter_sends_one_down_up_pair_and_releases_after_partial_failure(monkeypatch):
    from dictation.windows_native import Desktop,U
    desktop=Desktop.__new__(Desktop);desktop.focus=lambda:(1,2)
    monkeypatch.setattr(U,'GetAsyncKeyState',lambda _:0)
    calls=[]
    def send(count,events,_):
        calls.append([(events[i].value.ki.vk,events[i].value.ki.flags) for i in range(count)])
        return count
    monkeypatch.setattr(U,'SendInput',send);desktop.enter((1,2))
    assert calls==[[(0x0D,0),(0x0D,2)]]
    calls.clear()
    def partial(count,events,_):send(count,events,_);return 1
    monkeypatch.setattr(U,'SendInput',partial)
    with pytest.raises(RuntimeError,match='blocked Enter'):desktop.enter((1,2))
    assert calls==[[(0x0D,0),(0x0D,2)],[(0x0D,2)]]
