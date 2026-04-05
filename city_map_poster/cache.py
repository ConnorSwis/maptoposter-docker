from __future__ import annotations

import os
import pickle
from pathlib import Path
from typing import Any

from .config import CACHE_DIR


class CacheError(Exception):
    """Raised when a cache operation fails."""

    pass


def _cache_path(key: str) -> Path:
    safe = key.replace(os.sep, "_")
    return CACHE_DIR / f"{safe}.pkl"


def cache_get(key: str) -> Any | None:
    try:
        path = _cache_path(key)
        if not path.exists():
            return None
        with path.open("rb") as f:
            return pickle.load(f)
    except Exception as e:
        raise CacheError(f"Cache read failed: {e}") from e


def cache_set(key: str, value: Any) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(key)
        with path.open("wb") as f:
            pickle.dump(value, f, protocol=pickle.HIGHEST_PROTOCOL)
    except Exception as e:
        raise CacheError(f"Cache write failed: {e}") from e
