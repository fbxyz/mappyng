Quickstart
==========

``mappyng`` produces self-contained SVG maps from GeoDataFrame objects.
No display server or GUI is required, output is a plain ``.svg`` file or
a standalone HTML file.

A map is composed by adding objects to a :class:`~mappyng.Map`: layers
(:class:`~mappyng.Basemap`, :class:`~mappyng.Choropleth`...) and elements
(:class:`~mappyng.Title`, :class:`~mappyng.ScaleBar`,
:class:`~mappyng.Source`...):

.. code-block:: python

   import mappyng as mp
   from mappyng.data import load_france_departments

   gdf = load_france_departments()

   m = (
       mp.Map(gdf, width=800, height="auto", facecolor="#B9D9EB")
       + mp.Basemap()
       + mp.Title("Départements français")
       + mp.ScaleBar()
       + mp.Source("Source : IGN, GéoFLA")
   )
   m.render("france.svg")

The map is drawn when it is rendered, so the order in which elements are
added does not matter (layers are drawn in the order they were added,
unless ``z_index`` says otherwise).

``+`` or ``add``
----------------

``m + item`` returns a **new** map and leaves ``m`` unchanged.
``m.add(item, ...)`` adds to ``m`` in place and returns it, so calls can
be chained. Both accept one item, several items (``add``) or a list.

.. code-block:: python

   # Chained add
   m = (
       mp.Map(gdf, width=800, height="auto")
       .add(mp.Basemap())
       .add(mp.Title("Départements français"))
   )

   # Step by step
   m = mp.Map(gdf, width=800, height="auto")
   m.add(mp.Basemap())
   m.add(mp.Title("Départements français"), mp.Source("Source : IGN, GéoFLA"))

Since ``+`` does not modify its left operand, a shared base can be
derived into several maps:

.. code-block:: python

   base = (
       mp.Map(gdf, width=800, height="auto")
       + mp.Basemap()
       + mp.Source("Source : INSEE")
   )
   rate = base + mp.Choropleth(gdf, column="rate") + mp.Title("Rate")
   pop = base + mp.Proportional(pts, column="pop") + mp.Title("Population")

Layers are copied by ``+`` (their GeoDataFrame is shared).
:meth:`~mappyng.Map.copy` returns an unbuilt copy of a map.

Map elements
------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Element
     - Purpose
   * - :class:`~mappyng.Title`
     - Title and subtitle above the map.
   * - :class:`~mappyng.Source`
     - Source or credit line.
   * - :class:`~mappyng.ScaleBar`
     - Scale bar.
   * - :class:`~mappyng.NorthArrow`
     - North arrow.
   * - :class:`~mappyng.Insets` / :class:`~mappyng.Inset`
     - Cartouches (see :doc:`layout`).
   * - :class:`~mappyng.Zoom`
     - Zoom window.
   * - :class:`~mappyng.Tooltip`
     - Hover tooltips of the interactive export.
   * - :class:`~mappyng.RadialGradient`
     - Gradient usable as a ``fill`` through its ``url``.

A layer's legend is set with :class:`~mappyng.Legend`:

.. code-block:: python

   mp.Choropleth(gdf, column="rate",
                 legend=mp.Legend("Rate", orientation="horizontal"))

A plain dict (``legend={"title": "Rate"}``) is also accepted.

The methods ``m.title(...)``, ``m.source(...)``, ``m.scale_bar(...)`` and
``m.north_arrow(...)`` are shortcuts for adding the matching element.

``width="auto"`` / ``height="auto"`` size the canvas to the data aspect
ratio so the map is not letterboxed; :meth:`~mappyng.Map.autosize`
recomputes it on demand.

``Map`` constructor parameters
-------------------------------

.. list-table::
   :header-rows: 1
   :widths: 22 15 63

   * - Parameter
     - Default
     - Description
   * - ``gdf``
     - required
     - Base GeoDataFrame, defines extent and basemap geometry.
   * - ``bbox``
     - ``None``
     - ``[minx, miny, maxx, maxy]``.  Computed from ``gdf`` if omitted.
   * - ``width``
     - 800
     - SVG document width in pixels, or ``"auto"`` to derive it from the
       data aspect ratio.
   * - ``height``
     - 600
     - SVG document height in pixels, or ``"auto"`` (recommended) to
       derive it from the data so the map is not letterboxed.
   * - ``padding``
     - 10
     - Document-level padding in pixels.
   * - ``style``
     - ``"classic"``
     - Preset name (``"classic"``, ``"modern"``) or override dict
       (``{"base": "classic", "title_color": "#333"}``).
   * - ``facecolor``
     - ``None``
     - Ocean / background color drawn inside each viewport.
   * - ``background``
     - ``None``
     - Document background color (default white).
   * - ``basemap_color``
     - ``None``
     - Override fill color for basemap polygons.
   * - ``border_radius``
     - 4
     - Corner radius of the main map viewport (SVG px, 0 = sharp).
   * - ``box_shadow``
     - ``None``
     - Drop shadow on the main map: ``True`` (defaults), ``False``, or
       dict (keys: ``dx``, ``dy``, ``blur``, ``color``, ``opacity``).
   * - ``glow``
     - ``None``
     - Outer glow on the main map: same format as ``box_shadow``.
   * - ``cartouche_params``
     - ``None``
     - Inset map definitions.  Dict keyed by integer index, each value
       a dict with required ``bbox`` and ``crs``, and optional
       ``cartouche_title``, ``size``, ``spacing``, ``border_radius``,
       ``box_shadow``, ``glow``. :class:`~mappyng.Insets` is the object
       form.
   * - ``cartouche_spacing``
     - ``None``
     - Global vertical spacing between cartouches (SVG px).
   * - ``font_scale``
     - ``"auto"``
     - Global font size multiplier.  ``"auto"`` (default) scales to the
       document area; pass a float to override.

Output methods
--------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Method
     - Description
   * - ``m.render("map.svg")``
     - Render to a file; format inferred from the extension (``.svg``
       and ``.html`` native, ``.png`` / ``.pdf`` via the ``export``
       extra). Returns ``self``.
   * - ``m.to_string()``
     - Return SVG markup as a string.
   * - ``m.to_interactive(...)``
     - Return :class:`~mappyng.interactive.InteractiveMap` with hover tooltips.
   * - ``m.save_interactive("map.html")``
     - Save as standalone HTML file.
   * - ``m.to_yaml("map.yaml")``
     - Serialise the map's intent (layers + chrome) to YAML.
   * - ``Map.from_yaml("map.yaml", gdf=gdf)``
     - Rebuild a map from YAML, reattaching the supplied geometry.
   * - ``Map.from_yaml("map.yaml")``
     - Build from a YAML that declares its own ``data:`` sources, no
       geometry argument needed.
   * - ``python -m mappyng map.yaml -o map.svg``
     - Render a source-bearing YAML to a file from the shell
       (``.svg`` / ``.png`` / ``.pdf`` / ``.html``).

``m.save(...)``, the former alias of ``m.render(...)``, was removed in 2.0.

Building a map from YAML
------------------------

A map serialises to a YAML document that captures the configuration, the
ordered layers with every parameter, and the chrome. An *exported* map
references its geometry (pass it back with ``gdf=``), but a hand-written
document can declare where its data comes from and then build with no
Python:

.. code-block:: yaml

   mappyng: 1
   map: {width: 820, height: auto}
   layers:
   - type: Choropleth
     data:
       dataset: france_departments   # a built-in dataset (or path: file.geojson)
       crs: 2154                       # optional reprojection
       filter: COD_GEO.str.len() == 2  # optional pandas query
       join:                           # optional CSV attribute join
         path: deaths.csv
         left_on: COD_GEO
         right_on: code_dep
     params: {column: rate, cmap: RdBu, method: StdMean, num_classes: 7}
   chrome:
     title: {text: Mortality}

.. code-block:: bash

   python -m mappyng map.yaml -o map.svg      # also .png, .pdf, .html

.. warning::

   Loading a YAML executes its declared sources (file reads and the
   pandas ``filter`` expression), so only build documents you trust.

Style customization
-------------------

.. code-block:: python

   # Use a preset
   m = Map(gdf, style="modern")

   # Override specific values
   m = Map(gdf, style={"base": "classic", "title_color": "#1a1a2e",
                        "basemap_fill": "#f5f5f5"})

   # Register a custom style for reuse
   from mappyng.config import ConfigManager
   ConfigManager.add_style("my_style", {
       "base": "classic",
       "title_color": "#1a1a2e",
       "basemap_fill": "#e8e8e8",
       "basemap_edge_color": "#999999",
   })
   m = Map(gdf, style="my_style")
