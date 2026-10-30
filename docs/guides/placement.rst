.. _placing-elements:

Placing elements
================

The title, scale bar, north arrow, source line and legends all take a
``position``. They understand **the same forms**, so a position written for one
element works for any other. Without a ``position`` an element sits at its
default place (a corner of the map for the scale bar and the north arrow, above
the map for the title, below it for legends).

.. code-block:: python

   import mappyng as mp

   m = (
       mp.Map(gdf, bbox=[90000, 6040000, 1280000, 7150000])
       + mp.Basemap()
       + mp.ScaleBar(length=100_000, position={"lon": 3.3, "lat": 42.95})
       + mp.NorthArrow(position={"x": "92%", "y": "8%"})
   )

A complete example is in the gallery: :doc:`../gallery/plot_16_placement`.

Forms of ``position``
---------------------

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Form
     - Meaning
   * - ``(0.46, 0.9)`` or ``{"x": 0.46, "y": 0.9}``
     - Fractions of the **map area** (the drawn extent, not the whole
       document): ``(0, 0)`` is its top-left corner and ``(1, 1)`` its
       bottom-right corner. Values outside ``[0, 1]`` place the element outside
       the map, for example ``y=1.05`` for a line under it.
   * - ``("46%", "90%")`` or ``{"x": "46%", "y": "90%"}``
     - The same, written as percentages.
   * - ``{"px": 120, "py": 80}``
     - SVG pixels in the document.
   * - ``{"geo": (x, y)}``
     - A point in the **map CRS**: metres for a Lambert-93 map, degrees for a
       lon/lat map.
   * - ``{"geo": (x, y), "crs": "EPSG:3035"}``
     - A point in another CRS, reprojected to the map CRS.
   * - ``{"lon": 4.0, "lat": 42.6}``
     - A point in WGS 84 longitude/latitude, whatever the map CRS.

Forms can be mixed freely from one element to the next. Within a single
position, write one form only: if several keys are present, ``geo`` is used
first, then ``lon``/``lat``, then ``px``/``py``, and ``x``/``y`` last, so the
others are ignored without a warning.

What the point designates
-------------------------

The point is the element's **anchor**, which differs from one element to the
next:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - Element
     - Anchor
   * - :class:`~mappyng.ScaleBar`
     - The **left end** of the bar. It extends to the right, over the length
       of the bar.
   * - :class:`~mappyng.NorthArrow`
     - The **tip** of the arrow head. The label sits above it.
   * - :class:`~mappyng.Source`
     - The **start** of the text, aligned by ``text_anchor`` and turned by
       ``rotation``.
   * - :class:`~mappyng.Title`
     - The **baseline of the last line** (the subtitle if there is one), aligned
       by ``loc``: ``"left"`` starts at the point, ``"center"`` centres on it,
       ``"right"`` ends at it. ``offset_x`` and ``offset_y`` still apply.
   * - Legends
     - The **top-left corner** of the legend, title included. The ``position``
       goes in the legend options: ``Legend("Title", position={...})`` or the
       ``legend`` dict of the layer.

Anchoring to a place
--------------------

Geographic positions tie an element to a place rather than to a spot on the
page, so it stays put if you change the document size or the bounding box. A
typical use is a scale bar over the sea, clear of the coast:

.. code-block:: python

   mp.ScaleBar(length=100_000, position={"lon": 3.3, "lat": 42.95})

``lon``/``lat`` are always WGS 84. To use another CRS, give it explicitly:

.. code-block:: python

   mp.NorthArrow(position={"geo": (3_773_000, 2_229_000), "crs": "EPSG:3035"})

Finding the right coordinates is easiest by trial: render, look, move. The
:func:`~mappyng.position.resolve_position` function turns any ``position`` into
SVG pixels if you need to compute a placement in code.

What can go wrong
-----------------

A malformed or impossible position raises a
:class:`~mappyng.errors.LayoutError` with a message saying why, instead of
silently placing the element at a default spot.

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Position
     - Problem
   * - ``"centre"``, ``(0.5,)``, ``{"geo": 3}``
     - Not an ``(x, y)`` pair or a recognised dict.
   * - ``{"lon": 2.0}``
     - ``lon`` and ``lat`` are both required.
   * - ``{"x": "abc"}``
     - Not a number or a percentage.
   * - ``{"lon": 2.0, "lat": 48.0}`` on data with no CRS
     - A CRS is needed to convert geographic coordinates. Set one on the
       GeoDataFrame, or use ``{"geo": (x, y)}`` in the map's own coordinates.
   * - A point on the hidden side of an orthographic globe
     - The projection cannot represent it.

In YAML
-------

Positions are plain values, so they survive ``to_yaml`` and ``from_yaml``:

.. code-block:: yaml

   chrome:
     scale_bar:
       length: 100000
       position:
         lon: 3.3
         lat: 42.95
     title:
       text: Mortality
       position:
         x: 2%
         y: -1%

Only the main map is a target for positions: the scale bar, north arrow, source,
title and legends belong to the main viewport. Cartouches and the zoom window
have their own frame and are placed with ``Insets`` and ``Zoom``.
