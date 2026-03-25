import pytest
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remo_media_player import RemoMediaPlayerManager

@pytest.fixture
def manager(tmp_path):
    data_file = tmp_path / "test_remo.json"
    m = RemoMediaPlayerManager(data_file=str(data_file))
    return m

def test_playback_state_transitions(manager):
    # Setup playlist
    playlist = manager.create_playlist("Test")
    pid = playlist["id"]
    for i in range(3):
        manager.add_item(pid, {"title": f"Item {i}", "source": f"src_{i}"})

    manager.set_active_playlist(pid)

    # 1. Play
    manager.start()
    pb = manager.state["playback"]
    assert pb["is_playing"] == True
    assert pb["is_paused"] == False
    assert pb["current_index"] == 0
    assert pb["current_item_id"] == pb["active_order"][0]

    # 2. Pause
    manager.pause()
    assert pb["is_playing"] == False
    assert pb["is_paused"] == True

    # 3. Next
    manager.start()
    manager.step(1)
    assert pb["current_index"] == 1
    assert pb["current_item_id"] == pb["active_order"][1]

    # 4. Prev
    manager.step(-1)
    assert pb["current_index"] == 0
    assert pb["current_item_id"] == pb["active_order"][0]

    # 5. Next to end without repeat
    manager.step(1) # index 1
    manager.step(1) # index 2
    manager.step(1) # should stop or stay at last index
    assert pb["current_index"] == 2
    assert pb["is_playing"] == False # Playback should stop if not repeating

    # 6. Repeat
    manager.toggle_repeat()
    # When start() is called, current_index is resolved. Since it's already 2 (the end),
    # start() will just resume playback from where it is.
    manager.start()
    manager.step(1) # index 2 -> 0 (because repeat is True)
    assert pb["current_index"] == 0
    assert pb["is_playing"] == True

    # 7. Shuffle
    manager.toggle_shuffle()
    assert pb["shuffle"] == True
    assert pb["current_index"] == 0
    assert len(pb["active_order"]) == 3

def test_api_reorder(manager):
    playlist = manager.create_playlist("Test API Reorder")
    pid = playlist["id"]
    manager.add_item(pid, {"title": "A", "source": "A"})
    manager.add_item(pid, {"title": "B", "source": "B"})
    manager.add_item(pid, {"title": "C", "source": "C"})

    # Validate items
    items = manager.state["playlists"][pid]["items"]
    assert items[0]["title"] == "A"
    assert items[1]["title"] == "B"
    assert items[2]["title"] == "C"

    # Move C to index 0
    item_c_id = items[2]["id"]
    manager.reorder_item(pid, item_c_id, 0)

    items = manager.state["playlists"][pid]["items"]
    assert items[0]["title"] == "C"
    assert items[1]["title"] == "A"
    assert items[2]["title"] == "B"

def test_api_delete(manager):
    playlist = manager.create_playlist("Test API Delete")
    pid = playlist["id"]
    manager.add_item(pid, {"title": "A", "source": "A"})
    manager.add_item(pid, {"title": "B", "source": "B"})

    items = manager.state["playlists"][pid]["items"]
    item_a_id = items[0]["id"]

    manager.remove_item(pid, item_a_id)
    items = manager.state["playlists"][pid]["items"]
    assert len(items) == 1
    assert items[0]["title"] == "B"
