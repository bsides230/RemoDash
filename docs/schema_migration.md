## Schema Migration

The current state schema for Remo Media Player is version `1`.

If future updates require schema changes, you must provide a rollback-safe migration script or handle schema evolution gracefully in `_load()`.

**Guidelines for Schema Evolution:**
1. Never overwrite unknown keys from older or newer versions.
2. Increment the `schema_version` integer in the state when introducing backward-incompatible changes.
3. If downgrading the software, an older version of the manager should ignore or preserve unknown keys from a newer schema.

*(Currently, no schema changes were required for Phase 05).*
