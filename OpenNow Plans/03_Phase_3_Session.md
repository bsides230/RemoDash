# Phase 3: Session Orchestration & Signaling

## Goals
Translate the core CloudMatch logic and WebRTC signaling protocols from Node.js to Python.

## Steps
1. **Analyze TypeScript Source:**
   - Review `OpenNOW/opennow-stable/src/main/gfn/cloudmatch.ts`.
   - Review `OpenNOW/opennow-stable/src/main/gfn/signaling.ts`.
   - Understand the flow of requesting a session, waiting in the queue, and establishing the initial WebRTC connection.

2. **CloudMatch Logic (`api.py`):**
   - Implement the API calls to request a new session from NVIDIA's servers given a game ID and region.
   - Replicate the polling mechanism to check queue status and receive the server assignment.
   - Implement session stop/claim logic.

3. **WebRTC Signaling:**
   - Replicate the signaling connection logic, parsing the ICE candidates and session descriptions (SDP).
   - *Note:* The actual WebRTC streaming will be handled in the browser (Phase 4), but the Python backend needs to facilitate the exchange of the SDP offer/answer between the frontend and NVIDIA's servers.
   - Implement WebSockets in FastAPI (if necessary) to stream signaling messages down to the frontend in real-time, or rely on long-polling/SSE depending on the protocol requirements.

4. **FastAPI Endpoints:**
   - `GET /api/modules/mod_opennow/regions` -> Fetch available streaming regions.
   - `POST /api/modules/mod_opennow/session/start` -> Initiate a session for a specific game.
   - `GET /api/modules/mod_opennow/session/poll` -> Check the status of the requested session.
   - `POST /api/modules/mod_opennow/session/stop` -> Terminate an active session.

5. **Testing:**
   - Successfully initiate a session for a free game and confirm the backend correctly reports moving through the queue.
   - Verify that the final signaling payload (SDP/ICE) is generated and ready to be consumed by the frontend player.
