# Custom Modals System

To maintain fullscreen illusions and match the application theme, system popups (`alert`, `confirm`, `prompt`) have been replaced with a unified `CustomModals` system.

## Usage

The `CustomModals` system is available globally on `window.CustomModals`. It provides asynchronous alternatives to standard system popups.

Since these modals return Promises, you must use `await` when calling them.

### `alert`

Displays a message to the user with an "OK" button.

```javascript
await window.CustomModals.alert("Action completed successfully.", "Success");
```

### `confirm`

Asks the user to confirm an action, returning `true` or `false`.

```javascript
const userAgreed = await window.CustomModals.confirm("Are you sure you want to delete this item?");
if (!userAgreed) return;
```

### `prompt`

Requests input from the user, returning the input string or `null` if cancelled.

```javascript
const newName = await window.CustomModals.prompt("Enter new name:", "default_name.txt", "Rename File");
if (!newName) return;
```

## Implementation Details

The implementation injects a single instance of the `modals.js` script into the head of pages. The script dynamically creates DOM elements for the overlay and dialog, leveraging standard CSS variables (`--bg-core`, `--text-color`, `--brand-color`) to automatically conform to the active theme.

## Best Practices

* **Always `await`**: These functions are asynchronous. Failing to await them will lead to race conditions where the modal is displayed, but code execution continues instantly.
* **Fallback for Native Popups**: All uses of native `alert()`, `confirm()`, and `prompt()` within the application should be replaced with `window.CustomModals` equivalents.
