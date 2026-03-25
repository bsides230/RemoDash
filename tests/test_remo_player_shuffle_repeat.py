import pytest
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from remo_media_player import RemoMediaPlayerManager

@pytest.fixture
def temp_manager(tmp_path):
    data_file = tmp_path / "test_remo.json"
    manager = RemoMediaPlayerManager(data_file=str(data_file))
    return manager

def test_shuffle_preparation(temp_manager):
    # Test basic shuffle preparation
    items = [{"id": str(i), "media_key": f"key_{i}"} for i in range(10)]

    # Bucket size for 10 is 2
    # Forbidden keys
    forbidden = {"key_0", "key_1"}

    # We want to force a scenario where key_0 and key_1 are in the first 2 slots, to ensure they get swapped out
    # Since it's random, we can't easily force it, but we can verify the output respects the rule

    # Let's run it multiple times to ensure the first 2 never contain key_0 or key_1
    for _ in range(50):
        order = temp_manager._prepare_shuffle_order(items, forbidden_start_media_keys=forbidden)

        # order is list of ids, which match the index here
        first_two_keys = {items[int(i)]["media_key"] for i in order[:2]}

        # Verify no intersection when possible
        assert not first_two_keys.intersection(forbidden)

def test_shuffle_preparation_fallback(temp_manager):
    # Test when it's NOT possible to avoid overlap
    items = [{"id": str(i), "media_key": "same_key"} for i in range(5)]
    forbidden = {"same_key"}

    order = temp_manager._prepare_shuffle_order(items, forbidden_start_media_keys=forbidden)
    # Shouldn't crash, and should just return a valid order
    assert len(order) == 5

def test_next_loop_prebuild(temp_manager):
    playlist = temp_manager.create_playlist("Test")
    pid = playlist["id"]

    # Add 10 items
    for i in range(10):
        temp_manager.add_item(pid, {"title": f"Item {i}", "source": f"src_{i}"})

    temp_manager.set_active_playlist(pid)

    # Start playback
    temp_manager.start()

    pb = temp_manager.state["playback"]
    pb["repeat"] = True
    pb["shuffle"] = True

    # Active order length is 10. Bucket is 2.
    # Current index is 0. Next order should be empty.
    temp_manager._prefetch_next_order_if_needed()
    assert not pb["next_order"]

    # Step to index 7 (last window starts at index 8 for 10 items, bucket 2. wait, len 10 - 2 = 8, so index 8 and 9 are in the window)
    for _ in range(7):
        temp_manager.step(1)

    assert pb["current_index"] == 7
    assert not pb["next_order"]

    # Step to index 8. Now we are in the last window.
    temp_manager.step(1)

    assert pb["current_index"] == 8
    assert len(pb["next_order"]) == 10

    # Verify the first 2 items of next_order do not overlap with the last 2 of active_order
    tail_keys = temp_manager._tail_media_keys(temp_manager._active_playlist(), pb["active_order"])

    # Get the media keys of the first 2 items of next_order
    playlist_data = temp_manager._active_playlist()
    item_map = {it["id"]: it["media_key"] for it in playlist_data["items"]}

    next_head_keys = {item_map[i] for i in pb["next_order"][:2]}
    assert not next_head_keys.intersection(tail_keys)

def test_step_transition_to_next_order(temp_manager):
    playlist = temp_manager.create_playlist("Test")
    pid = playlist["id"]

    for i in range(5):
        temp_manager.add_item(pid, {"title": f"Item {i}", "source": f"src_{i}"})

    temp_manager.set_active_playlist(pid)
    temp_manager.start()

    pb = temp_manager.state["playback"]
    pb["repeat"] = True
    pb["shuffle"] = True

    # Manually jump to the last index
    pb["current_index"] = 4
    temp_manager._prefetch_next_order_if_needed()

    next_order_saved = list(pb["next_order"])
    assert len(next_order_saved) == 5

    # Step next!
    temp_manager.step(1)

    assert pb["current_index"] == 0
    assert pb["active_order"] == next_order_saved
    assert not pb["next_order"]
    assert pb["loop_generation"] == 1
