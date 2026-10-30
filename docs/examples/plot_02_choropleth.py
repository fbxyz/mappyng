"""
Choropleth
==========

A choropleth maps a *relative* quantity (here a standardised mortality
rate) to colour value. Data: mortality from heart failure, rate per
100,000 inhabitants, 2020-2022 average (Sante publique France, ODISSE).
The legend swatches have rounded corners (``swatch_shape="rounded"``).

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

# Mainland frame (Lambert-93) and overseas cartouches (declared in 3857).
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

m = (
    mp.Map(europe, bbox=BBOX_METRO, width=900, height=1000, padding=25,
           facecolor="#B9D9EB", border_radius=10,
           box_shadow={"dx": 3, "dy": 3, "blur": 6, "opacity": 0.2})
    + insets
    # Lighter water along the coasts of the European countries.
    + mp.OceanGradient(europe)
    # European countries as background, with France lifted by a drop shadow.
    + mp.Basemap()
    + mp.Vector(regions, stroke="#4d4d4d", stroke_width=0.1)
    + mp.DropShadow(europe, query="code_pays_iso3 == 'FRA'")
    + mp.Choropleth(
        deps, column="taux_mortalite", cmap="Reds",
        method="Quantiles", num_classes=5, stroke_width=0.15,
        legend=mp.Legend("Deaths / 100,000 inhabitants",
                         orientation="horizontal", decimals=0,
                         nodata_label="No data", swatch_shape="rounded"),
    )
    + mp.Vector(regions, stroke="#333333", stroke_width=0.4, position="top")
    + mp.Title("Mortality from heart failure",
               subtitle="Standardised rate, 2020-2022 average")
    # Scale bar over the sea, in the Gulf of Lion.
    + mp.ScaleBar(length=100000, label="100 km", position=(0.55, 0.855),
                  opacity=0.8)
    + mp.Source("Source: Sante publique France (ODISSE)")
    # Hover tooltips of the interactive export (m.render("map.html")).
    + mp.Tooltip(["LIB_GEO", "taux_mortalite"],
                 aliases={"LIB_GEO": "Department", "taux_mortalite": "Rate"})
)
