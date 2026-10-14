import json
import types
import numpy as np
import pytest
from dictation.core import Config, TranscriptHistory, input_level


def test_history_keeps_five_newest_and_selected_item_is_independent_of_clipboard():
    history = TranscriptHistory()
    assert history.text == ""
    for i in range(6):
        history.add(f"Transcript {i}")
    assert history.items == [f"Transcript {i}" for i in range(5, 0, -1)]
    history.select(4)
    assert history.text == "Transcript 1"
    history.add(" ")
    assert history.text == "Transcript 1"
    history.add("Newest")
    assert history.text == "Newest" and len(history.items) == 5
    assert "Transcript 1" not in history.items
    with pytest.raises(ValueError):
        history.select(5)


def test_repeated_transcripts_count_as_distinct_recordings_and_restart_is_empty():
    history = TranscriptHistory()
    history.add("Same words")
    history.add("Same words")
    assert len(history.items) == 2
    assert TranscriptHistory().items == []


def test_meter_handles_silence_empty_and_full_scale_without_integer_overflow():
    assert input_level(np.zeros((512, 1), dtype=np.int16)) == 0
    assert input_level(np.array([], dtype=np.int16)) == 0
    assert input_level(np.full((512, 1), -32768, dtype=np.int16)) == 1
    quiet = input_level(np.full((512, 1), 100, dtype=np.int16))
    voice = input_level(np.full((512, 1), 3000, dtype=np.int16))
    assert 0 < quiet < voice < 1


def test_existing_config_gains_forward_binding_without_overwriting_files(tmp_path):
    path = tmp_path/'config.json'
    path.write_text(json.dumps({'button': 8}))
    before = path.read_text()
    assert Config.load(path).paste_button == 9
    assert path.read_text() == before
    path.write_text(json.dumps({'button': 9}))
    assert Config.load(path).paste_button == 8
    path.write_text(json.dumps({'button': 8, 'paste_button': 8}))
    with pytest.raises(ValueError, match='different'):
        Config.load(path)
