Layout Elements
===============

Title, scale bar, source attribution and north arrow are **chrome**
elements: :class:`~mappyng.Title`, :class:`~mappyng.ScaleBar`,
:class:`~mappyng.Source` and :class:`~mappyng.NorthArrow`. Cartouches
(:class:`~mappyng.Insets`) and the zoom window (:class:`~mappyng.Zoom`)
are elements too. All are added like layers, with ``+`` or
:meth:`~mappyng.Map.add`. Chrome is drawn when the map is rendered;
adding a second title replaces the first.

The methods ``m.title(...)``, ``m.scale_bar(...)``, ``m.source(...)``,
``m.north_arrow(...)``, ``m.add_zoom({...})`` and ``m.add_shadow(...)``
remain as shortcuts for the matching element.

Title
-----

The first argument is the title text; the rest are keyword options.

.. code-block:: python

   m = m + mp.Title(
       "Population par département",
       subtitle="Source : INSEE, 2024",
       loc="left",
       font_size=14,
       font_weight="bold",
       top_gap=10,
       offset_x=0,
       offset_y=0,
   )

.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Key
     - Default
     - Description
   * - ``text``
     - required
     - Title text.  Wrapped automatically at ``max_chars``.
   * - ``subtitle``
     - ``None``
     - Subtitle rendered below the title.
   * - ``loc``
     - ``"left"``
     - Horizontal alignment: ``"left"``, ``"center"``, or ``"right"``.
   * - ``max_chars``
     - 60
     - Maximum characters per line before wrapping.
   * - ``font_size``
     - from style
     - Title font size (scaled by ``font_scale``).
   * - ``fill``
     - from style
     - Title color.
   * - ``font_weight``
     - from style
     - Font weight (e.g. ``"bold"``).
   * - ``font_family``
     - from style
     - Font family.
   * - ``subtitle_font_size``
     - auto
     - Subtitle font size (defaults to ``font_size × 0.75``).
   * - ``subtitle_color``
     - from style
     - Subtitle color.
   * - ``subtitle_font_weight``
     - ``"normal"``
     - Subtitle font weight.
   * - ``top_gap``
     - 8
     - Gap between title baseline and map top edge (SVG px).
       Positive = title moves up.
   * - ``position``
     - ``None``
     - Place the title anywhere instead of above the map (anchor: baseline
       of the last line, aligned by ``loc``). See :ref:`placing-elements`.
   * - ``offset_x``
     - 0.0
     - Additional horizontal shift (SVG px).
   * - ``offset_y``
     - 0.0
     - Additional vertical shift (SVG px).

Scale bar
---------

.. code-block:: python

   mp.ScaleBar()                                 # fully automatic
   mp.ScaleBar(length=200_000, label="200 km")
   mp.ScaleBar(location="lower left", color="#444444",
               bar_height=4, opacity=0.8)
   mp.ScaleBar(position=(0.46, 0.9))             # fractions of the content

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Key
     - Default
     - Description
   * - ``length``
     - auto
     - Bar length in map CRS units.  Auto: ~20 % of map width.
   * - ``label``
     - auto
     - Label text.  Auto-generated from ``length / unit_factor``.
       Pass ``""`` to suppress.
   * - ``unit``
     - ``"km"``
     - Unit string appended to auto-label.
   * - ``unit_factor``
     - 1000
     - Divisor for CRS-units to display-units (default: metres to km).
   * - ``location``
     - ``"lower right"``
     - Preset position: ``"lower right"``, ``"lower left"``,
       ``"upper right"``, ``"upper left"``.
   * - ``position``
     - ``None``
     - Manual position of the left end of the bar (overrides
       ``location``). See :ref:`placing-elements`.
   * - ``color``
     - from style
     - Unified color for bar, ticks, and label.
   * - ``bar_color``
     - from ``color``
     - Bar line color override.
   * - ``tick_color``
     - from ``color``
     - Tick color override.
   * - ``label_color``
     - from ``color``
     - Label color override.
   * - ``font_size``
     - 8
     - Label font size.
   * - ``font_weight``
     - ``"normal"``
     - Label font weight.
   * - ``font_family``
     - from style
     - Label font family.
   * - ``bar_height``
     - 3
     - Bar line thickness (SVG px).
   * - ``tick_height``
     - ``bar_height + 3``
     - Tick mark height (SVG px).
   * - ``tick_width``
     - 1
     - Tick stroke width (SVG px).
   * - ``margin``
     - 15
     - Distance from the content edge to the bar (SVG px).
   * - ``opacity``
     - 1.0
     - Overall opacity 0-1.

Source attribution
------------------

.. code-block:: python

   mp.Source("Source : INSEE")
   mp.Source("Source : INSEE\\nTraitement : auteur", layout="horizontal")
   mp.Source("Source : IGN, GéoFLA", position=(0.5, 1.05))

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Key
     - Default
     - Description
   * - ``text``
     - required
     - Attribution text.  Use ``"\\n"`` for line breaks in horizontal mode.
   * - ``layout``
     - ``"vertical"``
     - ``"vertical"``, rotated 90° at the right edge, reading bottom-to-top.
       ``"horizontal"``, normal text at the bottom-right.
   * - ``position``
     - ``None``
     - Manual position of the start of the text (overrides ``layout``).
       See :ref:`placing-elements`.
   * - ``rotation``
     - 90 / 0
     - Explicit rotation in degrees (default depends on layout).
   * - ``font_size``
     - from style
     - Font size.
   * - ``color``
     - from style
     - Text color.
   * - ``opacity``
     - from style
     - Text opacity.
   * - ``font_style``
     - ``"italic"``
     - CSS font-style.
   * - ``font_weight``
     - ``"normal"``
     - CSS font-weight.
   * - ``font_family``
     - from style
     - Font family.
   * - ``text_anchor``
     - auto
     - SVG text-anchor: ``"start"``, ``"middle"``, or ``"end"``.

Placing elements and finer zoom geometry
----------------------------------------

Every element with a ``position`` accepts fractions, percentages, pixels and
geographic coordinates: see :ref:`placing-elements`. The zoom window and the
cartouches can draw a finer geometry than the main map while keeping the
layer's symbology: see :doc:`detail`.

Cartouches (:class:`~mappyng.Insets`)
--------------------------------------

Cartouches show areas away from the main frame (overseas territories,
Alaska...), each in its own CRS, stacked on the left of the map. An
:class:`~mappyng.Insets` groups them; options passed to ``Insets`` apply
to every :class:`~mappyng.Inset` that does not set them.

.. code-block:: python

   insets = mp.Insets(
       [
           mp.Inset("Guadeloupe", bbox=[-6890454, 1780151, -6799589, 1874186],
                    crs=3857),
           mp.Inset("Martinique", bbox=[-6826862, 1609607, -6759494, 1685367],
                    crs=3857),
       ],
       spacing=15, title_size=7, border_radius=6, box_shadow=True,
   )
   m = m + insets

Layers are drawn in the cartouches by default. Pass
``on_cartouches=False`` to keep a layer on the main map only.

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Option
     - Default
     - Description
   * - ``title``
     - ``None``
     - Title above the cartouche (first argument of ``Inset``).
   * - ``bbox`` / ``crs``
     - required
     - Area shown and its CRS.
   * - ``title_size``
     - 8
     - Title font size.
   * - ``size``
     - 1.0
     - Scale factor of the cartouche.
   * - ``spacing``
     - auto
     - Space above the cartouche (SVG px). On ``Insets``: spacing
       between all cartouches.
   * - ``border_color`` / ``border_width`` / ``border_radius``
     - from style
     - Frame of the cartouche.
   * - ``box_shadow`` / ``glow``
     - ``None``
     - Effects, same format as on the main map.

Zoom window (:class:`~mappyng.Zoom`)
-------------------------------------

.. code-block:: python

   m = m + mp.Zoom([586377, 6780533, 739396, 6904563],
                   border_radius=8, box_shadow=True)

Thematic layers are redrawn in the zoom window by default
(``on_zoom=True``); vector layers and drop shadows are not.

In a YAML document, the zoom window is a top-level ``zoom`` block with
the same keys:

.. code-block:: yaml

   zoom:
     bbox: [586377, 6780533, 739396, 6904563]
     border_radius: 8
     box_shadow: true

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Key
     - Default
     - Description
   * - ``bbox``
     - required
     - Geographic bounding box ``[minx, miny, maxx, maxy]``.
   * - ``x`` / ``y``
     - auto
     - SVG pixel position of the zoom window top-left corner.
   * - ``width`` / ``height``
     - auto
     - Zoom window size in SVG px.
   * - ``border_color``
     - from style
     - Border stroke color.
   * - ``border_width``
     - 1
     - Border stroke width (SVG px).
   * - ``border_radius``
     - 4
     - Corner radius (SVG px, 0 = sharp).
   * - ``box_shadow``
     - ``None``
     - Drop shadow: ``True`` (defaults), ``False``, or dict
       (keys: ``dx``, ``dy``, ``blur``, ``color``, ``opacity``).
   * - ``glow``
     - ``None``
     - Outer glow: same format as ``box_shadow``.

Ocean gradient (:class:`~mappyng.OceanGradient`)
------------------------------------------------

An optional gradient on the ocean, fading out from the coastline of a
layer. With the default white colour it lightens the water along the
coast; a dark colour gives the opposite effect.

.. code-block:: python

   m = (
       mp.Map(europe, bbox=bbox_metro, facecolor="#B9D9EB")
       + mp.OceanGradient(europe)
       + mp.Basemap()
   )

It is drawn above the ``facecolor`` and below every other layer,
whatever the order in which it is added. The gradient is made of nested
buffers of the dissolved geometries rather than an SVG filter, so PNG and
PDF exports match the SVG.

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Key
     - Default
     - Description
   * - ``query``
     - ``None``
     - pandas query selecting the rows the gradient starts from.
   * - ``width``
     - 24
     - Distance in pixels over which the gradient fades out.
   * - ``color``
     - ``"#ffffff"``
     - Gradient colour along the coast.
   * - ``opacity``
     - 0.45
     - Opacity along the coast; it decreases to 0 at ``width``.
   * - ``steps``
     - 8
     - Number of bands. More bands give a smoother gradient and a larger
       file.
   * - ``on_cartouches`` / ``on_zoom``
     - ``True``
     - Draw in the cartouches and in the zoom window.

Graticule (:class:`~mappyng.Graticule`)
---------------------------------------

.. code-block:: python

   m = m + mp.Graticule(step=5.0, stroke="#888888", opacity=0.4,
                        stroke_width=0.5, dash="4 2")

.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Key
     - Default
     - Description
   * - ``step``
     - 10.0
     - Graticule spacing in degrees.
   * - ``color``
     - ``"#aaaaaa"``
     - Line color.
   * - ``opacity``
     - 0.5
     - Line opacity.
   * - ``stroke_width``
     - 0.5
     - Line width (SVG px).
   * - ``dash``
     - ``"4 2"``
     - SVG ``stroke-dasharray``.
