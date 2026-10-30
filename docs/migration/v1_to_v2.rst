Migration from v1 (matplotlib) to v2 (SVG)
===========================================

The import statement is unchanged::

   from mappyng import Map

The constructor signature is preserved.  The drawing API, however, is now
**object-based**: instead of ``m.add_choropleth(gdf, {...})`` you build a
layer and add it with ``m.add(Choropleth(gdf, ...))``.  The dict-based
``add_*`` helpers have been removed (see :doc:`../guides/quickstart`).
The parameter names below still apply; they are now keyword arguments of
the corresponding layer class.

Layer and element names
-----------------------

Layers and chrome are objects added with ``+`` or ``m.add(...)`` (see
:doc:`../guides/quickstart`). The layer classes lost their ``Layer``
suffix; the former names were removed in mappyng 2.0 (they had emitted a
``DeprecationWarning`` since the layer classes were introduced).

.. list-table::
   :header-rows: 1
   :widths: 40 60

   * - Former
     - Current
   * - ``ChoroplethLayer``, ``CategoryLayer``, ``ProportionalLayer``,
       ``SituationLayer``, ``LabelLayer``, ``VectorLayer``
     - ``Choropleth``, ``Category``, ``Proportional``, ``Situation``,
       ``Label``, ``Vector``
   * - ``BasemapLayer``, ``TileLayer``, ``RasterLayer``,
       ``GraticuleLayer``
     - ``Basemap``, ``Tile``, ``Raster``, ``Graticule``
   * - ``m.title(...)``, ``m.source(...)``, ``m.scale_bar(...)``,
       ``m.north_arrow(...)``
     - ``Title``, ``Source``, ``ScaleBar``, ``NorthArrow`` (the methods
       remain as shortcuts)
   * - ``cartouche_params={0: {...}}``
     - ``Insets([Inset(...), ...])`` (the parameter remains)
   * - ``m.add_zoom({...})``
     - ``Zoom(bbox, ...)``
   * - ``m.add_shadow(gdf, {...})``
     - ``DropShadow(gdf, ...)``; ``stdDeviation`` is now ``blur``
   * - ``m.add_radial_gradient(...)``
     - ``RadialGradient(...)``, referenced with ``fill=gradient.url``
   * - ``m.to_interactive(columns=..., aliases=...)``
     - ``Tooltip(columns, aliases=...)`` and ``m.render("map.html")``

``m.add(layer)`` now returns the map instead of the layer; the layer
still receives its ``id``. ``Vector`` is drawn in the cartouches by
default (``on_cartouches=True``), like the thematic layers.

Renamed parameters
------------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - v1 parameter
     - v2 parameter
     - Notes
   * - ``symbol["alpha"]``
     - ``fill_opacity``
     - Proportional and situation layers.
   * - ``symbol["edgecolors"]``
     - ``stroke``
     - Proportional and situation layers.
   * - ``symbol["linewidth"]``
     - ``stroke_width``
     - Proportional and situation layers.
   * - ``line_color`` (leader)
     - ``leader_color``
     - ProportionalLegendConfig.
   * - ``line_width`` (leader)
     - ``leader_width``
     - ProportionalLegendConfig.
   * - ``line_style`` (leader)
     - ``leader_dash``
     - SVG dasharray string instead of matplotlib line style.
   * - ``line_alpha`` (leader)
     - ``leader_opacity``
     - ProportionalLegendConfig.
   * - ``circle_color``
     - ``circle_fill``
     - ProportionalLegendConfig.
   * - ``rounding``
     - ``decimals``
     - Legend label decimal places.
   * - ``edgecolor`` (choropleth)
     - ``stroke``
     - Choropleth.
   * - ``linewidth`` (choropleth)
     - ``stroke_width``
     - Choropleth.

Removed parameters
------------------

These v1 parameters are not available in v2:

.. list-table::
   :header-rows: 1
   :widths: 25 75

   * - v1 parameter
     - Reason
   * - ``symbol["marker"]`` (non-circle shapes in proportional)
     - v2 proportional symbols are always circles.
   * - ``symbol["zorder"]``
     - Z-order is managed globally by :class:`~mappyng.config.ZOrderConfig`.
   * - ``adjust_size``
     - v2 uses ``max_radius`` for auto-scaling; fixed scale via ``reference_radius``.
   * - ``units`` (legend position)
     - v2 always uses SVG pixel coordinates.
   * - PNG custom markers (``situation.py``)
     - v2 is SVG-native only.  Use custom SVG files instead.

New parameters in v2
--------------------

These parameters are not present in v1:

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Parameter
     - Method / class
     - Description
   * - ``font_scale``
     - :class:`~mappyng.Map`
     - Global font size multiplier.
   * - ``reference_radius``
     - Proportional
     - Fixed circle radius in SVG px (replaces ``reference_size``).
   * - ``num_values``
     - ProportionalLegendConfig
     - Number of auto-generated legend values.
   * - ``circle_fill_opacity``
     - ProportionalLegendConfig
     - Legend circle fill opacity.
   * - ``columns_n`` / ``col_gap``
     - SituationLegendConfig
     - Multi-column legend layout.
   * - ``hatch_style``
     - ChoroplethLegendConfig
     - SVG hatch pattern for legend swatches.
   * - ``hover_opacity``
     - ``Tooltip``
     - Hover effect opacity: ``Tooltip(columns, hover_opacity=0.7)``, or
       ``tooltip={"hover": {"opacity": 0.7}}``. The ``to_interactive``
       argument of the same name was removed in 2.0.
   * - ``label_position`` / ``label_format``
     - ChoroplethLegendConfig (horizontal)
     - Label centering and range formatting for horizontal legends.

Tile basemaps
-------------

v1 used ``contextily`` (matplotlib-based).  v2 downloads tiles directly::

   # v1
   import contextily as cx
   cx.add_basemap(ax, source=cx.providers.CartoDB.Positron)

   # v2
   from mappyng import Tile
   m.add(Tile(source="cartodb_positron"))

Requires ``pip install mappyng[tile]``.

Label placement
---------------

v1 used ``adjustText`` (matplotlib).  v2 uses a pure Python simulated-annealing
implementation with geometric obstacle avoidance::

   # v1
   m.add_toponyms(gdf, column="nom", max_labels=20)

   # v2
   from mappyng import Label
   m.add(Label(gdf, column="nom", max_labels=20, n_sweeps=50))

Exceptions
----------

v2 exposes a typed exception hierarchy not present in v1::

   from mappyng.errors import MapError, DataError, RenderError
