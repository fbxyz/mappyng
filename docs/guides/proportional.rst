Proportional Symbols
====================

:class:`~mappyng.Proportional` draws circles whose area is
proportional to a data column.  Circle centroids are computed from polygon
centroids automatically.

.. code-block:: python

   from mappyng import Map, Basemap, Proportional

   m = Map(gdf, width=800, height="auto")
   m.add(Basemap())
   m.add(Proportional(
       gdf_pts,
       column="population",
       fill="#e31a1c",
       fill_opacity=0.7,
       stroke="#ffffff",
       stroke_width=0.5,
       reference_value=1_000_000,
       reference_radius=20,
       legend={
           "title": "Population",
           "orientation": "nested",
           "values": [100_000, 500_000, 1_000_000],
           "number_format": "space",
           "leader_opacity": 0.5,
       },
   ))

Layer parameters
----------------

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Key
     - Default
     - Description
   * - ``column``
     - required
     - Numeric column for circle sizing.
   * - ``fill``
     - ``"#1f77b4"``
     - Circle fill color.
   * - ``fill_opacity``
     - 0.7
     - Circle fill opacity 0-1.
   * - ``stroke``
     - ``"#ffffff"``
     - Circle stroke color.
   * - ``stroke_width``
     - 0.5
     - Circle stroke width (SVG px).
   * - ``max_radius``
     - 30
     - Maximum circle radius in auto-scale mode (SVG px).
   * - ``reference_value``
     - ``None``
     - Data value that maps exactly to ``reference_radius``.
       Use with ``reference_radius`` to fix the scale across multiple maps.
   * - ``reference_radius``
     - ``None``
     - Radius in SVG px for ``reference_value``.  Both must be set together.
   * - ``on_zoom``
     - ``True``
     - Render on zoom viewport.
   * - ``on_cartouches``
     - ``True``
     - Render on cartouche viewports.
   * - ``legend``
     - ``None``
     - Legend sub-config dict.  See tables below.

Legend parameters (``legend`` sub-dict)
----------------------------------------

Shared fields: see the :ref:`choropleth guide <legend-frame>` (shared fields table
under "Legend parameters").

Proportional-specific fields
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Key
     - Default
     - Description
   * - ``orientation``
     - ``"nested"``
     - Layout: ``"nested"`` (concentric circles), ``"vertical"``,
       or ``"horizontal"``.
   * - ``values``
     - ``None``
     - Explicit list of data values to show.  Auto-generated if None.
   * - ``num_values``
     - 4
     - Number of auto-generated legend values.
   * - ``decimals``
     - 0
     - Decimal places for value labels.
   * - ``number_format``
     - ``"space"``
     - Thousands separator: ``"space"`` (narrow no-break) or ``"none"``.
   * - ``circle_fill``
     - ``None``
     - Override circle fill color in the legend.  Uses layer fill if None.
   * - ``circle_fill_opacity``
     - 0.7
     - Legend circle fill opacity.
   * - ``circle_stroke``
     - ``"black"``
     - Legend circle stroke color.
   * - ``circle_stroke_width``
     - 0.8
     - Legend circle stroke width (SVG px).
   * - ``circle_spacing``
     - ``None``
     - Fixed gap between circles in horizontal mode (SVG px).  Auto if None.
   * - ``label_gap``
     - 4
     - Gap between circle edge and label (SVG px).
   * - ``leader_color``
     - ``"black"``
     - Leader line color (nested mode).
   * - ``leader_width``
     - 0.5
     - Leader line stroke width (SVG px).
   * - ``leader_dash``
     - ``"4 2"``
     - Leader line SVG ``stroke-dasharray``.
   * - ``leader_opacity``
     - 0.6
     - Leader line opacity 0-1.
