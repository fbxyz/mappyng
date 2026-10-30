"""
Proportional symbols
=====================

For an *absolute* quantity (a count), symbol size preserves the
magnitude that colour value would flatten. Data: excess deaths among
people over 75 during the 2025 heatwaves, by department (Sante publique
France, ODISSE).

Hover a circle to read its value.
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
           facecolor="#eef2e6", border_radius=10,
           box_shadow={"dx": 3, "dy": 3, "blur": 6, "opacity": 0.2})
    + insets
    + mp.Basemap()
    # Department outlines (where the circles sit), under the region outlines.
    + mp.Vector(deps, stroke="#9a9a9a", stroke_width=0.3)
    + mp.Vector(regions, stroke="#4d4d4d", stroke_width=0.2)
    + mp.DropShadow(europe, query="code_pays_iso3 == 'FRA'")
    + mp.Proportional(pts, column="exces_deces", fill="#d7301f",
                      fill_opacity=0.6, stroke="#7f0000",
                      legend=mp.Legend("Excess deaths"))
    + mp.Title("Excess deaths during heatwaves",
               subtitle="People over 75, 2025")
    # Scale bar over the sea, in the Gulf of Lion.
    + mp.ScaleBar(length=100000, label="100 km", position=(0.55, 0.855),
                  opacity=0.8)
    + mp.Source("Source: Sante publique France (ODISSE)")
    + mp.Tooltip(["LIB_GEO", "exces_deces"],
                 aliases={"LIB_GEO": "Department",
                          "exces_deces": "Excess deaths"})
)
