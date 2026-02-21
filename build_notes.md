
## Updates - [Date]

### Module Improvements
- **Graceful Shutdown:** Implemented a `shutdown_event` in `mod_xtts` and `mod_kokoro` to handle server shutdown signals gracefully.
  - Ensures TTS generation tasks are aborted immediately upon server stop.
  - Prevents the server from hanging indefinitely while waiting for background threads to finish.
  - Patched `mod_kokoro` model loading to exit early if shutdown is requested during initialization.
