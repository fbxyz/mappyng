"""
Styles
======

The ``style`` parameter accepts a preset (``"classic"``, ``"modern"``)
or a dict of overrides. Below, the same basemap rendered with two
styles; both maps appear in the gallery.
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
    spacing=12, title_size=6, border_radius=5,
)


def build(style, facecolor):
    return (
        mp.Map(europe, bbox=BBOX_METRO, width=680, height=760, padding=20,
               style=style, facecolor=facecolor)
        + insets
        + mp.Basemap()
        + mp.DropShadow(europe, query="code_pays_iso3 == 'FRA'")
    )


# Classic preset.
m_classic = build("classic", "#bcd2e8") + mp.Title("Classic style")

# Targeted overrides on the classic base.
m_custom = build({"base": "classic", "title_color": "#1a1a2e",
                  "basemap_fill": "#f3ede2", "basemap_edge_color": "#b9a98f"},
                 "#e9e2d4") + mp.Title("Custom style")
