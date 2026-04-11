# Phase 4: Frontend UI & WebRTC Player

## Goals
Completely replace the React/Electron UI with standard RemoDash HTML/CSS/JS architecture. Implement the WebRTC stream player directly in the browser.

## Steps
1. **RemoDash Theming Integration:**
   - Create `web/index.html`.
   - Include standard RemoDash base CSS (`../../assets/base.css`) and theme client logic (`../../assets/theme-client.js`).
   - Replicate the visual layout of OpenNOW (sidebar for navigation, main area for game grid) using pure HTML and CSS Grid/Flexbox.

2. **UI Javascript Logic (`web/app.js`):**
   - Implement the view switching logic (Login view -> Library view -> Player view).
   - Fetch the authentication status from the backend to determine which view to show.
   - Fetch the game library and render the game cards dynamically.

3. **WebRTC In-Browser Player:**
   - Analyze how `OpenNOW/opennow-stable/src/renderer/App.tsx` and related player components handle the WebRTC video stream.
   - Implement the `RTCPeerConnection` logic in vanilla JavaScript.
   - Handle capturing controller input (Gamepad API) and mouse/keyboard events, sending them over WebRTC data channels to the NVIDIA server.
   - Render the incoming video stream onto a standard `<video>` HTML element.

4. **Settings & Overlays:**
   - Implement a simple settings menu to control stream quality, bitrate, and resolution.
   - Ensure the UI gracefully handles fullscreen requests and pointer locks when a stream starts.

5. **Testing:**
   - Perform a full end-to-end test: Login -> Browse Library -> Launch Game -> Play in Browser.
   - Verify that inputs are correctly transmitted and video plays smoothly.
