"""
Finer geometry in a zoom window
===============================

A map is often drawn from a *generalised* (simplified) layer, which keeps the
file light but looks coarse once a dense area is magnified in a zoom window or
an inset. ``detail`` lets a layer draw its zoom and inset views from a finer
layer of the same areas, **keeping the layer's symbology**: the classes and
colours are computed once, from the layer's own data, then carried to the
finer outlines through a join key (``detail_join``).

Here the coarse level is made by simplifying the departments (in practice you
would load two generalisation levels of your own data). Both maps below zoom on
Paris and its inner ring; only the second one passes ``detail``. Every
department keeps the colour it has on the main map.

Data: mortality from heart failure, rate per 100,000 inhabitants
(Sante publique France, ODISSE).
"""

from pathlib import Path

import pandas as pd

import mappyng as mp
from mappyng.data import load_france_departments

fine = load_france_departments().to_crs(2154)
df = pd.read_csv(Path("data") / "cardio_mortalite_dep.csv", dtype={"code_dep": str})
fine = fine.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")

# The coarse level: same departments, outlines simplified to 15 km.
coarse = fine.copy()
coarse["geometry"] = coarse.geometry.simplify(15000)

BBOX_METRO = [90000, 6040000, 1280000, 7150000]
PARIS = [500000, 6740000, 780000, 6940000]


def build(detail=None):
    """The map; ``detail`` is the finer layer, or None for the plain zoom."""
    return (
        mp.Map(coarse, bbox=BBOX_METRO, width=800, height=800,
               facecolor="#dce6f0")
        + mp.Basemap(detail=detail)
        + mp.Choropleth(
            coarse, column="taux_mortalite", cmap="Reds",
            method="Quantiles", num_classes=5, stroke_width=0.15,
            legend=mp.Legend("Deaths / 100,000", orientation="horizontal",
                             decimals=0, swatch_width=18, fontsize=7,
                             label_rotation=0, nodata_label="No data"),
            on_zoom=True,
            detail=detail,           # finer outlines for the zoom ...
            detail_join="COD_GEO",   # ... joined on this column, in both layers
        )
        + mp.Zoom(PARIS, x=520, y=90, width=250, height=250,
                  border_radius=8)
    )


# Without ``detail``: the zoom is drawn from the coarse outlines.
m_coarse = build() + mp.Title("Zoom from the generalised layer")

# With ``detail``: finer outlines in the zoom, same colours.
m_detail = build(detail=fine) + mp.Title("Zoom from the finer layer")
