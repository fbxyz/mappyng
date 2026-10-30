"""
Basemap and chrome
==================

A minimal map: European countries as background, France lifted by a drop
shadow, department boundaries on top, plus the chrome (title, scale bar,
source). Mainland France is framed in Lambert-93 and the overseas
departments are drawn as cartouches.

A map is built by adding layers and elements to a :class:`~mappyng.Map`
with ``+``. The order of the elements does not matter: the map is drawn
when it is rendered.
"""

import mappyng as mp
from mappyng.data import load_france_departments, load_europe

europe = load_europe().to_crs(2154)
deps = load_france_departments().to_crs(2154)

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
           facecolor="#B9D9EB", border_radius=10)
    + insets
    + mp.Basemap()
    + mp.DropShadow(europe, query="code_pays_iso3 == 'FRA'")
    + mp.Vector(deps, stroke="#4d4d4d", stroke_width=0.3)
    + mp.Title("Departments of France")
    # Scale bar over the sea, in the Gulf of Lion.
    + mp.ScaleBar(length=100000, label="100 km", position=(0.55, 0.855),
                  opacity=0.8)
    + mp.Source("Basemap: Natural Earth, IGN GéoFLA")
)
