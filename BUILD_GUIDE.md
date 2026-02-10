# Module Developer Guide

This guide explains how to create and distribute modules for RemoDash.

## Structure

A RemoDash module is a ZIP file (renamed to `.mdpk`) containing the following structure:

```
my_module.mdpk
├── module.json        (Required: Metadata)
├── api.py             (Optional: Backend Logic)
├── requirements.txt   (Optional: Python Dependencies)
└── web/               (Optional: Frontend Assets)
    ├── index.html     (Entry point)
    ├── style.css
    └── script.js
```

### 1. `module.json`

This file defines your module's identity.

```json
{
  "id": "my_weather_plugin",
  "name": "Weather Widget",
  "description": "Displays current weather",
  "version": "1.0.0",
  "author": "Your Name",
  "icon": "sunny",   // Material Symbol name
  "enabled": true
}
```

### 2. `api.py`

This file handles backend logic. You must expose a FastAPI `APIRouter` named `router`.

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("/current")
async def get_weather():
    return {"temp": 72, "condition": "Sunny"}
```

This endpoint will be available at `/api/modules/my_weather_plugin/current`.

### 3. Frontend (`web/`)

The contents of the `web/` directory are served at `/modules/my_weather_plugin/`.

The dashboard loads `web/index.html` into an `<iframe>` or injects it depending on the implementation.
For now, assume it's loaded as a standalone page inside a dashboard widget.

**Example `web/index.html`:**
```html
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: sans-serif; padding: 10px; }
    </style>
</head>
<body>
    <h3>Weather</h3>
    <div id="temp">Loading...</div>

    <script>
        fetch('/api/modules/my_weather_plugin/current')
            .then(res => res.json())
            .then(data => {
                document.getElementById('temp').innerText = `${data.temp}°F ${data.condition}`;
            });
    </script>
</body>
</html>
```

### 4. Packaging

1. Create your folder with the structure above.
2. Zip the contents (not the parent folder itself).
3. Rename the `.zip` file to `.mdpk`.

## Installation

Use the `wizard_module.py` tool to install your `.mdpk` file.

```bash
python3 wizard_module.py
```
Select option `2. Install Module`.

## Development Tips

- **Hot Reloading:** During development, you can work directly in `modules/your_module/`. Changes to `web/` files are instant. Changes to `api.py` require a server restart.
- **Dependencies:** List PyPI packages in `requirements.txt`. The installer will run `pip install -r requirements.txt`.
