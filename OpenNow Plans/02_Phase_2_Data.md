# Phase 2: Data Fetching & Caching

## Goals
Translate the GeForce NOW GraphQL queries for game catalogs and libraries from TypeScript to Python and expose them via FastAPI.

## Steps
1. **Analyze TypeScript Source:**
   - Review `OpenNOW/opennow-stable/src/main/gfn/games.ts`.
   - Identify the GraphQL endpoints, queries, and headers required to fetch the game library and public catalog.

2. **Backend API Logic (`api.py`):**
   - Implement Python functions to fetch the main games list, public games catalog, and the user's specific library.
   - Attach the access token obtained in Phase 1 to the authorization headers.
   - Utilize `aiohttp` for non-blocking HTTP calls.

3. **Caching Layer:**
   - Review `OpenNOW/opennow-stable/src/main/services/cacheManager.ts`.
   - Implement a similar caching strategy in Python (e.g., using an in-memory dictionary or saving to a local JSON file like `data/opennow_cache.json`).
   - Add TTL logic to refresh the cache when necessary.

4. **FastAPI Endpoints:**
   - `GET /api/modules/mod_opennow/games/library` -> Returns the user's owned/synced games.
   - `GET /api/modules/mod_opennow/games/public` -> Returns the general catalog of available games.
   - `POST /api/modules/mod_opennow/games/refresh` -> Force a cache invalidation and re-fetch.

5. **Testing:**
   - Call the endpoints manually to ensure they return JSON structured data.
   - Verify that subsequent calls are faster, confirming the caching logic is working.
