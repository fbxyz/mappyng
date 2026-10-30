"""
Zoom, cartouches and drop shadow
=================================

A zoom window magnifies a dense area (the Paris region), the overseas
departments are drawn as cartouches and ``box_shadow`` lifts the main
map off the European background. Layers are drawn in the cartouches by
default; ``on_zoom=True`` also redraws a layer in the zoom window.

The map is derived from a shared ``base`` with ``+``, which returns a new
map and leaves ``base`` unchanged.

Hover a department to read its value.
"""

from pathlib import Path

import pandas as pd

import mappyng as mp
from mappyng.data import load_france_departments, load_france_regions, load_europe

europe = load_europe().to_crs(2154)
regions = load_france_regions().to_crs(2154)
deps = load_france_departments().to_crs(2154)
df = pd.read_csv(Path("data") / "cardio_mortalite_dep.csv", dtype={"code_dep": str})
deps = deps.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")

BBOX_METRO = [90000, 6040000, 1280000, 7150000]
OVERSEAS = {
    "Guadeloupe": [-6890454, 1780151, -6799589, 1874186],
    "Martinique": [-6826862, 1609607, -6759494, 1685367],
    "French Guiana": [-6136680, 235261, -5707791, 671780],
    "Reunion": [6136383, -2448160, 6226316, -2366992],
    "Mayotte": [5006226, -1459183, 5050208, -1416184],
}
insets = mp.Insets(
    [mp.Inset(name, bbox=bbox, crs=3857) for name, bbox in OVERSEAS.items()],
    spacing=15, title_size=7, border_radius=6, box_shadow=True,
)

# Paris and the inner ring (75, 92, 93, 94) in Lambert-93. A tight bbox
# over a large window magnifies this dense area about 11 times relative to
# the main map.
zoom = mp.Zoom([634000, 6841000, 674000, 6882000],
               x=705, y=160, width=128, height=140, border_radius=8,
               box_shadow={"dx": 2, "dy": 2, "blur": 4, "opacity": 0.3})

base = (
    mp.Map(europe, bbox=BBOX_METRO, width=900, height=1000, padding=25,
           facecolor="#dce6f0", border_radius=10,
           box_shadow={"dx": 3, "dy": 3, "blur": 6, "opacity": 0.2})
    + insets
    + mp.Basemap()
    + mp.Vector(regions, stroke="#4d4d4d", stroke_width=0.1)
    + mp.DropShadow(europe, query="code_pays_iso3 == 'FRA'")
    # Scale bar over the sea, in the Gulf of Lion.
    + mp.ScaleBar(length=100000, label="100 km", position=(0.55, 0.855),
                  opacity=0.8)
    + mp.Source("Source: Sante publique France (ODISSE)")
)

m = (
    base
    + zoom
    + mp.Choropleth(
        deps, column="taux_mortalite", cmap="Reds",
        method="Quantiles", num_classes=5, stroke_width=0.15,
        legend=mp.Legend("Deaths / 100,000 inhabitants",
                         orientation="horizontal", decimals=0,
                         nodata_label="No data"),
        on_zoom=True,
    )
    + mp.Vector(regions, stroke="#333333", stroke_width=0.4, position="top",
                on_zoom=True)
    + mp.Title("Mortality from heart failure",
               subtitle="Zoom on the Paris region, overseas in cartouches")
    + mp.Tooltip(["LIB_GEO", "taux_mortalite"],
                 aliases={"LIB_GEO": "Department", "taux_mortalite": "Rate"})
)
