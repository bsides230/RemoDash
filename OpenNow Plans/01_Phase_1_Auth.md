# Phase 1: Foundation & Backend Authentication

## Goals
Establish the base RemoDash module structure for `mod_opennow` and reimplement the NVIDIA OAuth flow.

## Steps
1. **Module Scaffolding:**
   - Create `modules/mod_opennow/module.json`.
   - Create `modules/mod_opennow/api.py`.
   - Create the `modules/mod_opennow/web/` directory.

2. **Backend Authentication Logic (`api.py`):**
   - Study `OpenNOW/opennow-stable/src/main/gfn/auth.ts`.
   - Reimplement the NVIDIA OAuth flow in Python. This includes generating PKCE verifiers, handling the login URL generation, and the token exchange process.
   - Use `aiohttp` for the external HTTP requests to NVIDIA authentication endpoints.
   - Securely store the authentication tokens using RemoDash's data structure, likely saving to `data/opennow_auth.json`.

3. **FastAPI Endpoints:**
   - `GET /api/modules/mod_opennow/auth/login-url` -> Returns the NVIDIA login URL to direct the user to.
   - `POST /api/modules/mod_opennow/auth/callback` -> Endpoint to process the authorization code and complete the login.
   - `GET /api/modules/mod_opennow/auth/status` -> Check if a valid session exists.

4. **Testing:**
   - Ensure the module loads successfully in RemoDash without throwing errors on startup.
   - Verify the login URL can be generated.
   - Test the OAuth flow to ensure an access token is successfully retrieved and saved.
