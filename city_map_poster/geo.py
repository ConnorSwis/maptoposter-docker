from __future__ import annotations
import time
import osmnx as ox
from shapely.geometry import Point
import asyncio
from geopy.geocoders import Nominatim
from .cache import cache_get, cache_set, CacheError
from .logger import get_logger

logger = get_logger()


def get_coordinates(city, country):
    """
    Fetches coordinates for a given city and country using geopy.
    Includes rate limiting to be respectful to the geocoding service.
    """
    coords = f"coords_{city.lower()}_{country.lower()}"
    cached = cache_get(coords)
    if cached:
        logger.info("Using cached coordinates for %s, %s", city, country)
        return cached

    logger.info("Looking up coordinates...")
    geolocator = Nominatim(user_agent="city_map_poster", timeout=10)  # type: ignore

    # Add a small delay to respect Nominatim's usage policy
    time.sleep(1)

    try:
        location = geolocator.geocode(f"{city}, {country}")
    except Exception as e:
        raise ValueError(f"Geocoding failed for {city}, {country}: {e}")

    # If geocode returned a coroutine in some environments, run it to get the result.
    if asyncio.iscoroutine(location):
        try:
            location = asyncio.run(location)
        except RuntimeError:
            # If an event loop is already running, try using it to complete the coroutine.
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Running event loop in the same thread; raise a clear error.
                raise RuntimeError(
                    "Geocoder returned a coroutine while an event loop is already running. Run this script in a synchronous environment."
                )
            location = loop.run_until_complete(location)

    if location:
        # Use getattr to safely access address (helps static analyzers)
        addr = getattr(location, "address", None)
        if addr:
            logger.info("Found: %s", addr)
        else:
            logger.info("Found location (address not available)")
        logger.info("Coordinates: %s, %s", location.latitude, location.longitude)
        try:
            cache_set(coords, (location.latitude, location.longitude))
        except CacheError as e:
            logger.warning("Cache write failed: %s", e)
        return (location.latitude, location.longitude)
    else:
        raise ValueError(f"Could not find coordinates for {city}, {country}")


def get_crop_limits(G_proj, center_lat_lon, fig, dist):
    """
    Crop inward to preserve aspect ratio while guaranteeing
    full coverage of the requested radius.
    """
    lat, lon = center_lat_lon

    # Project center point into graph CRS
    center = ox.projection.project_geometry(
        Point(lon, lat), crs="EPSG:4326", to_crs=G_proj.graph["crs"]
    )[0]
    center_x, center_y = center.x, center.y

    fig_width, fig_height = fig.get_size_inches()
    aspect = fig_width / fig_height

    # Start from the *requested* radius
    half_x = dist
    half_y = dist

    # Cut inward to match aspect
    if aspect > 1:  # landscape → reduce height
        half_y = half_x / aspect
    else:  # portrait → reduce width
        half_x = half_y * aspect

    return (
        (center_x - half_x, center_x + half_x),
        (center_y - half_y, center_y + half_y),
    )
