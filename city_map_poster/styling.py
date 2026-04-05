from __future__ import annotations
from typing import Any, Dict, List
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


def edge_colors_by_type(G, theme: Dict[str, Any]) -> List[str]:
    colors: List[str] = []
    for _, _, data in G.edges(data=True):
        highway = data.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0] if highway else "unclassified"

        if highway in ["motorway", "motorway_link"]:
            c = theme["road_motorway"]
        elif highway in ["trunk", "trunk_link", "primary", "primary_link"]:
            c = theme["road_primary"]
        elif highway in ["secondary", "secondary_link"]:
            c = theme["road_secondary"]
        elif highway in ["tertiary", "tertiary_link"]:
            c = theme["road_tertiary"]
        elif highway in ["residential", "living_street", "unclassified"]:
            c = theme["road_residential"]
        else:
            c = theme["road_default"]

        colors.append(c)
    return colors


def edge_widths_by_type(G) -> List[float]:
    widths: List[float] = []
    for _, _, data in G.edges(data=True):
        highway = data.get("highway", "unclassified")
        if isinstance(highway, list):
            highway = highway[0] if highway else "unclassified"

        if highway in ["motorway", "motorway_link"]:
            w = 1.2
        elif highway in ["trunk", "trunk_link", "primary", "primary_link"]:
            w = 1.0
        elif highway in ["secondary", "secondary_link"]:
            w = 0.8
        elif highway in ["tertiary", "tertiary_link"]:
            w = 0.6
        else:
            w = 0.4

        widths.append(w)
    return widths
