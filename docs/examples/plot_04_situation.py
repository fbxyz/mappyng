"""
Situation map (qualitative symbols)
===================================

Located qualitative points, differentiated by category, with a zoom
window on the dense Paris region. Data: hospital helipads in mainland
France, distinguished by night-flight capability (data.gouv.fr, CC-BY).

Hover a marker to read its name.
"""

from pathlib import Path

import geopandas as gpd
import pandas as pd

import mappyng as mp
from mappyng.data import load_france_departments, load_europe

europe = load_europe().to_crs(2154)
deps = load_france_departments().to_crs(2154)
df = pd.read_csv(Path("data") / "helistations.csv")
points = gpd.GeoDataFrame(
    df,
    geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
    crs="EPSG:4326",
).to_crs(2154)

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

# Zoom on the Paris region (Lambert-93), where helipads are dense.
zoom = mp.Zoom([586377, 6780533, 739396, 6904563], border_radius=8,
               box_shadow={"dx": 2, "dy": 2, "blur": 4, "opacity": 0.3})

m = (
    mp.Map(europe, bbox=BBOX_METRO, width=900, height=1000, padding=25,
           facecolor="#e8eef2", border_radius=10)
    + insets
    + zoom
    + mp.Basemap()
    + mp.Vector(deps, stroke="#9aa6b2", stroke_width=0.2)
    + mp.DropShadow(europe, query="code_pays_iso3 == 'FRA'")
    + mp.Situation(
        points,
        column="vol_nuit",
        symbol={
            "Night flight": {"marker": "circle", "fill": "#1f78b4", "size": 6},
            "Day only": {"marker": "triangle", "fill": "#e31a1c", "size": 9},
        },
        legend=mp.Legend("Hospital helipads"),
    )
    + mp.Title("Hospital helipads", subtitle="Night-flight capability")
    # Scale bar over the sea, in the Gulf of Lion.
    + mp.ScaleBar(length=100000, label="100 km", position=(0.55, 0.855),
                  opacity=0.8)
    + mp.Source("Source: data.gouv.fr (CC-BY)")
    + mp.Tooltip(["nom", "vol_nuit"],
                 aliases={"nom": "Site", "vol_nuit": "Capability"})
)
