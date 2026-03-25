# RemoDash Media Player Module (VLC Replacement) - Initial Design

## 1) Proposed Architecture

### A. Playlist/Data Layer
- **Authority:** Playlist order and metadata are source of truth.
- **Storage:** `data/remo_media_player.json` (single-file, append-friendly JSON).
- **Mutation Model:** Small operations (`add`, `remove`, `reorder`, `toggle`) without rebuilding full playlist.
- **Schemas:** Playlist + playback state explicitly versioned (`schema_version`).

### B. Playback/Control API Layer
- FastAPI endpoints under `/api/remo-player/*`.
- Stateless command calls mutate server-side playback state machine.
- Playback state derives from:
  - active playlist
  - active order
  - current index
  - repeat flag
  - shuffle flag
  - precomputed next shuffle order

### C. Local Fullscreen Viewer Layer
- Viewer kept separate from playlist management.
- Viewer behavior target:
  - fullscreen on host
  - invisible close hotspot (top corner)
  - hidden controls near bottom
  - controls reveal on mouse/touch/keyboard activity
  - auto-hide on inactivity
- Linux/Windows may use different launchers but must implement identical command contract.

## 2) API Contract (v0 Initial)

### Playlist APIs
- `GET /api/remo-player/state`
  - Returns full playlists + active playback state.
- `POST /api/remo-player/playlists`
  - Body: `{ "name": "Menu Loop" }`
- `POST /api/remo-player/playlists/active`
  - Body: `{ "playlist_id": "..." }`
- `POST /api/remo-player/playlists/{playlist_id}/items`
  - Body: `{ "type":"audio|video|image", "source":"...", "title":"...", "duration_sec":8, "media_key":"..." }`
- `POST /api/remo-player/playlists/{playlist_id}/reorder`
  - Body: `{ "item_id":"...", "to_index":3 }`
- `POST /api/remo-player/playlists/{playlist_id}/items/delete`
  - Body: `{ "item_id":"..." }`

### Playback Control APIs
- `POST /api/remo-player/control`
  - Body: `{ "action": "play|pause|next|prev|toggle_repeat|toggle_shuffle" }`

## 3) Playlist Schema

```json
{
  "id": "uuid",
  "name": "Lunch Playlist",
  "created_at": "2026-03-25T00:00:00Z",
  "updated_at": "2026-03-25T00:00:00Z",
  "items": [
    {
      "id": "uuid",
      "type": "audio|video|image",
      "title": "Display Name",
      "source": "/path/or/url",
      "duration_sec": 8,
      "enabled": true,
      "media_key": "/path/or/url"
    }
  ]
}
```

## 4) Playback State Model

```json
{
  "is_playing": true,
  "is_paused": false,
  "repeat": true,
  "shuffle": true,
  "current_index": 4,
  "current_item_id": "uuid",
  "active_order": ["uuid1", "uuid2"],
  "next_order": ["uuid3", "uuid4"],
  "loop_generation": 2,
  "image_default_duration_sec": 8,
  "viewer": {
    "mode": "detached",
    "status": "idle",
    "impl": "webview"
  }
}
```

## 5) Recommended Viewer Approach

### Linux
- **Preferred:** Chromium/Chrome kiosk/fullscreen app window pointing at a local viewer URL.
- **Fallback:** Qt WebEngine or mpv-based wrapper if browser stack is unavailable.

### Windows
- **Preferred:** Edge/Chrome app-window fullscreen launch to local viewer URL.
- **Fallback:** WebView2 desktop host.

### Shared Contract
Both must support same commands:
- load state
- play/pause
- next/prev
- jump to index
- set repeat/shuffle
- report now-playing

## 6) Initial Implementation Plan

1. Keep playlist state and control APIs in core server (`server.py`) as a stable contract.
2. Build RemoDash module UI (`web/modules/RemoMediaPlayer.html`) for:
   - playlist creation/editing
   - mixed media item insertion
   - mobile-friendly pointer drag reorder
   - playback controls + now-playing display
3. Add local viewer page + launcher abstraction (`viewer_linux.py`, `viewer_windows.py`) with identical API adapter.
4. Connect viewer heartbeats/events to `/api/remo-player/state` for robust state sync.
5. Add tests for:
   - reorder correctness
   - shuffle preparation constraints
   - repeat boundary next-order prebuild
   - cross-loop 20% boundary exclusion by `media_key`

## Shuffle/Repeat Logic Notes
- Shuffle is precomputed as an ordered queue (`active_order`).
- No item from previous loop final 20% may appear in next loop first 20% (by `media_key`) when possible.
- If repeat+shuffle and playback enters final 20%, precompute `next_order` ahead of loop end.
