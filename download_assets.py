import os
import urllib.request
import re

ASSETS_DIR = "web/assets"
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")
STYLE_CSS = os.path.join(ASSETS_DIR, "style.css")

os.makedirs(FONTS_DIR, exist_ok=True)

def download_file(url, filename):
    print(f"Downloading {filename}...")
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            with open(os.path.join(FONTS_DIR, filename), "wb") as f:
                f.write(response.read())
        return True
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return False

# 1. Material Symbols
print("Fetching Material Symbols CSS...")
try:
    # Use a User-Agent to ensure we get woff2
    req = urllib.request.Request(
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0",
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    )
    with urllib.request.urlopen(req) as response:
        css_content = response.read().decode('utf-8')
        # Extract url(...)
        match = re.search(r'src:\s*url\((https://[^)]+)\)', css_content)
        if match:
            font_url = match.group(1)
            download_file(font_url, "MaterialSymbolsOutlined.woff2")
        else:
            print("Could not find Material Symbols URL")
except Exception as e:
    print(f"Error fetching Material Symbols: {e}")


# 2. Inter & JetBrains Mono (from jsdelivr/fontsource)
fonts_to_download = [
    ("https://cdn.jsdelivr.net/npm/@fontsource/inter@5.0.15/files/inter-latin-400-normal.woff2", "Inter-Regular.woff2"),
    ("https://cdn.jsdelivr.net/npm/@fontsource/inter@5.0.15/files/inter-latin-600-normal.woff2", "Inter-SemiBold.woff2"),
    ("https://cdn.jsdelivr.net/npm/@fontsource/jetbrains-mono@5.0.15/files/jetbrains-mono-latin-400-normal.woff2", "JetBrainsMono-Regular.woff2"),
    ("https://cdn.jsdelivr.net/npm/@fontsource/jetbrains-mono@5.0.15/files/jetbrains-mono-latin-700-normal.woff2", "JetBrainsMono-Bold.woff2"),
]

for url, name in fonts_to_download:
    download_file(url, name)

# Generate style.css
css_content = """/* Local Fonts */

@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 400;
    src: url('fonts/Inter-Regular.woff2') format('woff2');
}

@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 600;
    src: url('fonts/Inter-SemiBold.woff2') format('woff2');
}

@font-face {
    font-family: 'JetBrains Mono';
    font-style: normal;
    font-weight: 400;
    src: url('fonts/JetBrainsMono-Regular.woff2') format('woff2');
}

@font-face {
    font-family: 'JetBrains Mono';
    font-style: normal;
    font-weight: 700;
    src: url('fonts/JetBrainsMono-Bold.woff2') format('woff2');
}

@font-face {
  font-family: 'Material Symbols Outlined';
  font-style: normal;
  font-weight: 400;
  src: url('fonts/MaterialSymbolsOutlined.woff2') format('woff2');
}

.material-symbols-outlined {
  font-family: 'Material Symbols Outlined';
  font-weight: normal;
  font-style: normal;
  font-size: 24px;
  display: inline-block;
  line-height: 1;
  text-transform: none;
  letter-spacing: normal;
  word-wrap: normal;
  white-space: nowrap;
  direction: ltr;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
  -moz-osx-font-smoothing: grayscale;
  font-feature-settings: 'liga';
}
"""

with open(STYLE_CSS, "w") as f:
    f.write(css_content)

print("Assets downloaded and configured.")
