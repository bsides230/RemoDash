# Remo Player - Phase 02 Prompt (Local Fullscreen Viewer)

Implement only Phase 02.

## Goals
Build host-local fullscreen viewer/player layer while preserving existing API contract.

## Requirements
- Linux/Windows can have separate implementations but same command behavior.
- Fullscreen viewer with:
  - invisible close hotspot in top corner
  - hidden control bar near bottom
  - reveal on mouse movement/touch/keyboard input
  - auto-hide after inactivity
- Viewer only plays/render media and responds to controls.

## Deliverables
1. Viewer launcher abstraction per OS.
2. Viewer page/app implementing controls + media display.
3. Runtime hooks to receive state/commands from RemoDash API.
4. Build notes update with logging section.
