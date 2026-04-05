from __future__ import annotations

import json
from typing import Dict

from .config import THEMES_DIR, DEFAULT_THEME_NAME
from .logger import get_logger

logger = get_logger()

Theme = Dict[str, str]


def get_available_themes() -> list[dict]:
    if not THEMES_DIR.exists():
        THEMES_DIR.mkdir(parents=True, exist_ok=True)
        return []

    themes: list[dict] = []
    for file in sorted(THEMES_DIR.iterdir()):
        if file.suffix == ".json":
            with file.open("r", encoding="utf-8") as f:
                theme = json.load(f)
                themes.append(
                    {
                        "id": file.stem,
                        "name": theme.get("name", "Unknown Theme"),
                        "description": theme.get(
                            "description", "No description available."
                        ),
                    }
                )
    return themes


def default_theme() -> Theme:
    return {
        "name": "Feature-Based Shading",
        "description": "A simple theme that colors map features based on their type.",
        "bg": "#FFFFFF",
        "text": "#000000",
        "gradient_color": "#FFFFFF",
        "water": "#C0C0C0",
        "parks": "#F0F0F0",
        "road_motorway": "#0A0A0A",
        "road_primary": "#1A1A1A",
        "road_secondary": "#2A2A2A",
        "road_tertiary": "#3A3A3A",
        "road_residential": "#4A4A4A",
        "road_default": "#3A3A3A",
    }


def load_theme(theme_name: str = DEFAULT_THEME_NAME) -> Theme:
    theme_file = THEMES_DIR / f"{theme_name}.json"

    if not theme_file.exists():
        logger.warning(
            "Theme file '%s' not found. Using default feature_based theme.", theme_file
        )
        return default_theme()

    with theme_file.open("r", encoding="utf-8") as f:
        theme = json.load(f)

    logger.info("Loaded theme: %s", theme.get("name", theme_name))
    if "description" in theme:
        logger.info("%s", theme["description"])
    return theme
