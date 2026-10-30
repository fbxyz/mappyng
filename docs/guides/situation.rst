Situation (Point Symbols)
=========================

:class:`~mappyng.Situation` draws categorical or uniform point
markers.  Polygon geometries are automatically converted to centroids.

.. code-block:: python

   from mappyng import Map, Basemap, Situation

   m = Map(gdf, width=800, height="auto")
   m.add(Basemap())

   # Categorical markers
   m.add(Situation(
       gdf_pts,
       column="type",
       symbol={
           "Hospital": {"marker": "cross",  "fill": "#e63946", "size": 12},
           "School":   {"marker": "square", "fill": "#457b9d", "size": 10},
           "Park":     {"marker": "circle", "fill": "#2a9d8f", "size": 9,
                        "fill_opacity": 0.8},
       },
       legend={"title": "Facilities", "columns_n": 2, "col_gap": 30},
   ))

   # Uniform marker
   m.add(Situation(gdf_pts, marker="star", fill="#f4a261", size=14))

   # Composite marker
   m.add(Situation(
       gdf_pts,
       marker="circle+cross",
       fill="#264653",
       inner_fill="#ffffff",
       size=12,
   ))

   # Custom SVG icon
   m.add(Situation(gdf_pts, marker="icons/hospital.svg", size=16))

Layer parameters
----------------

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Key
     - Default
     - Description
   * - ``column``
     - ``None``
     - Categorical column (multi-symbol mode).  Omit for uniform mode.
   * - ``symbol``
     - ``None``
     - ``{category: {marker, color, size, ...}}`` mapping (multi-symbol mode).
   * - ``marker``
     - ``"circle"``
     - Shape name (uniform mode or default for categories without an explicit entry).

       Built-in: ``"circle"``, ``"square"``, ``"triangle"``, ``"diamond"``,
       ``"star"``, ``"cross"`` / ``"plus"``, ``"x"``, ``"pentagon"``,
       ``"hexagon"``.

       Composite: ``"circle+cross"`` (any two shapes joined with ``+``).

       Custom SVG: path to a ``.svg`` file.
   * - ``color``
     - ``"#e31a1c"``
     - Fill color (uniform mode).
   * - ``size``
     - 8.0
     - Marker size in SVG px (uniform mode).
   * - ``stroke``
     - ``"#ffffff"``
     - Stroke color (uniform mode).
   * - ``stroke_width``
     - 0.5
     - Stroke width (SVG px).
   * - ``fill_opacity``
     - 1.0
     - Fill opacity 0-1.
   * - ``inner_fill``
     - ``None``
     - Fill for inner shape in composite markers.
   * - ``inner_stroke``
     - ``None``
     - Stroke for inner shape in composite markers.
   * - ``label``
     - ``None``
     - Legend label text (uniform mode).
   * - ``on_zoom``
     - ``True``
     - Render on zoom viewport.
   * - ``on_cartouches``
     - ``True``
     - Render on cartouche viewports.
   * - ``legend``
     - ``None``
     - Legend sub-config dict.  See table below.

Legend parameters (``legend`` sub-dict)
----------------------------------------

Shared fields: see the choropleth guide (shared fields table under
"Legend parameters").

Situation-specific fields
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Key
     - Default
     - Description
   * - ``marker_size``
     - 10.0
     - Marker preview size in the legend (SVG px).
   * - ``label_gap``
     - 6.0
     - Gap between marker preview and label text (SVG px).
   * - ``row_spacing``
     - 4.0
     - Vertical gap between legend rows (SVG px).
   * - ``columns_n``
     - 1
     - Number of legend columns.
   * - ``col_gap``
     - 20.0
     - Horizontal gap between columns (SVG px).
