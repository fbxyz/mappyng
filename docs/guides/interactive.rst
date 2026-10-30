Interactive Maps
================

The interactive export injects hover tooltips into the SVG via embedded
JavaScript.  The result has no external dependencies and renders
directly in Jupyter or as a standalone HTML file.

The tooltips are set with a :class:`~mappyng.Tooltip` added to the map.
Rendering to a ``.html`` path writes the interactive export:

.. code-block:: python

   import mappyng as mp

   m = (
       mp.Map(gdf, width=800, height="auto")
       + mp.Basemap()
       + mp.Choropleth(gdf, column="population", method="Quantiles")
       + mp.Tooltip(["LIB_GEO", "population"],
                    aliases={"LIB_GEO": "Département"})
   )
   m.render("carte.html")

In Jupyter, a map holding a ``Tooltip`` displays with its tooltips.

``Tooltip(columns, aliases=..., style=..., hover_opacity=...)`` takes the
same values as :meth:`~mappyng.Map.to_interactive` (plus ``hover_opacity``,
a shorthand for ``style={"hover": {"opacity": value}}``). ``to_interactive``
can also be called directly; its arguments override those of the
``Tooltip``:

.. code-block:: python

   interactive = m.to_interactive(
       columns=["LIB_GEO", "population"],
       aliases={"LIB_GEO": "Département"},
       tooltip={
           "background": "rgba(30,30,30,0.92)",
           "text_color": "#ffffff",
           "font_size": 12,
           "border_radius": 6,
           "key_weight": "600",
           "hover": {
               "opacity": 0.8,
               "scale": 1.05,
               "stroke_width_boost": 1.5,
               "shadow": True,
               "shadow_color": "rgba(0,0,0,0.4)",
           },
       },
   )
   interactive.save("carte.html")

``to_interactive`` parameters
------------------------------

.. list-table::
   :header-rows: 1
   :widths: 20 65

   * - Parameter
     - Description
   * - ``columns``
     - List of column names to include in tooltips.  All non-internal
       columns are shown if omitted.
   * - ``aliases``
     - ``{column: display_label}`` mapping for tooltip keys.
   * - ``tooltip``
     - Appearance dict, fields of :class:`~mappyng.interactive.TooltipStyle`.

TooltipStyle fields
-------------------

.. list-table::
   :header-rows: 1
   :widths: 25 20 55

   * - Field
     - Default
     - Description
   * - ``background``
     - ``"rgba(30,30,30,0.92)"``
     - Tooltip background color.
   * - ``text_color``
     - ``"#fff"``
     - Tooltip text color.
   * - ``font_size``
     - 11
     - Font size in px.
   * - ``font_family``
     - system sans-serif
     - Font family.
   * - ``border_radius``
     - 4
     - Tooltip corner radius in px.
   * - ``border_color``
     - ``"rgba(255,255,255,0.15)"``
     - Tooltip border color.
   * - ``key_weight``
     - ``"600"``
     - Font weight for key labels.
   * - ``hover``
     - ``HoverEffect()``
     - Hover effect config: ``True`` (defaults), ``False`` (disabled),
       or a dict of :class:`~mappyng.interactive.HoverEffect` fields.

HoverEffect fields
------------------

.. list-table::
   :header-rows: 1
   :widths: 25 25 50

   * - Field
     - Default
     - Description
   * - ``enabled``
     - ``True``
     - Master switch.  ``False`` disables all hover visuals.
   * - ``transition``
     - ``"all 0.25s ..."``
     - CSS transition timing string.
   * - ``opacity``
     - 1.0
     - Element opacity on hover (< 1 = dim).
   * - ``scale``
     - 1.0
     - Scale factor on hover (1.0 = no scaling).
   * - ``shadow``
     - ``False``
     - Show a CSS drop-shadow on hover.
   * - ``shadow_color``
     - ``"rgba(0,0,0,0.35)"``
     - Shadow color.
   * - ``shadow_dx`` / ``shadow_dy``
     - 0.0 / 4.0
     - Shadow offset in SVG px.
   * - ``shadow_blur``
     - 8.0
     - Shadow blur radius in SVG px.
   * - ``stroke_width_boost``
     - 1.0
     - Extra stroke-width added on hover (0 = no change).
   * - ``stroke_color``
     - ``"#333333"``
     - Override stroke color on hover (``None`` = keep original).
