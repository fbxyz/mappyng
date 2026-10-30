"""
United States with Alaska and Hawaii insets
============================================

A choropleth of population density across the contiguous United States,
drawn in the Albers Equal-Area projection (EPSG:5070). Neighbouring
countries fill the background, while Alaska and Hawaii, far from the lower
48, are drawn as enlarged cartouches in their own projections (Alaska
Albers and Web Mercator) so each keeps a faithful shape. The choropleth
classes are shared across the main map and both insets.

Hover a state to read its density.
"""

import geopandas as gpd

import mappyng as mp

STATES_URL = ("https://raw.githubusercontent.com/PublicaMundi/MappingAPI/"
              "master/data/geojson/us-states.json")
COUNTRIES_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-"
                 "vector/master/geojson/ne_110m_admin_0_countries.geojson")

states = gpd.read_file(STATES_URL)
# Repair geometries so they stay valid through the reprojections used by
# the Alaska and Hawaii cartouches.
states["geometry"] = states.make_valid()
states = states.to_crs(5070)

# Bordering countries as a backdrop. The Albers projection (EPSG:5070) is
# only valid around the United States, so distant countries would project
# to garbage coordinates that fall inside the frame. Keep an explicit list
# of North American neighbours (Russia borders the Alaska inset).
NEIGHBOURS = ["Canada", "Mexico", "Russia", "Cuba", "The Bahamas",
              "Greenland", "Guatemala", "Belize", "Honduras", "El Salvador"]
neighbours = gpd.read_file(COUNTRIES_URL)
neighbours["geometry"] = neighbours.make_valid()
neighbours = neighbours[neighbours["ADMIN"].isin(NEIGHBOURS)]
neighbours = neighbours.to_crs(5070)

# Contiguous states frame (Albers), Alaska and Hawaii in their own CRS.
bbox_conus = [-2400000, 250000, 2300000, 3220000]
insets = mp.Insets(
    [
        mp.Inset("Alaska", bbox=[-2257001, 417661, 1492561, 2374335],
                 crs=3338),
        mp.Inset("Hawaii", bbox=[-17784897, 2148846, -17233127, 2539036],
                 crs=3857),
    ],
    spacing=18, title_size=8, size=1.7, border_radius=6, box_shadow=True,
)

m = (
    mp.Map(states, bbox=bbox_conus, width=980, height=680, padding=20,
           facecolor="#bcd6ea", border_radius=10,
           box_shadow={"dx": 3, "dy": 3, "blur": 6, "opacity": 0.2})
    + insets
    + mp.Vector(neighbours, fill="#ececec", stroke="#9a9a9a",
                stroke_width=0.4, position="background")
    + mp.Choropleth(states, column="density", cmap="Blues",
                    method="Quantiles", num_classes=5, stroke_width=0.3,
                    legend=mp.Legend("Inhabitants / sq mi",
                                     orientation="horizontal", decimals=0))
    + mp.Title("United States population density, 2011",
               subtitle="Alaska and Hawaii shown as insets")
    # Scale bar in miles (the map CRS is metric: 300 mi = 482803 m), placed
    # over the open water of the Gulf of Mexico.
    + mp.ScaleBar(length=482803, label="300 mi", position=(0.57, 0.89),
                  opacity=0.85)
    + mp.Source("Density: US Census Bureau, 2011 | Borders: Natural Earth")
    + mp.Tooltip(["name", "density"],
                 aliases={"name": "State", "density": "Inhabitants / sq mi"})
)
