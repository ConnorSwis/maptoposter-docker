from __future__ import annotations

import time
import math
from typing import cast

import osmnx as ox
from geopandas import GeoDataFrame
from networkx import MultiDiGraph

from .cache import cache_get, cache_set, CacheError
from .logger import get_logger

logger = get_logger()


def fetch_graph(point, dist) -> MultiDiGraph | None:
    lat, lon = point
    graph = f"graph_{lat}_{lon}_{dist}"
    cached = cache_get(graph)
    if cached is not None:
        logger.info("Using cached street network")
        return cast(MultiDiGraph, cached)

    try:
        G = ox.graph_from_point(
            point,
            dist=dist,
            dist_type="bbox",
            network_type="all",
            truncate_by_edge=True,
        )
        # Rate limit between requests
        time.sleep(0.5)
        try:
            cache_set(graph, G)
        except CacheError as e:
            logger.warning("Cache write failed: %s", e)
        return G
    except Exception as e:
        logger.error("OSMnx error while fetching graph: %s", e)
        return None


def fetch_features(
    point: tuple[float, float],
    dist: float,
    tags: dict,
    name: str,
) -> GeoDataFrame | None:
    lat, lon = point
    tag_str = "_".join(tags.keys())
    key = f"{name}_{lat}_{lon}_{dist}_{tag_str}"
    cached = cache_get(key)
    if cached is not None:
        logger.info("Using cached %s", name)
        return cast(GeoDataFrame, cached)

    try:
        data = ox.features_from_point(point, tags=tags, dist=dist)
        time.sleep(0.3)
        try:
            cache_set(key, data)
        except CacheError as e:
            logger.warning("Cache write failed: %s", e)
        return data
    except Exception as e:
        logger.error(
            f"OSMnx error while fetching features: {'parameters': {'point': point, 'dist': dist, 'tags': tags}, 'message': {e}}"
        )
        return None
