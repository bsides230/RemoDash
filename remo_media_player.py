import datetime
import json
import random
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any, Set


class RemoMediaPlayerManager:
    """Playlist-authoritative media playback state manager.

    This manager intentionally keeps logic simple and deterministic:
    - Playlist is source of truth.
    - Playback order is either direct playlist order or a prepared shuffle order.
    - Repeat + shuffle prebuilds next loop order near the tail window.
    """

    def __init__(self, data_file: str = "data/remo_media_player.json"):
        self.data_file = Path(data_file)
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.state = {
            "schema_version": 1,
            "playlists": {},
            "active_playlist_id": None,
            "playback": {
                "is_playing": False,
                "is_paused": False,
                "repeat": False,
                "shuffle": False,
                "current_index": 0,
                "current_item_id": None,
                "active_order": [],
                "next_order": [],
                "loop_generation": 0,
                "image_default_duration_sec": 8,
                "viewer": {"mode": "detached", "status": "idle", "impl": "webview"},
            },
        }
        self._load()

    def _load(self):
        if not self.data_file.exists():
            self._save()
            return
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                self.state = json.load(f)
        except Exception:
            self._save()

    def _save(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    @staticmethod
    def _now() -> str:
        return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

    def _active_playlist(self) -> Optional[Dict[str, Any]]:
        pid = self.state.get("active_playlist_id")
        if not pid:
            return None
        return self.state.get("playlists", {}).get(pid)

    @staticmethod
    def _bucket_size(size: int) -> int:
        return max(1, int(size * 0.2)) if size > 0 else 0

    def _prepare_shuffle_order(
        self,
        items: List[Dict[str, Any]],
        forbidden_start_media_keys: Optional[Set[str]] = None,
    ) -> List[str]:
        work = list(items)
        random.shuffle(work)
        if not work:
            return []

        forbidden_start_media_keys = forbidden_start_media_keys or set()
        bucket = self._bucket_size(len(work))
        if bucket <= 0:
            return [it["id"] for it in work]

        if forbidden_start_media_keys:
            start = work[:bucket]
            for i, it in enumerate(start):
                if it.get("media_key") in forbidden_start_media_keys:
                    swap_idx = None
                    for j in range(bucket, len(work)):
                        if work[j].get("media_key") not in forbidden_start_media_keys:
                            swap_idx = j
                            break
                    if swap_idx is not None:
                        work[i], work[swap_idx] = work[swap_idx], work[i]

        return [it["id"] for it in work]

    def _tail_media_keys(self, playlist: Dict[str, Any], order: List[str]) -> Set[str]:
        items = {it["id"]: it for it in playlist.get("items", [])}
        bucket = self._bucket_size(len(order))
        tail_ids = order[-bucket:] if bucket else []
        return {items[i].get("media_key") for i in tail_ids if i in items}

    def _normalize_playlist(self, playlist: Dict[str, Any]):
        for it in playlist.get("items", []):
            it.setdefault("id", str(uuid.uuid4()))
            it.setdefault("type", "video")
            it.setdefault("title", Path(it.get("source", "item")).name)
            it.setdefault("source", "")
            it.setdefault("duration_sec", None)
            it.setdefault("enabled", True)
            it.setdefault("media_key", it.get("source", ""))

    def create_playlist(self, name: str) -> Dict[str, Any]:
        pid = str(uuid.uuid4())
        playlist = {
            "id": pid,
            "name": name,
            "created_at": self._now(),
            "updated_at": self._now(),
            "items": [],
        }
        self.state["playlists"][pid] = playlist
        if not self.state.get("active_playlist_id"):
            self.state["active_playlist_id"] = pid
        self._save()
        return playlist

    def set_active_playlist(self, playlist_id: str):
        if playlist_id not in self.state.get("playlists", {}):
            raise ValueError("Playlist not found")
        self.state["active_playlist_id"] = playlist_id
        playback = self.state["playback"]
        playback["current_index"] = 0
        playback["current_item_id"] = None
        playback["active_order"] = []
        playback["next_order"] = []
        self._save()

    def add_item(self, playlist_id: str, item: Dict[str, Any]) -> Dict[str, Any]:
        playlist = self.state.get("playlists", {}).get(playlist_id)
        if not playlist:
            raise ValueError("Playlist not found")
        new_item = {
            "id": str(uuid.uuid4()),
            "type": item.get("type", "video"),
            "title": item.get("title") or Path(item.get("source", "item")).name,
            "source": item.get("source", ""),
            "duration_sec": item.get("duration_sec"),
            "enabled": item.get("enabled", True),
            "media_key": item.get("media_key") or item.get("source", ""),
        }
        playlist["items"].append(new_item)
        playlist["updated_at"] = self._now()
        self._save()
        return new_item

    def remove_item(self, playlist_id: str, item_id: str):
        playlist = self.state.get("playlists", {}).get(playlist_id)
        if not playlist:
            raise ValueError("Playlist not found")
        playlist["items"] = [i for i in playlist.get("items", []) if i.get("id") != item_id]
        playlist["updated_at"] = self._now()
        self._save()

    def reorder_item(self, playlist_id: str, item_id: str, to_index: int):
        playlist = self.state.get("playlists", {}).get(playlist_id)
        if not playlist:
            raise ValueError("Playlist not found")
        items = playlist.get("items", [])
        idx = next((i for i, it in enumerate(items) if it.get("id") == item_id), None)
        if idx is None:
            raise ValueError("Item not found")
        item = items.pop(idx)
        to_index = max(0, min(to_index, len(items)))
        items.insert(to_index, item)
        playlist["updated_at"] = self._now()
        self._save()

    def _resolve_active_order(self):
        playlist = self._active_playlist()
        playback = self.state["playback"]
        if not playlist:
            playback["active_order"] = []
            return

        self._normalize_playlist(playlist)
        items = [it for it in playlist.get("items", []) if it.get("enabled", True)]

        if playback.get("shuffle"):
            if not playback.get("active_order"):
                playback["active_order"] = self._prepare_shuffle_order(items)
        else:
            playback["active_order"] = [it["id"] for it in items]

        if playback["current_index"] >= len(playback["active_order"]):
            playback["current_index"] = 0

    def _prefetch_next_order_if_needed(self):
        playlist = self._active_playlist()
        playback = self.state["playback"]
        if not playlist:
            return
        if not playback.get("repeat") or not playback.get("shuffle"):
            playback["next_order"] = []
            return

        active = playback.get("active_order", [])
        if not active:
            return

        bucket = self._bucket_size(len(active))
        idx = playback.get("current_index", 0)
        in_last_window = idx >= max(0, len(active) - bucket)

        if in_last_window and not playback.get("next_order"):
            items = [it for it in playlist.get("items", []) if it.get("enabled", True)]
            forbidden = self._tail_media_keys(playlist, active)
            playback["next_order"] = self._prepare_shuffle_order(
                items,
                forbidden_start_media_keys=forbidden,
            )

    def start(self):
        playback = self.state["playback"]
        self._resolve_active_order()
        playback["is_playing"] = True
        playback["is_paused"] = False
        active = playback.get("active_order", [])
        playback["current_item_id"] = active[playback["current_index"]] if active else None
        self._prefetch_next_order_if_needed()
        self._save()

    def pause(self):
        self.state["playback"]["is_paused"] = True
        self.state["playback"]["is_playing"] = False
        self._save()

    def toggle_repeat(self) -> bool:
        pb = self.state["playback"]
        pb["repeat"] = not pb.get("repeat", False)
        if not pb["repeat"]:
            pb["next_order"] = []
        self._save()
        return pb["repeat"]

    def toggle_shuffle(self) -> bool:
        pb = self.state["playback"]
        pb["shuffle"] = not pb.get("shuffle", False)
        pb["current_index"] = 0
        pb["active_order"] = []
        pb["next_order"] = []
        self._resolve_active_order()
        active = pb.get("active_order", [])
        pb["current_item_id"] = active[0] if active else None
        self._save()
        return pb["shuffle"]

    def step(self, direction: int):
        pb = self.state["playback"]
        self._resolve_active_order()
        active = pb.get("active_order", [])

        if not active:
            pb["current_item_id"] = None
            self._save()
            return

        pb["current_index"] += direction
        if pb["current_index"] >= len(active):
            if pb.get("repeat"):
                if pb.get("shuffle") and pb.get("next_order"):
                    pb["active_order"] = pb["next_order"]
                    pb["next_order"] = []
                    active = pb["active_order"]
                elif pb.get("shuffle"):
                    playlist = self._active_playlist()
                    items = [it for it in playlist.get("items", []) if it.get("enabled", True)] if playlist else []
                    forbidden = self._tail_media_keys(playlist, active) if playlist else set()
                    pb["active_order"] = self._prepare_shuffle_order(items, forbidden_start_media_keys=forbidden)
                    active = pb["active_order"]
                pb["current_index"] = 0
                pb["loop_generation"] = pb.get("loop_generation", 0) + 1
            else:
                pb["current_index"] = max(0, len(active) - 1)
                pb["is_playing"] = False
        elif pb["current_index"] < 0:
            pb["current_index"] = len(active) - 1 if pb.get("repeat") else 0

        pb["current_item_id"] = active[pb["current_index"]] if active else None
        self._prefetch_next_order_if_needed()
        self._save()

    def get_state(self) -> Dict[str, Any]:
        self._resolve_active_order()
        self._prefetch_next_order_if_needed()
        self._save()
        return self.state
