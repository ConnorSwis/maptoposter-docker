from __future__ import annotations

import matplotlib.colors as mcolors
import numpy as np


def create_gradient_fade(
    ax, color: str, location: str = "bottom", zorder: int = 10
) -> None:
    vals = np.linspace(0, 1, 256).reshape(-1, 1)
    gradient = np.hstack((vals, vals))

    rgb = mcolors.to_rgb(color)
    my_colors = np.zeros((256, 4))
    my_colors[:, 0] = rgb[0]
    my_colors[:, 1] = rgb[1]
    my_colors[:, 2] = rgb[2]

    if location == "bottom":
        my_colors[:, 3] = np.linspace(1, 0, 256)
        extent_y_start, extent_y_end = 0.0, 0.25
    else:
        my_colors[:, 3] = np.linspace(0, 1, 256)
        extent_y_start, extent_y_end = 0.75, 1.0

    custom_cmap = mcolors.ListedColormap(my_colors)

    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    y_range = ylim[1] - ylim[0]

    y_bottom = ylim[0] + y_range * extent_y_start
    y_top = ylim[0] + y_range * extent_y_end

    ax.imshow(
        gradient,
        extent=[xlim[0], xlim[1], y_bottom, y_top],
        aspect="auto",
        cmap=custom_cmap,
        zorder=zorder,
        origin="lower",
    )


def get_edge_colors_by_type(G, theme: dict[str, str]) -> list[str]:
    edge_colors: list[str] = []

    for _u, _v, data in G.edges(data=True):
        highway = data.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0] if highway else "unclassified"

        if highway in ["motorway", "motorway_link"]:
            color = theme["road_motorway"]
        elif highway in ["trunk", "trunk_link", "primary", "primary_link"]:
            color = theme["road_primary"]
        elif highway in ["secondary", "secondary_link"]:
            color = theme["road_secondary"]
        elif highway in ["tertiary", "tertiary_link"]:
            color = theme["road_tertiary"]
        elif highway in ["residential", "living_street", "unclassified"]:
            color = theme["road_residential"]
        else:
            color = theme["road_default"]

        edge_colors.append(color)

    return edge_colors


def get_edge_widths_by_type(G, dist_meters: int | float) -> list[float]:
    edge_widths: list[float] = []
    scale = float(np.clip(2500.0 / max(dist_meters, 1.0), 0.5, 2.0))

    for _u, _v, data in G.edges(data=True):
        highway = data.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0] if highway else "unclassified"

        if highway in ["motorway", "motorway_link"]:
            base_width = 1.2
        elif highway in ["trunk", "trunk_link", "primary", "primary_link"]:
            base_width = 1.0
        elif highway in ["secondary", "secondary_link"]:
            base_width = 0.8
        elif highway in ["tertiary", "tertiary_link"]:
            base_width = 0.6
        else:
            base_width = 0.4

        edge_widths.append(base_width * scale)

    return edge_widths


def get_rail_widths_from_gdf(rail_lines_gdf, dist_meters: int | float) -> list[float]:
    widths = []
    scale = float(np.clip(2500.0 / max(dist_meters, 1.0), 0.5, 2.0))

    for _, row in rail_lines_gdf.iterrows():
        railway = row.get("railway")
        if isinstance(railway, list):
            railway = railway[0] if railway else None

        service = row.get("service")
        if isinstance(service, list):
            service = service[0] if service else None

        width = 0.2  # default

        if railway == "rail":
            width = 1.0 if service not in {"siding", "yard", "spur"} else 0.2
        elif railway == "subway":
            width = 0.8
        elif railway in {"light_rail", "monorail", "narrow_gauge", "funicular"}:
            width = 0.7
        elif railway == "tram":
            width = 0.6
        elif railway in {"disused", "construction"}:
            width = 0.3

        widths.append(width * scale)
    return widths
