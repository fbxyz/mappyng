Tile Basemaps
=============

:class:`~mappyng.Tile` downloads XYZ raster tiles, warps them from
EPSG:3857 to the map CRS, and embeds them as base64 PNG ``<image>``
elements.

Requires: ``pip install mappyng[tile]``

.. code-block:: python

   from mappyng import Map, Tile

   m = Map(gdf, width=800, height="auto")
   m.add(Tile())
   m.add(Tile(source="satellite"))
   m.add(Tile(source="terrain", opacity=0.7, zoom_offset=-1))
   m.add(Tile(source="https://tile.openstreetmap.org/{z}/{x}/{y}.png"))

All parameters
--------------

These are passed as keyword arguments to ``Tile(...)``.

.. list-table::
   :header-rows: 1
   :widths: 22 18 60

   * - Key
     - Default
     - Description
   * - ``source``
     - ``"cartodb_positron"``
     - Provider alias or URL template with ``{x}``, ``{y}``, ``{z}``
       placeholders.
   * - ``zoom``
     - ``"auto"``
     - Zoom level (int) or ``"auto"`` (smallest zoom covering the viewport).
   * - ``zoom_offset``
     - 0
     - Integer added to the auto-calculated zoom
       (``-1`` = coarser / lighter, ``+1`` = more detail).
   * - ``alpha``
     - 1.0
     - Tile layer opacity 0-1.
   * - ``cache``
     - ``True``
     - Cache downloaded tiles on disk.
   * - ``cache_dir``
     - ``None``
     - Cache directory path.  Defaults to ``~/.cache/mappyng/tiles``.
   * - ``timeout``
     - 10.0
     - HTTP request timeout in seconds.
   * - ``on_cartouches``
     - ``True``
     - Render tiles on cartouche viewports.
   * - ``on_zoom``
     - ``True``
     - Render tiles on the zoom viewport.
   * - ``max_tiles``
     - 64
     - Maximum tiles downloaded per viewport (safety cap).
   * - ``warp_scale``
     - 1.5
     - Output image resolution relative to the SVG content area
       (1.0 = screen pixels, 1.5 = 50 % denser for crispness).
   * - ``extra_zoom_levels``
     - 0
     - Also fetch this many coarser zoom levels and composite them
       (coarse to fine, finer tiles overwrite coarser where available).
       Useful to fill gaps when fine tiles fail to download.

Built-in providers
------------------

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Alias
     - Provider
   * - ``"openstreetmap"`` / ``"osm"``
     - OpenStreetMap standard
   * - ``"osm_hot"``
     - OpenStreetMap Humanitarian
   * - ``"cartodb_positron"`` / ``"positron"``
     - CartoDB Positron (light, no labels)
   * - ``"cartodb_darkmatter"`` / ``"darkmatter"``
     - CartoDB DarkMatter (dark)
   * - ``"cartodb_voyager"`` / ``"voyager"``
     - CartoDB Voyager (color)
   * - ``"terrain"`` / ``"stadia_terrain"``
     - Stadia / Stamen Terrain
   * - ``"toner"`` / ``"stadia_toner"``
     - Stadia / Stamen Toner (black & white)
   * - ``"stadia_toner_lite"``
     - Stadia / Stamen Toner Lite
   * - ``"watercolor"`` / ``"stadia_watercolor"``
     - Stadia / Stamen Watercolor
   * - ``"satellite"`` / ``"esri_worldimagery"``
     - ESRI World Imagery (satellite)
   * - ``"esri_worldterrain"``
     - ESRI World Terrain Base
   * - ``"esri_worldstreet"``
     - ESRI World Street Map
   * - ``"esri_natgeo"``
     - ESRI National Geographic
   * - ``"esri_ocean"``
     - ESRI World Ocean Base
   * - ``"opentopomap"`` / ``"topo"``
     - OpenTopoMap (topographic)
