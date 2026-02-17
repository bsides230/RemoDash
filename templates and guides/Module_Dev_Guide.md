# RemoDash Module Development Guide

RemoDash is designed to be extensible. Modules are simply web pages (HTML/JS/CSS) loaded inside **iframes** within the dashboard.

This architecture ensures:
1.  **Isolation**: Modules cannot crash the main dashboard.
2.  **Flexibility**: Modules can be written in vanilla JS, React, Vue, or anything that compiles to HTML.
3.  **Security**: The backend API is the only bridge to the system.

---

## 1. The Basics

A module is just an `.html` file located in the `web/modules/` directory.

To register a new module:
1.  Place your `MyModule.html` in `web/modules/`.
2.  Add an entry to the `MODULE_REGISTRY` in `web/dashboard.html` (in the `<script>` section):
    ```javascript
    { id: "mod_mymodule", file: "MyModule.html", name: "My Module", icon: "🚀" },
    ```
    *Note: In future versions, this registry might be externalized.*

---

## 2. styling & Theming

To ensure your module looks native to RemoDash, **do not hardcode colors**. Use the CSS variables provided by the dashboard.

When your iframe loads, the dashboard will inject the current theme (Light/Dark), font size, and accent color.

### Core Variables

| Variable | Description |
| :--- | :--- |
| `--bg-core` | Main background (e.g., `#050505` or `#eef0f4`) |
| `--bg-panel` | Panel/Window background |
| `--bg-input` | Input field background |
| `--text-head` | Heading text color (High contrast) |
| `--text-body` | Standard text color |
| `--text-dim` | Dimmed/Label text color |
| `--border-color` | Border color |
| `--brand-color` | The user's chosen accent color (Emerald, Blue, etc.) |
| `--brand-color-dim` | Low opacity version of accent color (approx 10%) |
| `--font-size-base` | Base font size (controlled by user slider) |
| `--error-color` | Standard error red |

*Deprecated:* `--brand-purple` (use `--brand-color`), `--brand-purple-dim` (use `--brand-color-dim`).

### Font Family
The dashboard loads `Inter` and `JetBrains Mono`. You can use:
```css
font-family: 'Inter', sans-serif;
font-family: 'JetBrains Mono', monospace;
```

---

## 3. Communication (Messaging)

Modules communicate with the Core Dashboard via `window.parent.postMessage`.

### Sending Messages to Dashboard

**1. Open a Child Window (Popup)**
```javascript
window.parent.postMessage({
    type: 'OPEN_CHILD_WINDOW',
    id: 'my_child_window', // Unique ID
    title: 'My Child Window',
    url: 'modules/MyChild.html',
    parentId: 'win_mod_mymodule', // Your window ID (optional)
    canMinimize: true
}, '*');
```

**2. Open a Terminal Tab**
```javascript
window.parent.postMessage({
    type: 'OPEN_TERMINAL_TAB',
    cwd: '/home/user', // Optional working directory
    command: 'ls -la'   // Optional initial command
}, '*');
```

**3. Close Dashboard (Kiosk Mode)**
```javascript
window.parent.postMessage({ type: 'CLOSE_DASHBOARD' }, '*');
```

### Receiving Messages from Dashboard

You should set up a `message` listener to handle updates from the core.

**Primary Theme Message (Recommended)**

```javascript
        // Helper to load theme CSS
        function loadThemeCSS(url) {
            let link = document.getElementById('theme-css');
            if (!link) {
                link = document.createElement('link');
                link.id = 'theme-css';
                link.rel = 'stylesheet';
                document.head.appendChild(link);
            }
            link.href = url;
        }

        function clearThemeCSS() {
            const link = document.getElementById('theme-css');
            if (link) link.remove();
        }

        window.addEventListener('message', (e) => {
            const data = e.data;

            if (data.type === 'THEME_UPDATE') {
                // Apply Base Theme Mode
                document.body.setAttribute('data-theme', data.theme);

                // Apply Accent Color
                document.documentElement.style.setProperty('--brand-color', data.brandColor);

                // Derive Dim Color (Optional, usually handled by CSS variables if hex)
                const hex = data.brandColor.replace('#', '');
                const r = parseInt(hex.substring(0,2), 16);
                const g = parseInt(hex.substring(2,4), 16);
                const b = parseInt(hex.substring(4,6), 16);
                document.documentElement.style.setProperty('--brand-color-dim', `rgba(${r},${g},${b}, 0.1)`);

                // Apply Font Size
                document.documentElement.style.setProperty('--font-size-base', data.fontSize + 'px');

                // Load Theme Preset CSS (Dynamic Variables)
                if (data.themeCssUrl) {
                    loadThemeCSS(data.themeCssUrl);
                } else {
                    clearThemeCSS();
                }
            }

            // ... handle other messages ...
        });
```

**Legacy Messages (Deprecated)**
*Supported for backward compatibility, but use `THEME_UPDATE` for new modules.*

*   `THEME_CHANGE`: Only sends dark/light mode.
*   `COLOR_CHANGE`: Only sends accent color.
*   `FONT_CHANGE`: Only sends font size.

**System Messages**

*   `TOKEN_UPDATE`: Sends Admin Token.
*   `CORE_URL_CHANGE`: Sends Backend URL.

---

## 4. API Authentication

Most RemoDash modules need to talk to the backend (`server.py`).

1.  Wait for the `TOKEN_UPDATE` and `CORE_URL_CHANGE` messages on load.
2.  Use the token in the `X-Token` header.

```javascript
async function fetchData() {
    if (!window.authToken) return;

    const res = await fetch(`${window.coreUrl}/api/my-endpoint`, {
        headers: {
            'X-Token': window.authToken
        }
    });
    const json = await res.json();
    console.log(json);
}
```

---

## 5. Best Practices

*   **Responsive**: Modules may be resized or viewed on mobile. Use percentages or flexbox.
*   **No Scroll**: The body should generally have `overflow: hidden`. Create a specific scrollable container content area.
*   **Single File**: If possible, keep CSS and JS inside the HTML file to make distribution easier.
