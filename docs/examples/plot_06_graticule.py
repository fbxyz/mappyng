"""
Graticule
=========

``Graticule`` draws meridians and parallels at a step given in
degrees. The map is framed on continental Europe via ``bbox``.

This example uses :meth:`~mappyng.Map.add`, which adds to the map in
place and returns it, so calls can be chained. It is equivalent to
``+``.
"""

import mappyng as mp
from mappyng.data import load_europe

europe = load_europe()

# Continental Europe frame, in EPSG:3857 (the data CRS).
bbox = [-1400000, 4000000, 4700000, 11500000]

m = (
    mp.Map(europe, bbox=bbox, width=820, height="auto", facecolor="#cfe0ee")
    .add(mp.Graticule(step=10.0, stroke="#9bb0c4"))
    .add(mp.Basemap())
    .add(mp.Title("Europe", subtitle="Graticule at a 10-degree step"))
    .add(mp.Source("Basemap: Natural Earth"))
)
m.render("graticule.svg")
