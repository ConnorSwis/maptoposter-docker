from __future__ import annotations

import os
from pathlib import Path

# Project folders (relative to where you run the script)
THEMES_DIR = Path(os.environ.get("THEMES_DIR", "city_map_poster/themes"))
FONTS_DIR = Path(os.environ.get("FONTS_DIR", "city_map_poster/fonts"))
POSTERS_DIR = Path(os.environ.get("POSTERS_DIR", "posters"))

# Cache (default ".cache")
CACHE_DIR = Path(os.environ.get("CACHE_DIR", "city_map_poster/.cache"))

# Defaults
DEFAULT_THEME_NAME = "feature_based"
DEFAULT_DISTANCE_M = 29000
DEFAULT_WIDTH_IN = 12.0
DEFAULT_HEIGHT_IN = 16.0
MAX_POSTERS = int(os.environ.get("MAX_POSTERS", "4"))

# Ensure dirs exist where it makes sense
CACHE_DIR.mkdir(parents=True, exist_ok=True)
POSTERS_DIR.mkdir(parents=True, exist_ok=True)
THEMES_DIR.mkdir(parents=True, exist_ok=True)
