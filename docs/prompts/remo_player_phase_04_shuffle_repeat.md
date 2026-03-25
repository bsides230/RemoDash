# Remo Player - Phase 04 Prompt (Shuffle + Repeat Boundary Logic)

Implement only Phase 04.

## Goals
Implement deterministic prepared shuffle and loop prebuild behavior.

## Requirements
- Shuffle is prepared order, not item-by-item random picks.
- Enforce boundary rule:
  - first 20% of new order must not overlap with last 20% of previous order by item identity/media key when possible.
- If repeat+shuffle is active, precompute next order during final 20% of current order.

## Deliverables
1. Shuffle preparation logic finalized.
2. Next-loop prebuild trigger finalized.
3. Boundary exclusion logic finalized.
4. Tests for boundary behavior and repeat transitions.
5. Build notes update with logging section.
