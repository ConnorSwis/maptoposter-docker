import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    base_dir: str
    poster_dir: str
    cache_refresh_seconds: int


def load_config() -> AppConfig:
    base_dir = os.getcwd()
    poster_dir = os.path.join(base_dir, "posters")
    cache_refresh_seconds = int(os.getenv("CACHE_REFRESH_SECONDS", "60"))
    return AppConfig(
        base_dir=base_dir,
        poster_dir=poster_dir,
        cache_refresh_seconds=cache_refresh_seconds,
    )
