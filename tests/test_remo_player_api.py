import pytest
import os
import sys
import json
from pathlib import Path
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import app, remo_media_manager

client = TestClient(app)

import shutil

@pytest.fixture(autouse=True)
def bypass_auth():
    flag_dir = Path("global_flags")
    flag_file = flag_dir / "no_auth"
    flag_dir.mkdir(parents=True, exist_ok=True)

    # Backup existing if any
    was_present = flag_file.exists()

    with open(flag_file, "w") as f:
        f.write("1")

    yield

    # Cleanup
    if not was_present:
        try:
            flag_file.unlink()
        except:
            pass

@pytest.fixture(autouse=True)
def isolate_state():
    # Backup existing state to avoid polluting real data
    state_file = Path("data/remo_media_player.json")
    backup_file = Path("data/remo_media_player.json.bak")

    if state_file.exists():
        shutil.copy2(state_file, backup_file)

    yield

    # Restore state
    if backup_file.exists():
        shutil.move(backup_file, state_file)
    else:
        try:
            state_file.unlink()
        except:
            pass

def test_api_playlists():
    # Because we are testing the actual app instance, state might not be isolated.
    # So we handle dynamically.

    res = client.post("/api/remo-player/playlists", json={"name": "API Test Playlist"})
    assert res.status_code == 200
    playlist = res.json()
    pid = playlist["id"]

    res = client.post(f"/api/remo-player/playlists/active", json={"playlist_id": pid})
    assert res.status_code == 200

    res = client.post(f"/api/remo-player/playlists/{pid}/items", json={
        "type": "video",
        "title": "Vid 1",
        "source": "http://vid1"
    })
    assert res.status_code == 200
    item1 = res.json()

    res = client.post(f"/api/remo-player/playlists/{pid}/items", json={
        "type": "audio",
        "title": "Audio 1",
        "source": "http://aud1"
    })
    item2 = res.json()

    res = client.get("/api/remo-player/state")
    state = res.json()
    items = state["playlists"][pid]["items"]
    assert len(items) == 2
    assert items[0]["id"] == item1["id"]

    # reorder
    res = client.post(f"/api/remo-player/playlists/{pid}/reorder", json={
        "item_id": item1["id"],
        "to_index": 1
    })
    assert res.status_code == 200

    res = client.get("/api/remo-player/state")
    state = res.json()
    items = state["playlists"][pid]["items"]
    assert items[0]["id"] == item2["id"]

    # Control next
    res = client.post(f"/api/remo-player/control", json={"action": "next"})
    assert res.status_code == 200
    state = res.json()
    # It will resolve the active order and change current_index to 1.
    assert state["playback"]["current_index"] == 1

    # Viewer launch
    res = client.post("/api/remo-player/viewer/launch", json={})
    assert res.status_code == 200
