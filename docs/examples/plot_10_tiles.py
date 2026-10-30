"""
Topographic tiles (SRTM relief)
===============================

A tiled basemap drawn from XYZ web tiles. OpenTopoMap renders SRTM
elevation as shaded relief with contour lines, here over the northern
French Alps. The tiles are fetched in Web Mercator, warped into the
Lambert-93 map CRS and embedded as a single image, with the department
boundaries drawn on top.

Tiles are cached on disk after the first download.
"""

import mappyng as mp
from mappyng.data import load_france_departments

deps = load_france_departments().to_crs(2154)
alps = deps[deps["COD_GEO"].isin(["74", "73", "38", "05", "26", "04"])]

# Landscape frame over the northern Alps (Lambert-93).
bbox_alps = [880000, 6390000, 1040000, 6560000]

m = mp.Map(alps, bbox=bbox_alps, width=900, height=820, padding=20,
           border_radius=8,
           box_shadow={"dx": 3, "dy": 3, "blur": 6, "opacity": 0.2})
m.add(
    mp.Tile(source="topo"),  # OpenTopoMap: SRTM hillshade and contours
    mp.Vector(alps, fill="none", stroke="#1a1a1a", stroke_width=0.6,
              position="top"),
    mp.Title("Northern French Alps",
             subtitle="Shaded relief from SRTM elevation"),
    mp.ScaleBar(length=25000, label="25 km", position=(0.05, 0.06),
                opacity=0.85),
    mp.Source("Tiles: OpenTopoMap (CC-BY-SA), SRTM | "
              "Boundaries: IGN GéoFLA"),
)
