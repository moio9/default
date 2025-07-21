import json
import os
from pathlib import Path

# === XDG Base Directory Spec ===
XDG_CONFIG_HOME = Path(os.getenv('XDG_CONFIG_HOME', Path.home() / '.config'))
CONFIG_DIR = XDG_CONFIG_HOME / 'shortcut_launcher'
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

PREFIXES_FILE = CONFIG_DIR / 'wine_prefixes.json'

# Repository URLs
TEMPLATE_REPO = "https://github.com/moio9/barrel"
APP_REPO = "https://github.com/moio9/barrel"

def load_prefixes():
    if not PREFIXES_FILE.exists():
        return []
    with open(PREFIXES_FILE, "r") as f:
        return json.load(f)

def save_prefixes(prefixes):
    with open(PREFIXES_FILE, "w") as f:
        json.dump(prefixes, f, indent=4)
