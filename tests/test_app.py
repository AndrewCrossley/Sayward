import pytest
pytest.importorskip('gi')
pytest.importorskip('Xlib')
from dictation.app import App


@pytest.mark.parametrize('state', ['recording', 'working'])
def test_late_idle_unload_does_not_reset_active_operation(state):
    app = App.__new__(App)
    app.state = state
    changes = []
    app.set_state = lambda *args: changes.append(args)
    app.unloaded()
    assert app.state == state
    assert not changes
