# Remo Player - Phase 01 Prompt (Contract + Data Layer)

Implement only Phase 01 for RemoDash media player.

## Goals
- Keep playlist as source of truth.
- Implement/maintain playlist + playback data schema.
- Implement clean `/api/remo-player/*` API contract.
- Keep server thin and place media-player logic in a dedicated script/module.

## Required outcomes
1. Dedicated script for player logic (not bloating `server.py`).
2. CRUD-style playlist item operations: create/add/remove/reorder/set-active.
3. Playback state model fields:
   - current index/item
   - repeat
   - shuffle
   - active order
   - next order
4. Update build notes with logging section.

## Do not do in this phase
- No fullscreen host viewer yet.
- No visual polish.
