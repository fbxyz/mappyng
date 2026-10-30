Tile Providers
==============

.. autodata:: mappyng.tile.TILE_PROVIDERS
   :annotation: = dict, alias to XYZ URL template

Built-in aliases:

- **OpenStreetMap**: ``"openstreetmap"`` / ``"osm"``
- **CartoDB**: ``"cartodb_positron"`` / ``"positron"``, ``"cartodb_darkmatter"`` / ``"darkmatter"``, ``"cartodb_voyager"`` / ``"voyager"``
- **Stadia / Stamen**: ``"terrain"``, ``"toner"``, ``"watercolor"``
- **ESRI**: ``"satellite"`` / ``"esri_worldimagery"``, ``"esri_worldstreet"``, ``"esri_natgeo"``, ``"esri_ocean"``
- **OpenTopoMap**: ``"opentopomap"`` / ``"topo"``

.. autoclass:: mappyng.tile.TileConfig
   :members:
