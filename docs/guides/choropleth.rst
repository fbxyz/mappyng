Choropleth Maps
===============

:class:`~mappyng.Choropleth` classifies a numeric column using
mapclassify and draws filled polygons.  The legend is drawn automatically
below the main map.

.. code-block:: python

   import geopandas as gpd
   from mappyng import Map, Basemap, Choropleth

   gdf = gpd.read_file("departements_population.gpkg")

   m = Map(gdf, width=800, height="auto")
   m.add(Basemap())
   m.add(Choropleth(
       gdf,
       column="pop",
       cmap="YlOrRd",
       method="Quantiles",
       num_classes=5,
       stroke_width=0.15,
       legend={
           "title": "Population",
           "decimals": 0,
           "orientation": "vertical",
       },
   ))
   m.render("choropleth.svg")

Layer parameters
----------------

These are passed as keyword arguments to ``Choropleth(gdf, ...)``.

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Key
     - Default
     - Description
   * - ``column``
     - required
     - Numeric column to classify.
   * - ``cmap``
     - ``"YlOrRd"``
     - Colormap name (``"YlOrRd"``, ``"Blues"``, ``"Greens"``, ``"Reds"``,
       ``"RdYlGn"``) or a list of hex strings of length ``num_classes``.
   * - ``method``
     - ``"FisherJenks"``
     - Classification scheme: ``"EqualInterval"``, ``"Quantiles"``,
       ``"FisherJenks"``, ``"Q6"``, ``"StdMean"``, or a list of custom
       break values (length ``num_classes + 1``).
   * - ``num_classes``
     - 5
     - Number of classes (4-7).  Ignored when ``method`` is a list.
   * - ``stroke``
     - from style
     - Polygon outline color.
   * - ``stroke_width``
     - from style
     - Polygon outline width in SVG px.
   * - ``dissolve``
     - ``False``
     - Dissolve polygons by class before rendering (reduces SVG size).
   * - ``border_contrast``
     - ``None``
     - Make the borders between neighbours of similar colour visible
       (``True``, ``"check"`` or a dict).  See :ref:`border-contrast`.
   * - ``on_zoom``
     - ``True``
     - Render this layer on the zoom viewport.
   * - ``on_cartouches``
     - ``True``
     - Render this layer on cartouche viewports.
   * - ``legend``
     - ``None``
     - Legend sub-config dict.  See tables below.

.. _border-contrast:

Borders between similar colours
-------------------------------

When two touching areas are both light, or both dark, and the outline is close
to them in tone, the border between them disappears and the two areas read as
one. ``border_contrast`` finds those shared borders and redraws **only them**,
in a colour that stands out, on top of the polygons. The polygons keep their own
outline, and every other border is left as it is.

.. code-block:: python

   mp.Choropleth(gdf, column="rate", cmap="Blues", stroke="#eeeeee",
                 border_contrast=True)

The gallery compares the three states side by side:
:doc:`../gallery/plot_18_border_contrast`.

**Checking first.** ``border_contrast="check"`` does not change the map's look,
it reveals the problem: every weak border is drawn thick in magenta and a
warning gives their number and the first pairs of areas concerned. Once you have
seen which borders are hard to read, switch to ``True`` to fix them, or keep
``"check"`` as a quick audit of a palette.

**How a border is judged.** The contrast ratio is the WCAG one, from 1 (same
tone) to 21 (black on white). A shared border is *weak*, and gets redrawn, when
**both** conditions hold:

* its two fills are close (ratio below ``fill_ratio``): the change of colour
  alone does not show the border;
* the outline is close to at least one of the fills (ratio below
  ``stroke_ratio``): the outline does not show it either.

Two fills of the same class are the extreme case (ratio 1). A border between a
light and a dark area is never touched: the colour change is enough. For a weak
border, ``light`` and ``dark`` are tried, and the one that contrasts most with
the two fills is used, provided it does better than the current outline. So two
pale areas get a dark line and two dark areas a light one.

**Options.** ``True`` or ``"fix"`` use the defaults. A dict, or a
:class:`~mappyng.BorderContrast`, sets any of them:

.. list-table::
   :header-rows: 1
   :widths: 22 18 60

   * - Option
     - Default
     - Meaning
   * - ``mode``
     - ``"fix"``
     - ``"fix"`` redraws the weak borders; ``"check"`` reveals them.
   * - ``fill_ratio``
     - 1.5
     - Fills with a contrast ratio below this are alike. Raise it to also treat
       moderately different neighbours as weak.
   * - ``stroke_ratio``
     - 2.0
     - An outline with a ratio below this against a fill does not show.
   * - ``light``, ``dark``
     - ``"#ffffff"``, ``"#222222"``
     - The two colours tried for a weak border.
   * - ``check_color``
     - ``"#ff00ff"``
     - Colour of the weak borders in ``"check"`` mode.
   * - ``width_factor``
     - 1.0
     - Width of a redrawn border relative to the outline width.

.. code-block:: python

   mp.Choropleth(gdf, column="rate", stroke="#ffffff",
                 border_contrast={"dark": "#003366", "width_factor": 1.5})

**Good to know.**

* It applies to the main map, the zoom and the cartouches, each judged on what
  it draws. :class:`~mappyng.Category` accepts the same option, for categories
  with close colours.
* The shared borders are found from the polygons' own geometry, so adjacent
  areas must share their boundary exactly, as administrative layers do. Gaps or
  overlaps between neighbours hide the border from the search. With
  ``simplify``, the redrawn lines are simplified in the same way.
* The colours are the nominal fill colours. With ``opacity_column`` the
  rendered tone also depends on what lies under the area, unless you set
  ``blend_background``; the check uses the blended colour when you do.
* A map with no outline (``stroke="none"``) counts as having a fully
  transparent outline: neighbours of similar colour are all weak.
* The redrawn borders ignore the pointer, so hover tooltips of an interactive
  export still reach the areas below.
* Areas without data (hatched) are not part of the check.
* The option is plain data, so it survives ``to_yaml``.

Legend parameters (``legend`` sub-dict)
----------------------------------------

Shared fields (all legend types)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Key
     - Default
     - Description
   * - ``title``
     - ``None``
     - Legend title text.
   * - ``subtitle``
     - ``None``
     - Subtitle rendered below the title.
   * - ``title_fontsize``
     - from style
     - Title font size.
   * - ``title_fontcolor``
     - from style
     - Title font color.
   * - ``title_fontweight``
     - from style
     - Title font weight (e.g. ``"bold"``).
   * - ``title_fontfamily``
     - from style
     - Title font family.
   * - ``title_max_chars``
     - 35
     - Characters per line before title wraps.
   * - ``title_offset_x``
     - 0.0
     - Additional horizontal offset for title (SVG px).
   * - ``title_offset_y``
     - 0.0
     - Additional vertical offset for title (SVG px).
   * - ``fontsize``
     - from style
     - Label font size.
   * - ``fontcolor``
     - from style
     - Label font color.
   * - ``fontweight``
     - from style
     - Label font weight.
   * - ``fontfamily``
     - from style
     - Label font family.
   * - ``hatch_style``
     - from style
     - SVG hatch fill for swatches: ``"///"``, ``"\\\\"``, ``"xxx"``,
       ``"..."``, ``"|||"``, ``"---"``.
   * - ``hatch_color``
     - from style
     - Hatch line color.
   * - ``spacing``
     - 0.01
     - Extra vertical offset added to auto-position (fraction of content height).
   * - ``position``
     - ``None``
     - Manual position ``{"x": frac, "y": frac}`` (0,0 = top-left, 1,1 = bottom-right).
   * - ``frame``
     - ``None``
     - Background frame: ``False`` = none, ``True`` = default frame,
       dict = overrides (see :ref:`legend-frame`).

Choropleth-specific fields
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Key
     - Default
     - Description
   * - ``decimals``
     - 1
     - Decimal places for class boundary labels.
   * - ``orientation``
     - ``"horizontal"``
     - Legend layout: ``"horizontal"`` or ``"vertical"``.
   * - ``swatch_size``
     - ``None``
     - Global width override for all swatches (horizontal **and** vertical
       modes).  Height is always derived as ``swatch_size / phi`` (golden
       ratio).  Overrides ``swatch_width`` and ``vertical_swatch_width``.
       Example: ``"swatch_size": 40``.
   * - ``swatch_width``
     - 30
     - Color swatch width in horizontal mode (SVG px).
   * - ``swatch_height``
     - auto
     - Swatch height in horizontal mode.
       Defaults to ``swatch_width / phi`` (golden ratio).
   * - ``swatch_spacing``
     - 2
     - Gap between swatches (SVG px).
   * - ``swatch_shape``
     - ``"rect"``
     - Swatch shape: ``"rect"``, ``"rounded"`` (rounded corners) or
       ``"circle"`` (disc, diameter equal to the shorter side). Also
       applies to the no-data swatch.
   * - ``swatch_radius``
     - auto
     - Corner radius of ``"rounded"`` swatches (SVG px). Defaults to a
       quarter of the shorter side.
   * - ``label_rotation``
     - 0
     - Label rotation in degrees.
   * - ``label_position``
     - ``"border"``
     - ``"border"``, n+1 labels at swatch edges.
       ``"center"``, n labels centered inside each swatch.
   * - ``label_format``
     - ``"value"``
     - With ``label_position="center"``: ``"value"`` (lower bound) or
       ``"range"`` (``[min, max]`` interval).
   * - ``label_anchor``
     - ``"middle"``
     - SVG text-anchor for rotated labels: ``"middle"`` or ``"end"``.
   * - ``label_margin``
     - 4
     - Gap between swatch bottom and label baseline (SVG px).
   * - ``nodata_label``
     - ``"N/A"``
     - Label for missing-value swatch.
   * - ``nodata_gap``
     - 10
     - Gap between last class swatch and N/A swatch (SVG px).
   * - ``nodata_position``
     - ``"right"``
     - Vertical legend: ``"right"`` puts the N/A swatch in its own column,
       ``"below"`` under the last class (narrow legends).
   * - ``nodata_label_gap``
     - 4
     - Gap between N/A swatch right edge and its label (SVG px).
   * - ``vertical_swatch_width``
     - 16
     - Swatch width in vertical mode (SVG px).
   * - ``vertical_swatch_height``
     - 12
     - Swatch height in vertical mode (SVG px).
   * - ``vertical_label_gap``
     - 6
     - Gap between swatch and label in vertical mode (SVG px).
   * - ``labels``
     - ``None``
     - Custom label list (length == num_classes) replacing auto-generated labels.

.. _legend-frame:

Legend frame fields (``frame`` dict)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Key
     - Default
     - Description
   * - ``fill``
     - ``"white"``
     - Frame background color.
   * - ``fill_opacity``
     - 0.9
     - Frame background opacity.
   * - ``stroke``
     - ``"#cccccc"``
     - Frame border color.
   * - ``stroke_width``
     - 0.5
     - Frame border width (SVG px).
   * - ``border_radius``
     - 4
     - Frame corner radius (SVG px).
   * - ``padding``
     - 8
     - Inner padding between content and frame edge (SVG px).
   * - ``shadow``
     - ``False``
     - Add drop shadow behind the frame.
   * - ``shadow_dx`` / ``shadow_dy``
     - 2 / 2
     - Shadow offset (SVG px).
   * - ``shadow_blur``
     - 4
     - Shadow blur radius (SVG px).
   * - ``shadow_opacity``
     - 0.3
     - Shadow opacity.
