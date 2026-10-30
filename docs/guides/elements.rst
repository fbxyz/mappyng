Element catalogue
=================

One minimal example per element, with the map it produces. Every example is
executed when the documentation is built, so the code shown is the code that
draws the map beneath it. The gallery has larger, complete maps.

All the examples share these variables: ``mp`` (mappyng), ``pd``, ``gpd``,
``europe``, ``regions`` and ``deps`` (GeoDataFrames in Lambert-93, EPSG:2154),
``BBOX`` (the mainland France frame) and ``DATA`` (the folder of the sample
CSV files).

Map and Basemap
---------------

:class:`~mappyng.Map` is the canvas: data extent, size, background.
:class:`~mappyng.Basemap` draws the context layer behind the data.

.. mappyng-example::

   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#cfe0ee")
       + mp.Basemap()
   )

Vector
------

:class:`~mappyng.Vector` draws any geometry with a fixed style.

.. mappyng-example::

   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#cfe0ee")
       + mp.Basemap()
       + mp.Vector(regions, fill="#fff3c4", stroke="#b45309", stroke_width=0.8)
   )

Choropleth
----------

:class:`~mappyng.Choropleth` colours areas by a numeric column, with a
classification method and a legend. See :doc:`choropleth`.

.. mappyng-example::

   df = pd.read_csv(DATA / "cardio_mortalite_dep.csv", dtype={"code_dep": str})
   d = deps.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")
   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#cfe0ee")
       + mp.Basemap()
       + mp.Choropleth(d, column="taux_mortalite", cmap="Reds",
                       method="Quantiles", num_classes=5, stroke_width=0.15,
                       legend=mp.Legend("Deaths / 100,000"))
   )

Category
--------

:class:`~mappyng.Category` colours areas by a qualitative column.

.. mappyng-example::

   d = deps.copy()
   d["zone"] = d["COD_GEO"].map(
       lambda c: "Overseas" if c.startswith("97") else
                 "Corsica" if c.startswith("2") and c[1] in "AB" else
                 "North" if c in {"59", "62", "80", "02", "60"} else "Other")
   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#cfe0ee")
       + mp.Basemap()
       + mp.Category(d, column="zone",
                     fill_map={"North": "#1f78b4", "Corsica": "#e31a1c",
                               "Other": "#d9d9d9"},
                     default_fill="#eeeeee",
                     legend=mp.Legend("Zone"))
   )

Proportional
------------

:class:`~mappyng.Proportional` draws a circle whose area follows an absolute
quantity. See :doc:`proportional`.

.. mappyng-example::

   df = pd.read_csv(DATA / "canicule_exces_75_2025.csv", dtype={"code_dep": str})
   d = deps.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")
   pts = d[d["exces_deces"].notna()].copy()
   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#cfe0ee")
       + mp.Basemap()
       + mp.Vector(deps, fill="#f4f1ea", stroke="#bbbbbb", stroke_width=0.3)
       + mp.Vector(regions, stroke="#666666", stroke_width=0.6)
       + mp.Proportional(pts, column="exces_deces", fill="#d7301f",
                         fill_opacity=0.6, stroke="#7f0000",
                         legend=mp.Legend("Excess deaths"))
   )

Situation
---------

:class:`~mappyng.Situation` places a marker per feature, chosen by a category.
See :doc:`situation`.

.. mappyng-example::

   df = pd.read_csv(DATA / "helistations.csv")
   pts = gpd.GeoDataFrame(
       df, geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
       crs="EPSG:4326").to_crs(2154)
   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#cfe0ee")
       + mp.Basemap()
       + mp.Vector(regions, fill="#f4f1ea", stroke="#999999", stroke_width=0.3)
       + mp.Situation(
           pts, column="vol_nuit",
           symbol={"Night flight": {"marker": "circle", "fill": "#1f78b4", "size": 6},
                   "Day only": {"marker": "triangle", "fill": "#e31a1c", "size": 8}},
           legend=mp.Legend("Helistation"))
   )

Label
-----

:class:`~mappyng.Label` places names automatically, avoiding overlaps. See
:doc:`labels` and the gallery example :doc:`/gallery/plot_05_labels`.

Graticule
---------

:class:`~mappyng.Graticule` draws meridians and parallels. See the gallery
example :doc:`/gallery/plot_06_graticule` (and :doc:`/gallery/plot_13_globe`
for a globe).

Title and Source
----------------

:class:`~mappyng.Title` (with an optional subtitle) and
:class:`~mappyng.Source` are text elements, placed by default at the top and
the bottom of the map.

.. mappyng-example::

   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#cfe0ee")
       + mp.Basemap()
       + mp.Title("Regions of France", subtitle="Mainland and Corsica")
       + mp.Source("Source: IGN GéoFLA")
   )

ScaleBar and NorthArrow
-----------------------

:class:`~mappyng.ScaleBar` and :class:`~mappyng.NorthArrow`. Both accept a
``position``; see :doc:`placement`.

.. mappyng-example::

   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#cfe0ee")
       + mp.Basemap()
       + mp.ScaleBar(length=200000, label="200 km", position=(0.05, 0.93))
       + mp.NorthArrow(position=(0.88, 0.1))
   )

Legend
------

:class:`~mappyng.Legend` customises the legend of a thematic layer: title,
orientation, decimals, swatch shape.

.. mappyng-example::

   df = pd.read_csv(DATA / "cardio_mortalite_dep.csv", dtype={"code_dep": str})
   d = deps.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")
   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#cfe0ee")
       + mp.Basemap()
       + mp.Choropleth(d, column="taux_mortalite", cmap="Blues", num_classes=4,
                       stroke_width=0.15,
                       legend=mp.Legend("Rate", orientation="horizontal",
                                        decimals=0, swatch_shape="rounded"))
   )

DropShadow and OceanGradient
----------------------------

:class:`~mappyng.DropShadow` lifts a layer; :class:`~mappyng.OceanGradient`
lightens the water along the coasts. See :doc:`layout`.

.. mappyng-example::

   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#B9D9EB")
       + mp.OceanGradient(europe)
       + mp.Basemap()
       + mp.Vector(regions, fill="#f4f1ea", stroke="#888888", stroke_width=0.3)
       + mp.DropShadow(europe, query="code_pays_iso3 == 'FRA'")
   )

Inset
-----

:class:`~mappyng.Inset` shows a distant area (the overseas territories) in a
cartouche; :class:`~mappyng.Insets` lays several of them out. See
:doc:`layout` and the gallery examples :doc:`/gallery/plot_02_choropleth`
and :doc:`/gallery/plot_12_usa` (Alaska and Hawaii).

Zoom
----

:class:`~mappyng.Zoom` enlarges an area of the map in a box. Thematic layers
are redrawn in the box; plain ``Vector`` layers are not. See :doc:`layout` and
the gallery example :doc:`/gallery/plot_04_situation` (Paris region).

Tooltip
-------

:class:`~mappyng.Tooltip` adds hover tooltips. **Hover a department** below.
See :doc:`interactive`.

.. mappyng-example::

   df = pd.read_csv(DATA / "cardio_mortalite_dep.csv", dtype={"code_dep": str})
   d = deps.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")
   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#cfe0ee")
       + mp.Basemap()
       + mp.Choropleth(d, column="taux_mortalite", cmap="Greens", num_classes=5,
                       stroke_width=0.15)
       + mp.Tooltip(["LIB_GEO", "taux_mortalite"],
                    aliases={"LIB_GEO": "Department",
                             "taux_mortalite": "Rate"})
   )

BorderContrast
--------------

:class:`~mappyng.BorderContrast` makes borders between neighbours of similar
colour visible. The ``"check"`` mode reveals them in magenta.

.. mappyng-example::

   df = pd.read_csv(DATA / "cardio_mortalite_dep.csv", dtype={"code_dep": str})
   d = deps.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")
   m = (
       mp.Map(europe, bbox=BBOX, width=420, height="auto", facecolor="#cfe0ee")
       + mp.Basemap()
       + mp.Choropleth(d, column="taux_mortalite", cmap="Reds", num_classes=5,
                       stroke="none", border_contrast=mp.BorderContrast())
   )

Tile and Raster
---------------

:class:`~mappyng.Tile` (web map tiles) needs network access and
:class:`~mappyng.Raster` needs a GeoTIFF file, so they are not executed here:
see :doc:`tiles` and the *Tiles* example of the gallery.
