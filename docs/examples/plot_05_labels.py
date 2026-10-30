"""
Automatic labels
================

``Label`` places place names by simulated annealing to limit
overlaps. Here the mainland region names, over a European background.
"""

import mappyng as mp
from mappyng.data import load_france_regions, load_europe

europe = load_europe().to_crs(2154)
regions = load_france_regions().to_crs(2154)

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
           facecolor="#eceff4", border_radius=10)
    + insets
    + mp.Basemap()
    + mp.DropShadow(europe, query="code_pays_iso3 == 'FRA'")
    + mp.Vector(regions, stroke="#9aa6b2", stroke_width=0.4)
    + mp.Label(regions, column="LIB_GEO", font_size=11)
    + mp.Title("Regions of mainland France")
    + mp.Source("Basemap: Natural Earth, IGN GéoFLA")
)
