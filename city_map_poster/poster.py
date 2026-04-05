from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import osmnx as ox
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from matplotlib.font_manager import FontProperties
from shapely.geometry import Point

from .config import MAX_POSTERS, POSTERS_DIR
from .fonts import load_fonts
from .geo import get_crop_limits
from .osm import fetch_graph
from .render import (
    create_gradient_fade,
    get_edge_colors_by_type,
    get_edge_widths_by_type,
)
from .features import FeatureState, build_default_features
from .logger import get_logger


FONTS = load_fonts()
logger = get_logger()


def generate_output_filename(city: str, theme_name: str, output_format: str) -> Path:
    POSTERS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    city_slug = city.lower().replace(" ", "_")
    ext = output_format.lower()
    filename = f"{city_slug}_{theme_name}_{timestamp}.{ext}"
    return POSTERS_DIR / filename


# -----------------------------
# Data shapes
# -----------------------------
@dataclass(frozen=True)
class PosterData:
    city: str
    country: str
    point: tuple[float, float]
    star_point: tuple[float, float] | None
    dist: int
    width: float
    height: float
    compensated_dist: float

    # projected street graph + features dict
    G_proj: Any
    features: dict[str, "FeatureState"]

    # precomputed draw params for roads
    edge_colors: list[Any]
    edge_widths: list[float]
    # computed cropping bounds (projected CRS units)
    crop_xlim: tuple[float, float]
    crop_ylim: tuple[float, float]


@dataclass(frozen=True)
class PosterMeta:
    spaced_city: str
    country_text: str
    coords_text: str


@dataclass(frozen=True)
class PosterResult:
    output_file: Path
    output_format: str
    meta: PosterMeta


# -----------------------------
# Step 1: Gather data
# -----------------------------
def gather_poster_data(
    *,
    city: str,
    country: str,
    point: tuple[float, float],
    star_point: tuple[float, float] | None,
    dist: int,
    width: float,
    height: float,
    theme: dict[str, str],
    enabled_features: dict[str, bool] | None = None,
) -> PosterData:
    """
    Fetch OSM data and transform it into a 'ready to render' shape.
    This keeps network calls, projections, and precomputation out of rendering.
    """
    compensated_dist = float(dist)

    logger.info("Downloading street network...")
    G = fetch_graph(point, compensated_dist)
    if G is None:
        raise RuntimeError("Failed to retrieve street network data.")

    # Project the graph once; everything else follows its CRS
    G_proj = ox.project_graph(G)
    graph_crs = G_proj.graph.get("crs")

    # Build and process enabled features (fetch -> project -> precompute)
    features: dict[str, FeatureState] = {}
    for feat in build_default_features(enabled_overrides=enabled_features):
        if not getattr(feat, "enabled", True):
            # still record the key so downstream code can rely on presence
            features[feat.key] = FeatureState(gdf_proj=None, draw={})
            continue

        try:
            raw = feat.fetch(point, compensated_dist)
        except Exception:
            logger.warning("Failed to fetch %s data; skipping.", feat.name)
            raw = None

        proj = feat.project(raw, graph_crs=graph_crs)
        draw = feat.precompute(proj, dist=compensated_dist)
        features[feat.key] = FeatureState(gdf_proj=proj, draw=draw)

    # Precompute road styling
    edge_colors = get_edge_colors_by_type(G_proj, theme)
    edge_widths = get_edge_widths_by_type(G_proj, compensated_dist)

    # Need a figure to compute crop limits (uses fig geometry)
    tmp_fig, _ = plt.subplots(figsize=(width, height))
    try:
        crop_xlim, crop_ylim = get_crop_limits(G_proj, point, tmp_fig, compensated_dist)
    finally:
        plt.close(tmp_fig)

    return PosterData(
        city=city,
        country=country,
        point=point,
        star_point=star_point,
        dist=dist,
        width=width,
        height=height,
        compensated_dist=compensated_dist,
        G_proj=G_proj,
        features=features,
        edge_colors=edge_colors,
        edge_widths=edge_widths,
        crop_xlim=crop_xlim,
        crop_ylim=crop_ylim,
    )


# -----------------------------
# Step 2: Render figure
# -----------------------------
def _build_fonts(*, width: float) -> dict[str, FontProperties]:
    scale_factor = width / 12.0
    BASE_MAIN, BASE_SUB, BASE_COORDS, BASE_ATTR = 60, 22, 14, 8

    if FONTS:
        return {
            "main": FontProperties(
                fname=str(FONTS.bold), size=BASE_MAIN * scale_factor
            ),
            "sub": FontProperties(fname=str(FONTS.light), size=BASE_SUB * scale_factor),
            "coords": FontProperties(
                fname=str(FONTS.regular), size=BASE_COORDS * scale_factor
            ),
            "attr": FontProperties(
                fname=str(FONTS.light), size=BASE_ATTR * scale_factor
            ),
        }

    return {
        "main": FontProperties(
            family="monospace", weight="bold", size=BASE_MAIN * scale_factor
        ),
        "sub": FontProperties(
            family="monospace", weight="normal", size=BASE_SUB * scale_factor
        ),
        "coords": FontProperties(family="monospace", size=BASE_COORDS * scale_factor),
        "attr": FontProperties(family="monospace", size=BASE_ATTR * scale_factor),
    }


def _adjust_main_font_for_city(
    font_main: FontProperties, *, city: str, width: float
) -> FontProperties:
    # Match your prior behavior but make it a pure helper
    scale_factor = width / 12.0
    BASE_MAIN = 60
    base_adjusted_main = BASE_MAIN * scale_factor

    if len(city) > 10:
        length_factor = 10 / len(city)
        adjusted_font_size = max(base_adjusted_main * length_factor, 10 * scale_factor)
    else:
        adjusted_font_size = base_adjusted_main

    # FontProperties is mutable-ish; create a new one with same family/path if possible
    try:
        fname = font_main.get_file()
        if fname:
            return FontProperties(fname=str(fname), size=adjusted_font_size)
    except Exception:
        pass

    return FontProperties(
        family=font_main.get_family(),
        weight=font_main.get_weight(),
        size=adjusted_font_size,
    )


def _format_coords(point: tuple[float, float]) -> str:
    lat, lon = point
    coords = (
        f"{lat:.4f}° N / {lon:.4f}° E"
        if lat >= 0
        else f"{abs(lat):.4f}° S / {lon:.4f}° E"
    )
    if lon < 0:
        coords = coords.replace("E", "W")
    return coords


def render_poster_figure(
    *,
    data: PosterData,
    theme: dict[str, str],
    country_label: str | None = None,
) -> tuple[Figure, Axes, PosterMeta]:
    """
    Create and fully render the matplotlib Figure.
    No disk IO here.
    """
    fig, ax = plt.subplots(figsize=(data.width, data.height), facecolor=theme["bg"])
    ax.set_facecolor(theme["bg"])
    ax.set_position((0.0, 0.0, 1.0, 1.0))

    # Features (water, parks, rail, etc.)
    # Render "under" features first, then draw roads, then render "over" features.
    feats = build_default_features()

    for feat in feats:
        if getattr(feat, "layer", "under") != "under":
            continue
        state = data.features.get(feat.key)
        if state is None:
            continue
        feat.render(ax=ax, theme=theme, state=state)

    # Roads
    ox.plot_graph(
        data.G_proj,
        ax=ax,
        bgcolor=theme["bg"],
        node_size=0,
        edge_color=data.edge_colors,
        edge_linewidth=data.edge_widths,
        show=False,
        close=False,
    )

    for feat in feats:
        if getattr(feat, "layer", "under") != "over":
            continue
        state = data.features.get(feat.key)
        if state is None:
            continue
        feat.render(ax=ax, theme=theme, state=state)

    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(data.crop_xlim)
    ax.set_ylim(data.crop_ylim)

    if data.star_point is not None:
        try:
            star = ox.projection.project_geometry(
                Point(data.star_point[1], data.star_point[0]),
                crs="EPSG:4326",
                to_crs=data.G_proj.graph.get("crs"),
            )[0]
            fig_w = float(ax.figure.get_size_inches()[0])  # type: ignore[index]
            size = 140.0 * (fig_w / 12.0)
            color = theme.get("civic_icon", theme.get("text", "#ffffff"))

            ax.scatter(
                [star.x],  # type: ignore[arg-type]
                [star.y],  # type: ignore[arg-type]
                s=size,
                marker="*",
                color=color,
                zorder=40,
            )
            ax.scatter(
                [star.x],  # type: ignore[arg-type]
                [star.y],  # type: ignore[arg-type]
                s=size * 1.35,
                marker="*",
                facecolors="none",
                edgecolors=color,
                linewidths=1.2,
                zorder=39,
            )
        except Exception:
            pass

    # Gradients
    create_gradient_fade(ax, theme["gradient_color"], location="bottom", zorder=10)
    create_gradient_fade(ax, theme["gradient_color"], location="top", zorder=10)

    # Typography
    fonts = _build_fonts(width=data.width)
    font_main_adjusted = _adjust_main_font_for_city(
        fonts["main"], city=data.city, width=data.width
    )

    spaced_city = "  ".join(list(data.city.upper()))
    country_text = (
        country_label if country_label is not None else data.country
    ).upper()
    coords_text = _format_coords(data.point)

    # Bottom text
    ax.text(
        0.5,
        0.14,
        spaced_city,
        transform=ax.transAxes,
        color=theme["text"],
        ha="center",
        fontproperties=font_main_adjusted,
        zorder=11,
    )

    ax.text(
        0.5,
        0.10,
        country_text,
        transform=ax.transAxes,
        color=theme["text"],
        ha="center",
        fontproperties=fonts["sub"],
        zorder=11,
    )

    scale_factor = data.width / 12.0
    ax.plot(
        [0.4, 0.6],
        [0.125, 0.125],
        transform=ax.transAxes,
        color=theme["text"],
        linewidth=1 * scale_factor,
        zorder=11,
    )

    meta = PosterMeta(
        spaced_city=spaced_city, country_text=country_text, coords_text=coords_text
    )
    return fig, ax, meta


# -----------------------------
# Step 3: Save output
# -----------------------------
def save_poster_figure(
    *,
    fig: Figure,
    output_file: Path,
    output_format: str,
    theme: dict[str, str],
) -> Path:
    fmt = output_format.lower()
    save_kwargs: dict[str, Any] = dict(
        facecolor=theme["bg"], bbox_inches="tight", pad_inches=0.05
    )
    if fmt == "png":
        save_kwargs["dpi"] = 300

    output_file.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_file, format=fmt, **save_kwargs)
    plt.close(fig)
    return output_file


def cleanup_old_posters(
    *,
    keep: int = MAX_POSTERS,
    posters_dir: Path = POSTERS_DIR,
    extensions: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".pdf", ".svg"),
) -> None:
    if keep < 1:
        return
    if not posters_dir.exists():
        return

    candidates = [
        path
        for path in posters_dir.iterdir()
        if path.is_file() and path.suffix.lower() in extensions
    ]
    if len(candidates) <= keep:
        return

    candidates.sort(key=lambda path: path.stat().st_mtime)
    to_remove = candidates[: max(0, len(candidates) - keep)]
    for path in to_remove:
        try:
            path.unlink()
            logger.info("Removed old poster %s", path)
        except OSError:
            logger.warning("Failed to remove old poster %s", path)


# -----------------------------
# Runner / Orchestrator
# -----------------------------
def create_poster(
    *,
    city: str,
    country: str,
    point: tuple[float, float],
    star_point: tuple[float, float] | None = None,
    dist: int,
    output_file: Path,
    output_format: str,
    theme: dict[str, str],
    width: float = 12,
    height: float = 16,
    country_label: str | None = None,
    enabled_features: dict[str, bool] | None = None,
) -> PosterResult:
    """
    Runner function: gather -> render -> save. Returns a small result object.
    """
    logger.info("Generating map for %s, %s...", city, country)

    data = gather_poster_data(
        city=city,
        country=country,
        point=point,
        star_point=star_point,
        dist=dist,
        width=width,
        height=height,
        theme=theme,
        enabled_features=enabled_features,
    )

    logger.info("All data retrieved successfully.")
    logger.info("Rendering map...")

    fig, _, meta = render_poster_figure(
        data=data, theme=theme, country_label=country_label
    )

    logger.info("Saving to %s...", output_file)
    out = save_poster_figure(
        fig=fig, output_file=output_file, output_format=output_format, theme=theme
    )

    cleanup_old_posters()

    logger.info("Done. Poster saved as %s", out)
    return PosterResult(output_file=out, output_format=output_format, meta=meta)
