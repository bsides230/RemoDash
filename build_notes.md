# Build Notes

## Update: Cleanup and Tailscale Integration

**Date:** (Current Date)

### Summary
This update transitions the repository from a LYRN-specific AI dashboard to a generic system dashboard ("RemoDash"). It removes unused LLM-related modules and adds support for installing Tailscale via the setup wizard.

### Changes

#### Core System
- **Cleanup:** Removed all LLM-related code and module references from the frontend.
- **Wizard:** Added a step to `wizard.py` to optionally install Tailscale for remote access.

#### Frontend
- **Dashboard:**
    - Removed `mod_chat`, `mod_builder`, `mod_models`, `mod_model_manager`, and `mod_job_manager` from the registry.
    - Removed the `#sys-status-llm` indicator.
- **Server Status Module:**
    - Removed the LLM tab and stats display.
- **Settings Module:**
    - Removed the API Endpoints configuration section.

#### Deleted Files
- `web/modules/Chat Interface.html`
- `web/modules/Job Manager.html`
- `web/modules/ModelController.html`
- `web/modules/ModelManager.html`
- `web/modules/Snapshot Builder.html`
- `web/modules/Gamemaster/` directory

### Logging
- No changes to the logging system in this update.
