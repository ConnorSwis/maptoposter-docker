from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import FONTS_DIR
from .logger import get_logger

logger = get_logger()


@dataclass(frozen=True)
class FontPaths:
    bold: Path
    regular: Path
    light: Path


def load_fonts() -> FontPaths | None:
    fonts = FontPaths(
        bold=FONTS_DIR / "Roboto-Bold.ttf",
        regular=FONTS_DIR / "Roboto-Regular.ttf",
        light=FONTS_DIR / "Roboto-Light.ttf",
    )

    missing = [p for p in (fonts.bold, fonts.regular, fonts.light) if not p.exists()]
    if missing:
        for p in missing:
            logger.warning("Font not found: %s", p)
        return None

    return fonts
