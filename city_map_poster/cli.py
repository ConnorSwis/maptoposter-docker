from __future__ import annotations

import argparse
import sys
import json

from .themes import get_available_themes, load_theme
from .geo import get_coordinates
from .poster import build_default_features, create_poster, generate_output_filename
from .config import (
    DEFAULT_THEME_NAME,
    DEFAULT_DISTANCE_M,
    DEFAULT_WIDTH_IN,
    DEFAULT_HEIGHT_IN,
)
from .logger import get_logger

# import osmnx as ox

# ox.settings.log_console = True
# ox.settings.use_cache = True

logger = get_logger()


def print_examples() -> None:
    feature_keys = ", ".join(_get_feature_keys())
    logger.info(
        f"""
City Map Poster Generator
=========================

Usage:
  python create_map_poster.py --city <city> --country <country> [options]

Examples:
  python create_map_poster.py -c "New York" -C "USA" -t noir -d 12000
  python create_map_poster.py -c "Barcelona" -C "Spain" -t warm_beige -d 8000
  python create_map_poster.py -c "Tokyo" -C "Japan" -t japanese_ink -d 15000

Options:
  --city, -c        City name (required)
  --country, -C     Country name (required)
  --country-label   Override country text displayed on poster
  --theme, -t       Theme name (default: feature_based)
  --all-themes      Generate posters for all themes
  --distance, -d    Map radius in meters (default: 29000)
  --lat             Override center latitude (requires --lon)
  --lon             Override center longitude (requires --lat)
  --star-lat        Place a star at latitude (requires --star-lon)
  --star-lon        Place a star at longitude (requires --star-lat)
  --enable-features Comma-separated feature keys to enable (repeatable)
  --disable-features Comma-separated feature keys to disable (repeatable)
                   Available: {feature_keys}
  --list-themes     List all available themes
  --format, -f      png|svg|pdf (default: png)
"""
    )


def list_themes() -> None:
    available = get_available_themes()
    if not available:
        logger.warning("No themes found in 'themes/' directory.")
        return
    sys.stdout.write(json.dumps(available) + "\n")


def list_features() -> None:
    features = build_default_features()
    if not features:
        logger.warning("No features available.")
        return

    for feat in features[:-1]:
        sys.stdout.write(f"{feat.key}: {feat.display_name}, ")
    sys.stdout.write(f"{features[-1].key}: {features[-1].display_name}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate beautiful map posters for any city",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--city", "-c", type=str, help="City name")
    parser.add_argument("--country", "-C", type=str, help="Country name")
    parser.add_argument(
        "--country-label",
        dest="country_label",
        type=str,
        help="Override country text displayed on poster",
    )
    parser.add_argument(
        "--theme",
        "-t",
        type=str,
        default=DEFAULT_THEME_NAME,
        help=f"Theme name (default: {DEFAULT_THEME_NAME})",
    )
    parser.add_argument(
        "--all-themes",
        dest="all_themes",
        action="store_true",
        help="Generate posters for all themes",
    )
    parser.add_argument(
        "--distance",
        "-d",
        type=int,
        default=DEFAULT_DISTANCE_M,
        help=f"Map radius in meters (default: {DEFAULT_DISTANCE_M})",
    )
    parser.add_argument(
        "--lat",
        type=float,
        help="Override center latitude (requires --lon)",
    )
    parser.add_argument(
        "--lon",
        type=float,
        help="Override center longitude (requires --lat)",
    )
    parser.add_argument(
        "--star-lat",
        dest="star_lat",
        type=float,
        help="Place a star at latitude (requires --star-lon)",
    )
    parser.add_argument(
        "--star-lon",
        dest="star_lon",
        type=float,
        help="Place a star at longitude (requires --star-lat)",
    )
    parser.add_argument(
        "--enable-features",
        dest="enable_features",
        action="append",
        help=(
            "Comma-separated feature keys to enable (repeatable). "
            "Use --disable-features to turn off defaults."
        ),
    )
    parser.add_argument(
        "--disable-features",
        dest="disable_features",
        action="append",
        help="Comma-separated feature keys to disable (repeatable)",
    )
    parser.add_argument(
        "--width",
        "-W",
        type=float,
        default=DEFAULT_WIDTH_IN,
        help=f"Image width in inches (default: {DEFAULT_WIDTH_IN})",
    )
    parser.add_argument(
        "--height",
        "-H",
        type=float,
        default=DEFAULT_HEIGHT_IN,
        help=f"Image height in inches (default: {DEFAULT_HEIGHT_IN})",
    )
    parser.add_argument(
        "--list-themes", action="store_true", help="List all available themes"
    )
    parser.add_argument(
        "--format",
        "-f",
        default="png",
        choices=["png", "svg", "pdf"],
        help="Output format for the poster (default: png)",
    )

    parser.add_argument(
        "--list-features", action="store_true", help="List all available features"
    )

    return parser


def _get_feature_keys() -> list[str]:
    return [feat.key for feat in build_default_features()]


def _parse_feature_list(values: list[str] | None) -> list[str]:
    if not values:
        return []
    items: list[str] = []
    for raw in values:
        for part in raw.split(","):
            key = part.strip()
            if key:
                items.append(key)
    return items


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if len(sys.argv) == 1:
        print_examples()
        return 0

    if args.list_themes:
        list_themes()
        return 0

    if args.list_features:
        list_features()
        return 0

    if not args.city or not args.country:
        logger.error("Error: --city and --country are required.")
        print_examples()
        return 1

    available = get_available_themes()
    if not available:
        logger.error("No themes found in 'themes/' directory.")
        return 1

    if args.all_themes:
        themes_to_generate = [t["id"] for t in available]
    else:
        if args.theme not in [t["id"] for t in available]:
            logger.error("Error: Theme '%s' not found.", args.theme)
            logger.error(available)
            return 1
        themes_to_generate = [args.theme]

    enabled_features: dict[str, bool] | None = None
    enable_list = _parse_feature_list(args.enable_features)
    disable_list = _parse_feature_list(args.disable_features)
    if enable_list or disable_list:
        feature_keys = _get_feature_keys()
        unknown = sorted(set(enable_list + disable_list).difference(set(feature_keys)))
        if unknown:
            logger.error("Error: Unknown feature key(s): %s", ", ".join(unknown))
            logger.error("Available features: %s", ", ".join(feature_keys))
            return 1
        conflicts = sorted(set(enable_list).intersection(set(disable_list)))
        if conflicts:
            logger.error(
                "Error: Features can't be both enabled and disabled: %s",
                ", ".join(conflicts),
            )
            return 1
        enabled_features = {key: True for key in enable_list}
        enabled_features.update({key: False for key in disable_list})

    logger.info("=" * 50)
    logger.info("City Map Poster Generator")
    logger.info("=" * 50)

    if (args.lat is None) ^ (args.lon is None):
        logger.error("Error: --lat and --lon must be provided together.")
        return 1
    if args.lat is not None and args.lon is not None:
        coords = (args.lat, args.lon)
        logger.info("Using custom coordinates: %s, %s", args.lat, args.lon)
    else:
        coords = get_coordinates(args.city, args.country)

    if (args.star_lat is None) ^ (args.star_lon is None):
        logger.error("Error: --star-lat and --star-lon must be provided together.")
        return 1
    star_point = None
    if args.star_lat is not None and args.star_lon is not None:
        star_point = (args.star_lat, args.star_lon)
        logger.info("Placing star at: %s, %s", args.star_lat, args.star_lon)

    for theme_name in themes_to_generate:
        theme = load_theme(theme_name)
        output_file = generate_output_filename(args.city, theme_name, args.format)
        create_poster(
            city=args.city,
            country=args.country,
            point=coords,
            star_point=star_point,
            dist=args.distance,
            output_file=output_file,
            output_format=args.format,
            width=args.width,
            height=args.height,
            country_label=args.country_label,
            theme=theme,
            enabled_features=enabled_features,
        )

    logger.info("=" * 50)
    logger.info("Poster generation complete!")
    logger.info("=" * 50)
    return 0
