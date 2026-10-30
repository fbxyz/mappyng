"""
Drop shadow and glow
=====================

``box_shadow`` and ``glow`` apply to the main map, either with the
default settings (``True``) or through a dict (``dx``, ``dy``,
``blur``, ``color``, ``opacity``). Here an outer glow on a dark
background, over a European basemap.
"""

import mappyng as mp
from mappyng.data import load_france_departments, load_europe

europe = load_europe().to_crs(2154)
deps = load_france_departments().to_crs(2154)

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
    spacing=15, title_size=7, border_radius=6,
    glow={"blur": 8, "color": "#4cc9f0"},
)

m = (
    mp.Map(
        europe,
        bbox=BBOX_METRO,
        width=900,
        height=1000,
        padding=25,
        style={"base": "classic", "title_color": "#e0e1dd"},
        facecolor="#16324a",
        background="#0d1b2a",
        border_radius=10,
        glow={"blur": 14, "color": "#4cc9f0", "opacity": 0.7},
    )
    + insets
    + mp.Basemap()
    + mp.DropShadow(europe, query="code_pays_iso3 == 'FRA'")
    + mp.Vector(deps, stroke="#4cc9f0", stroke_width=0.2)
    + mp.Title("Outer glow on a dark background")
)
