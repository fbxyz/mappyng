"""
Coloured proportional symbols
=============================

Circle size keeps the magnitude of a count; colour can carry a second
variable on the same symbols. ``Proportional`` colours its circles in two
ways, each with its own legend next to the size legend:

* ``color_column``: a numeric column classified like a ``Choropleth``
  (``cmap``, ``method``, ``num_classes``), a choropleth inside the circles;
* ``fill_column`` and ``fill_map``: one colour per category, as a
  ``Category`` layer. Categories absent from ``fill_map`` and missing values
  keep ``fill``, shown in the legend under ``default_label``.

Both maps size the circles by the excess deaths among people over 75 during
the 2025 heatwaves (Sante publique France, ODISSE). The first one colours
them by the excess relative to the expected deaths, the second one by a
broad zone of the department's region.

Hover a circle to read its values.
"""

from pathlib import Path

import pandas as pd

import mappyng as mp
from mappyng.data import load_france_departments, load_france_regions, load_europe

europe = load_europe().to_crs(2154)
regions = load_france_regions().to_crs(2154)
deps = load_france_departments().to_crs(2154)
df = pd.read_csv(Path("data") / "canicule_exces_75_2025.csv", dtype={"code_dep": str})
deps = deps.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")
pts = deps[deps["exces_deces"].notna()].copy()

# Broad zones from the region codes: the Mediterranean regions, the other
# southern ones, and the rest left to ``fill`` (shown as "Northern regions").
ZONES = {"76": "Mediterranean", "93": "Mediterranean", "94": "Mediterranean",
         "75": "Other south", "84": "Other south"}
pts["zone"] = pts["insee_reg"].astype(str).map(ZONES)

BBOX_METRO = [90000, 6040000, 1280000, 7150000]


def base(title):
    """Background shared by both maps."""
    return (
        mp.Map(europe, bbox=BBOX_METRO, width=800, height=800, padding=25,
               facecolor="#eef2e6")
        + mp.Basemap()
        + mp.Vector(deps, stroke="#9a9a9a", stroke_width=0.3)
        + mp.Vector(regions, stroke="#4d4d4d", stroke_width=0.2)
        + mp.Title(title, subtitle="People over 75, 2025")
        + mp.Source("Source: Sante publique France (ODISSE)")
    )


# Classes of a second column: the relative excess, in four quartiles.
m_classes = base("Excess deaths and relative excess") + mp.Proportional(
    pts, column="exces_deces", fill_opacity=0.85, stroke="#ffffff",
    color_column="exces_relatif", cmap="YlOrRd", method="Quantiles",
    num_classes=4,
    legend=mp.Legend("Excess deaths", circle_fill="#bdbdbd"),
    color_legend=mp.Legend("Relative excess (%)", decimals=0),
) + mp.Tooltip(["LIB_GEO", "exces_deces", "exces_relatif"],
               aliases={"LIB_GEO": "Department",
                        "exces_deces": "Excess deaths",
                        "exces_relatif": "Relative excess (%)"})

# Categories: one colour per zone, the other departments keep ``fill``.
m_categories = base("Excess deaths by zone") + mp.Proportional(
    pts, column="exces_deces", fill_opacity=0.85, stroke="#ffffff",
    fill_column="zone",
    fill_map={"Mediterranean": "#d95f02", "Other south": "#e6ab02"},
    fill="#7570b3", default_label="Northern regions",
    legend=mp.Legend("Excess deaths", circle_fill="#bdbdbd"),
    color_legend=mp.Legend("Zone"),
) + mp.Tooltip(["LIB_GEO", "exces_deces", "zone"],
               aliases={"LIB_GEO": "Department",
                        "exces_deces": "Excess deaths", "zone": "Zone"})
