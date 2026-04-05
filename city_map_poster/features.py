from dataclasses import dataclass
from typing import Any
from matplotlib.axes import Axes
import osmnx as ox
from .render import get_rail_widths_from_gdf
from .osm import fetch_features


def build_default_features(
    *, enabled_overrides: dict[str, bool] | None = None
) -> list[MapFeature]:
    """Create the default feature set. Toggle with enabled_overrides={"rail": False, "buildings": True} etc."""
    enabled_overrides = enabled_overrides or {}

    def _enabled(key: str, default: bool) -> bool:
        return enabled_overrides.get(key, default)

    return [
        # Big-shape layers
        OceanFeature(enabled=_enabled("ocean", False)),
        WaterFeature(enabled=_enabled("water", False)),
        ForestFeature(enabled=_enabled("forest", False)),
        ParksFeature(enabled=_enabled("parks", False)),
        BuildingsFeature(enabled=_enabled("buildings", False)),
        # Line overlays
        RiversFeature(enabled=_enabled("rivers", False)),
        RailFeature(enabled=_enabled("rail", False)),
        CoastlineFeature(enabled=_enabled("coastline", False)),
        CivicIconFeature(enabled=_enabled("civic_icon", False)),
    ]


# -----------------------------
# Feature system
# -----------------------------
@dataclass(frozen=True)
class FeatureState:
    """Holds the projected GeoDataFrame plus any precomputed draw params."""

    gdf_proj: Any | None
    draw: dict[str, Any]


class MapFeature:
    """Base class for map features (water, parks, rails, etc.).

    A feature is responsible for:
      - fetching its raw OSM feature GeoDataFrame
      - projecting/sanitizing its geometry to match the graph CRS
      - precomputing any draw parameters
      - rendering itself onto a matplotlib Axes

    This keeps feature logic in one place and lets the poster pipeline simply
    iterate enabled features.
    """

    key: str  # stable identifier used in data.features
    name: str  # friendly name for status messages
    display_name: str  # display name for UI
    layer: str = "under"  # "under" renders before roads; "over" renders after roads

    def __init__(self, *, enabled: bool = True):
        self.enabled = enabled

    # ----- Fetch / transform -----
    def fetch(self, point: tuple[float, float], dist: float) -> Any | None:
        raise NotImplementedError

    def project(self, gdf: Any | None, *, graph_crs: Any | None) -> Any | None:
        raise NotImplementedError

    def precompute(self, gdf_proj: Any | None, *, dist: int | float) -> dict[str, Any]:
        return {}

    # ----- Render -----
    def render(self, *, ax: Axes, theme: dict[str, str], state: FeatureState) -> None:
        raise NotImplementedError


class PolygonFeature(MapFeature):
    """Convenience base class for polygon features."""

    allowed_geom = ("Polygon", "MultiPolygon")

    def project(self, gdf: Any | None, *, graph_crs: Any | None) -> Any | None:
        if gdf is None or getattr(gdf, "empty", True):
            return None
        polys = gdf[gdf.geometry.type.isin(list(self.allowed_geom))]
        if polys.empty:
            return None
        try:
            return ox.projection.project_gdf(polys)
        except Exception:
            if graph_crs is None:
                return polys
            return polys.to_crs(graph_crs)


class LineFeature(MapFeature):
    """Convenience base class for line features."""

    allowed_geom = ("LineString", "MultiLineString")

    def project(self, gdf: Any | None, *, graph_crs: Any | None) -> Any | None:
        if gdf is None or getattr(gdf, "empty", True):
            return None
        lines = gdf[gdf.geometry.type.isin(list(self.allowed_geom))]
        if lines.empty:
            return None
        try:
            return ox.projection.project_gdf(lines)
        except Exception:
            return lines.to_crs(graph_crs) if graph_crs is not None else lines


class WaterFeature(PolygonFeature):
    key = "water"
    name = "water features"
    display_name = "Water"

    def fetch(self, point: tuple[float, float], dist: float) -> Any | None:
        return fetch_features(
            point,
            dist,
            tags={"natural": "water", "waterway": "riverbank"},
            name="water",
        )

    def render(self, *, ax: Axes, theme: dict[str, str], state: FeatureState) -> None:
        gdf = state.gdf_proj
        if gdf is None or getattr(gdf, "empty", True):
            return
        gdf.plot(ax=ax, facecolor=theme["water"], edgecolor="none", zorder=1)


class OceanFeature(PolygonFeature):
    key = "ocean"
    name = "ocean/sea"
    display_name = "Oceans"

    def fetch(self, point: tuple[float, float], dist: float) -> Any | None:
        return fetch_features(
            point,
            dist,
            tags={"water": ["sea", "ocean", "bay", "lagoon"]},
            name="ocean",
        )

    def render(self, *, ax: Axes, theme: dict[str, str], state: FeatureState) -> None:
        gdf = state.gdf_proj
        if gdf is None or getattr(gdf, "empty", True):
            return
        color = theme.get("ocean", theme.get("water", theme.get("bg", "#ffffff")))
        gdf.plot(ax=ax, facecolor=color, edgecolor="none", zorder=0)


class ParksFeature(PolygonFeature):
    key = "parks"
    name = "parks/green spaces"
    display_name = "Parks"

    def fetch(self, point: tuple[float, float], dist: float) -> Any | None:
        return fetch_features(
            point,
            dist,
            tags={"leisure": "park", "landuse": "grass"},
            name="parks",
        )

    def render(self, *, ax: Axes, theme: dict[str, str], state: FeatureState) -> None:
        gdf = state.gdf_proj
        if gdf is None or getattr(gdf, "empty", True):
            return
        gdf.plot(ax=ax, facecolor=theme["parks"], edgecolor="none", zorder=2)


class RailFeature(LineFeature):
    key = "rail"
    name = "rail features"
    display_name = "Rails"

    def fetch(self, point: tuple[float, float], dist: float) -> Any | None:
        return fetch_features(
            point,
            dist,
            tags={
                "railway": [
                    "rail",
                    "siding",
                    "yard",
                    "spur",
                    "subway",
                    "light_rail",
                    "monorail",
                    "narrow_gauge",
                    "tram",
                    "disused",
                    "turntable",
                ]
            },
            name="rail",
        )

    def precompute(self, gdf_proj: Any | None, *, dist: int | float) -> dict[str, Any]:
        if gdf_proj is None or getattr(gdf_proj, "empty", True):
            return {"widths": []}
        return {"widths": get_rail_widths_from_gdf(gdf_proj, dist)}

    def render(self, *, ax: Axes, theme: dict[str, str], state: FeatureState) -> None:
        gdf = state.gdf_proj
        if gdf is None or getattr(gdf, "empty", True):
            return
        widths = state.draw.get("widths")
        if widths is None:
            widths = get_rail_widths_from_gdf(gdf, state.draw.get("dist", 0))
        gdf.plot(
            ax=ax,
            linewidth=widths,
            color=theme["rail"],
            zorder=3,
        )


class BuildingsFeature(PolygonFeature):
    key = "buildings"
    name = "building footprints"
    display_name = "Buildings"

    def fetch(self, point: tuple[float, float], dist: float) -> Any | None:
        # building=True pulls all building=* and building:part=* geometries.
        return fetch_features(
            point,
            dist,
            tags={"building": True},
            name="buildings",
        )

    def render(self, *, ax: Axes, theme: dict[str, str], state: FeatureState) -> None:
        gdf = state.gdf_proj
        if gdf is None or getattr(gdf, "empty", True):
            return
        # Use theme["buildings"] if present; otherwise fall back to a subtle tone.
        color = theme.get("buildings", theme.get("text", "#ffffff"))
        gdf.plot(ax=ax, facecolor=color, edgecolor="none", zorder=2)


class ForestFeature(PolygonFeature):
    key = "forest"
    name = "forest/woodland"
    display_name = "Forests"

    def fetch(self, point: tuple[float, float], dist: float) -> Any | None:
        # Combine common woodland tags.
        return fetch_features(
            point,
            dist,
            tags={"landuse": ["forest"], "natural": ["wood"]},
            name="forest",
        )

    def render(self, *, ax: Axes, theme: dict[str, str], state: FeatureState) -> None:
        gdf = state.gdf_proj
        if gdf is None or getattr(gdf, "empty", True):
            return
        color = theme.get("forest", theme.get("parks", theme.get("text", "#ffffff")))
        gdf.plot(ax=ax, facecolor=color, edgecolor="none", zorder=2)


class RiversFeature(LineFeature):
    key = "rivers"
    name = "rivers/streams"
    display_name = "Rivers"

    def fetch(self, point: tuple[float, float], dist: float) -> Any | None:
        return fetch_features(
            point,
            dist,
            tags={"waterway": ["river", "stream", "canal"]},
            name="rivers",
        )

    def precompute(self, gdf_proj: Any | None, *, dist: int | float) -> dict[str, Any]:
        # Vary widths by waterway type if available.
        if gdf_proj is None or getattr(gdf_proj, "empty", True):
            return {"widths": []}
        widths: list[float] = []
        for _, row in gdf_proj.iterrows():
            wtype = row.get("waterway")
            if isinstance(wtype, list):
                wtype = wtype[0] if wtype else None
            if wtype == "river":
                widths.append(1.8)
            elif wtype == "canal":
                widths.append(1.3)
            else:
                widths.append(0.9)
        return {"widths": widths}

    def render(self, *, ax: Axes, theme: dict[str, str], state: FeatureState) -> None:
        gdf = state.gdf_proj
        if gdf is None or getattr(gdf, "empty", True):
            return
        color = theme.get("rivers", theme.get("water", theme.get("text", "#ffffff")))
        widths = state.draw.get("widths")
        if not widths:
            widths = [1.0] * len(gdf)
        gdf.plot(ax=ax, linewidth=widths, color=color, zorder=3)


class CoastlineFeature(LineFeature):
    key = "coastline"
    name = "coastline"
    display_name = "Coastlines"

    def fetch(self, point: tuple[float, float], dist: float) -> Any | None:
        return fetch_features(
            point,
            dist,
            tags={"natural": "coastline"},
            name="coastline",
        )

    def render(self, *, ax: Axes, theme: dict[str, str], state: FeatureState) -> None:
        gdf = state.gdf_proj
        if gdf is None or getattr(gdf, "empty", True):
            return
        color = theme.get("coastline", theme.get("text", "#ffffff"))
        # Coastline is a strong shape—keep it thin so it doesn't dominate.
        gdf.plot(ax=ax, linewidth=1.2, color=color, zorder=4)


class CivicIconFeature(MapFeature):
    """Places an icon on a key civic building (capitol / city hall) if found.

    This tries several OSM tag queries in priority order and chooses the best match.
    Render layer is "over" so it draws on top of roads.
    """

    key = "civic_icon"
    name = "civic icon"
    display_name = "Capital"

    def fetch(self, point: tuple[float, float], dist: float) -> Any | None:
        # Try a few common OSM patterns. We stop at the first query that returns data.
        # Notes:
        # - US: amenity=townhall is common for city hall.
        # - State capitols vary: building=capitol is sometimes used, otherwise office=government/government=legislative.
        tag_queries: list[dict[str, Any]] = [
            {"amenity": "townhall"},
            {"building": ["townhall", "city_hall", "capitol"]},
            {"office": "government"},
            {"government": ["legislative", "administrative"]},
        ]

        for tags in tag_queries:
            gdf = fetch_features(point, dist, tags=tags, name="civic")
            if gdf is not None and not getattr(gdf, "empty", True):
                return gdf
        return None

    def project(self, gdf: Any | None, *, graph_crs: Any | None) -> Any | None:
        # Accept points, polygons, and lines; we'll convert to representative points in precompute.
        if gdf is None or getattr(gdf, "empty", True):
            return None
        try:
            return ox.projection.project_gdf(gdf)
        except Exception:
            return gdf.to_crs(graph_crs) if graph_crs is not None else gdf

    def precompute(self, gdf_proj: Any | None, *, dist: int | float) -> dict[str, Any]:
        if gdf_proj is None or getattr(gdf_proj, "empty", True):
            return {"pt": None}

        # Choose the best candidate.
        best_pt = None
        best_score = -(10**9)

        for _, row in gdf_proj.iterrows():
            geom = row.geometry
            if geom is None:
                continue

            # Representative point
            gtype = getattr(geom, "geom_type", "")
            if gtype in ("Point", "MultiPoint"):
                try:
                    pt = geom if gtype == "Point" else list(geom.geoms)[0]
                except Exception:
                    continue
            else:
                # For polygons/lines, a point-on-surface tends to be safer than centroid.
                try:
                    pt = geom.representative_point()
                except Exception:
                    try:
                        pt = geom.centroid
                    except Exception:
                        continue

            # Scoring heuristic
            name = str(row.get("name", "") or "").lower()
            amenity = str(row.get("amenity", "") or "").lower()
            building = str(row.get("building", "") or "").lower()
            office = str(row.get("office", "") or "").lower()
            government = str(row.get("government", "") or "").lower()

            score = 0
            if "capitol" in name or "capitol" in building:
                score += 50
            if "city hall" in name or "town hall" in name or amenity == "townhall":
                score += 40
            if building in ("townhall", "city_hall"):
                score += 35
            if office == "government":
                score += 15
            if government in ("legislative", "administrative"):
                score += 10
            if name:
                score += 3

            # Prefer larger polygon buildings when available
            try:
                area = float(getattr(row.geometry, "area", 0.0) or 0.0)
                score += min(area / 2_000_000.0, 10.0)  # gentle nudge
            except Exception:
                pass

            if score > best_score:
                best_score = score
                best_pt = pt

        return {"pt": best_pt}

    def render(self, *, ax: Axes, theme: dict[str, str], state: FeatureState) -> None:
        pt = state.draw.get("pt")
        if pt is None:
            return

        # Size scales with poster width.
        fig_w = float(ax.figure.get_size_inches()[0])  # type: ignore[index]
        size = 110.0 * (fig_w / 12.0)
        color = theme.get("civic_icon", theme.get("text", "#ffffff"))

        try:
            ax.scatter([pt.x], [pt.y], s=size, marker="*", color=color, zorder=30)
            # subtle outline for contrast
            ax.scatter(
                [pt.x],
                [pt.y],
                s=size * 1.25,
                marker="*",
                facecolors="none",
                edgecolors=color,
                linewidths=1.0,
                zorder=29,
            )
        except Exception:
            # Fall back to text marker
            ax.text(
                pt.x,
                pt.y,
                "★",
                color=color,
                ha="center",
                va="center",
                fontsize=size / 10.0,
                zorder=30,
            )
