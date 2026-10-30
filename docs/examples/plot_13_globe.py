"""
The world as a globe
====================

An orthographic projection turns the flat world into a sphere seen from
space. The trick is to clip the data to the visible hemisphere before
projecting (distant points would otherwise fold onto invalid
coordinates), then draw on a dark background:

* an ocean disc shaded by a radial gradient, for the spherical volume,
  plus a soft outer glow for the atmosphere;
* the land masses clipped to the same hemisphere;
* a graticule from :class:`~mappyng.Graticule`, whose meridians and
  parallels now bend with the sphere;
* great-circle air routes from Paris to African cities, whose width is
  proportional to the real 2024 passenger traffic on each route.
"""

import math
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyproj import Geod
from shapely.geometry import LineString, Point

import mappyng as mp

URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
       "master/geojson/ne_110m_admin_0_countries.geojson")

R = 6378137.0           # Earth radius (metres) in the orthographic CRS
LON0, LAT0 = 0, 12      # centre of the visible hemisphere
ORTHO = f"+proj=ortho +lat_0={LAT0} +lon_0={LON0} +ellps=WGS84 +units=m +no_defs"
AEQD = f"+proj=aeqd +lat_0={LAT0} +lon_0={LON0} +ellps=WGS84 +units=m +no_defs"

# Visible hemisphere as a polygon in lon/lat: a disc of radius 90 degrees
# (just under, to avoid the degenerate limb) built in an azimuthal
# equidistant CRS, then expressed in WGS84.
cap = gpd.GeoDataFrame(
    geometry=[Point(0, 0).buffer(R * math.pi / 2 * 0.985, resolution=180)],
    crs=AEQD).to_crs(4326)
cap["geometry"] = cap.make_valid()

# Land: clip to the hemisphere first, then project. make_valid() after the
# projection repairs the few polygons that touch the limb.
world = gpd.read_file(URL)
world["geometry"] = world.make_valid()
land = gpd.clip(world, cap)
land = land[~land.is_empty].to_crs(ORTHO)
land["geometry"] = land.make_valid()
land = land[~land.is_empty]

# Ocean sphere.
disc = gpd.GeoDataFrame(geometry=[Point(0, 0).buffer(R, resolution=256)],
                        crs=ORTHO)

# Air routes: great circles from Paris to African cities. The line width
# encodes the real 2024 passenger traffic (Eurostat). Geod.npts samples the
# geodesic, so the densified line bends correctly once projected.
PARIS = (2.35, 48.85)
traffic = pd.read_csv(Path("data") / "paris_africa_air_traffic.csv")

geod = Geod(ellps="WGS84")
lines = [LineString([PARIS] + geod.npts(PARIS[0], PARIS[1], lon, lat, 80)
                    + [(lon, lat)])
         for lon, lat in zip(traffic["lon"], traffic["lat"])]
routes = gpd.GeoDataFrame({"pax": traffic["passengers_2024"]},
                          geometry=lines, crs=4326)
routes = gpd.clip(routes, cap)
routes = routes[~routes.is_empty].to_crs(ORTHO)
pmin, pmax = routes["pax"].min(), routes["pax"].max()

# City markers as small discs (point fills are not drawn, so buffer them).
dots = gpd.GeoDataFrame(
    geometry=[Point(xy) for xy in zip(traffic["lon"], traffic["lat"])],
    crs=4326).to_crs(ORTHO)
dots["geometry"] = dots.buffer(55000)
paris = gpd.GeoDataFrame(geometry=[Point(PARIS)], crs=4326).to_crs(ORTHO)
paris["geometry"] = paris.buffer(80000)

# Ocean shaded as a sphere: the focal point sits up and to the left, so the
# highlight reads as a light source and the colour deepens towards the limb.
ocean = mp.RadialGradient(
    [(0.0, "#3d8fc0"), (0.55, "#1c5d86"), (1.0, "#0a3553")],
    fx=0.36, fy=0.34, r=0.62)
# Limb darkening on top of everything: transparent at the highlight, dark at
# the edge, so land and ocean share the same spherical shading.
shade = mp.RadialGradient(
    [(0.0, "#06121f", 0.0), (0.6, "#06121f", 0.0), (1.0, "#06121f", 0.6)],
    fx=0.36, fy=0.34)

# Air routes, drawn above the shading so they stay bright. Line WIDTH is
# proportional to 2024 passenger traffic, all in the same red.
route_lines = []
for _, route in routes.iterrows():
    t = (route["pax"] - pmin) / (pmax - pmin)
    line = gpd.GeoDataFrame(geometry=[route.geometry], crs=routes.crs)
    route_lines.append(mp.Vector(line, fill="none", stroke="#e63946",
                                 stroke_width=0.6 + 2.6 * t,
                                 stroke_linecap="round", position="top"))

# Widen the frame beyond the disc so the atmosphere glow is not clipped by
# the viewport edge (the bbox is the map's clipping window).
margin = 0.18 * R
m = (
    mp.Map(disc, bbox=[-R - margin, -R - margin, R + margin, R + margin],
           width=860, height=860, padding=24,
           style={"base": "classic", "title_color": "#e8edf4"},
           background="#070b18")
    + ocean
    + shade
    # Atmosphere: a centred, blurred glow of the disc shape.
    + mp.DropShadow(disc, dx=0, dy=0, blur=22, color="#48cae4",
                    opacity=0.85, fill="#48cae4")
    # Stacking with explicit z values: atmosphere glow (z=1) < ocean (2) <
    # graticule (3) < land (5, the default background depth). The grid
    # therefore shows over the sea and is hidden behind the continents.
    + mp.Vector(disc, fill=ocean.url, stroke="#0b3a57", stroke_width=1.2,
                z=2)
    + mp.Graticule(step=20, stroke="#bcdcef", opacity=0.55,
                   stroke_width=0.6, z=3)
    + mp.Vector(land, fill="#e9edc9", stroke="#b9c79a", stroke_width=0.3)
    + mp.Vector(disc, fill=shade.url, stroke="none", position="top")
    # A wide, faint red stroke under each route makes it glow.
    + mp.Vector(routes, fill="none", stroke="#e63946", stroke_width=4.0,
                stroke_opacity=0.16, stroke_linecap="round", position="top")
    + route_lines
    + mp.Vector(dots, fill="#e63946", stroke="#ffffff", stroke_width=0.4,
                position="top")
    + mp.Vector(paris, fill="#ffffff", stroke="#e63946", stroke_width=0.8,
                position="top")
    + mp.Title("Air routes from Paris",
               subtitle="Line width: 2024 passenger traffic")
    + mp.Source("Traffic: Eurostat (avia_par_fr, 2024) | "
                "Borders: Natural Earth")
)
