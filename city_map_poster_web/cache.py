import json
import subprocess
import threading
import time
from dataclasses import dataclass

from .config import AppConfig


@dataclass
class CacheState:
    lock: threading.Lock
    features: list[dict[str, str]]
    themes: list[dict[str, str]]
    last_refresh_ts: float | None


def create_cache_state() -> CacheState:
    return CacheState(
        lock=threading.Lock(), features=[], themes=[], last_refresh_ts=None
    )


def _run_list_cmd(logger, args: list[str]) -> str:
    """
    Runs `python create_map_poster.py ...` and returns stdout.
    Logs stderr on failure and returns "" so callers can keep last good cache.
    """
    cmd = ["python", "create_map_poster.py", *args]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return (result.stdout or "").strip()
    except subprocess.CalledProcessError as e:
        logger.warning(
            "List command failed (%s): %s",
            " ".join(cmd),
            (e.stderr or e.stdout or str(e)).strip(),
        )
        return ""
    except Exception as e:
        logger.warning("List command errored (%s): %s", " ".join(cmd), e)
        return ""


def _parse_features(stdout: str) -> list[dict[str, str]]:
    if not stdout:
        return []
    parts = stdout.split(", ")
    out: list[dict[str, str]] = []
    for p in parts:
        if ": " not in p:
            continue
        fid, name = p.split(": ", 1)
        out.append({"id": fid.strip(), "name": name.strip()})
    return out


def _parse_themes(stdout: str) -> list[dict[str, str]]:
    if not stdout:
        return []
    try:
        raw = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id", "")).strip()
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        if not tid or not name:
            continue
        out.append({"id": tid, "name": name, "description": description})
    return out


def refresh_cache_once(config: AppConfig, state: CacheState, logger) -> None:
    """
    Fetch themes/features once and update globals if parsing yields something.
    If a fetch fails, we keep the last good cached value.
    """
    features_out = _run_list_cmd(logger, ["--list-features"])
    themes_out = _run_list_cmd(logger, ["--list-themes"])

    new_features = _parse_features(features_out)
    new_themes = _parse_themes(themes_out)

    with state.lock:
        if new_features:
            state.features = new_features
        if new_themes:
            state.themes = new_themes
        state.last_refresh_ts = time.time()

    logger.info(
        "Cache refreshed. features=%d themes=%d",
        len(state.features),
        len(state.themes),
    )


def start_cache_refresher(
    config: AppConfig,
    state: CacheState,
    logger,
    *,
    start_immediately: bool = True,
) -> None:
    """
    Start the background refresher thread exactly once.
    """

    def _loop():
        if start_immediately:
            refresh_cache_once(config, state, logger)
        while True:
            time.sleep(config.cache_refresh_seconds)
            refresh_cache_once(config, state, logger)

    t = threading.Thread(target=_loop, daemon=True, name="cache-refresher")
    t.start()
