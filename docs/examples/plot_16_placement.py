"""
Placing elements on the map
===========================

Every element with a ``position`` (title, scale bar, north arrow, source,
legend) understands the same forms:

* fractions or percentages of the map area, ``(0.7, 0.9)`` or
  ``{"x": "70%", "y": "90%"}``;
* pixels, ``{"px": 120, "py": 80}``;
* **geographic coordinates**, in the map CRS (``{"geo": (x, y)}``) or as
  longitude/latitude (``{"lon": 4.0, "lat": 42.6}``).

Geographic placement anchors an element to a place on the map, whatever the
size of the document. Here the scale bar sits in the Gulf of Lion, clear of
the coast, the north arrow in the Bay of Biscay and the legend in the
Mediterranean, below it. The point given is the anchor of each element: the left end
of the scale bar, the tip of the north arrow, the baseline of the title and
the top-left corner of the legend.

Data: mortality from heart failure, rate per 100,000 inhabitants
(Sante publique France, ODISSE).
"""

from pathlib import Path

import pandas as pd

import mappyng as mp
from mappyng.data import load_france_departments

deps = load_france_departments().to_crs(2154)
df = pd.read_csv(Path("data") / "cardio_mortalite_dep.csv", dtype={"code_dep": str})
deps = deps.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")

BBOX_METRO = [90000, 6040000, 1280000, 7150000]

m = (
    mp.Map(deps, bbox=BBOX_METRO, width=900, height=900, facecolor="#dce6f0")
    + mp.Basemap()
    + mp.Choropleth(
        deps, column="taux_mortalite", cmap="Reds", method="Quantiles",
        num_classes=5, stroke_width=0.15,
        legend=mp.Legend(
            "Deaths / 100,000", orientation="horizontal", decimals=0,
            swatch_width=18, fontsize=7, label_rotation=0, nodata_label="No data",
            # top-left corner of the legend, anchored to a place:
            position={"lon": 3.3, "lat": 42.5},
        ),
    )
    # Percentages of the map area.
    + mp.Title("Mortality from heart failure",
               position={"x": "1%", "y": "-1.5%"})
    # Geographic coordinates: the bar starts in the Gulf of Lion.
    + mp.ScaleBar(length=100000, label="100 km",
                  position={"lon": 3.3, "lat": 42.95})
    # ... the arrow tip in the Bay of Biscay.
    + mp.NorthArrow(size=40, position={"lon": -3.6, "lat": 45.2})
    # Pixels.
    + mp.Source("Source: Sante publique France (ODISSE)", layout="horizontal",
                position={"px": 40, "py": 885})
)
