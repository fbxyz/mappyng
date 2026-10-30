Layers
======

Every drawable is a :class:`~mappyng.layers.Layer` added to a map with
``+`` or :meth:`mappyng.Map.add`. Layers carry their data and parameters, validate
themselves, and render into the map when it is built.

Base classes
------------

.. autoclass:: mappyng.layers.Layer
   :members:
   :show-inheritance:

.. autoclass:: mappyng.layers.RenderContext
   :members:

.. autoexception:: mappyng.layers.LayerStateError

Thematic layers
---------------

.. autoclass:: mappyng.Choropleth
   :show-inheritance:

.. autoclass:: mappyng.Category
   :show-inheritance:

.. autoclass:: mappyng.Proportional
   :show-inheritance:

.. autoclass:: mappyng.Situation
   :show-inheritance:

.. autoclass:: mappyng.Label
   :show-inheritance:

.. autoclass:: mappyng.Vector
   :show-inheritance:

Reference layers
----------------

.. autoclass:: mappyng.Basemap
   :show-inheritance:

.. autoclass:: mappyng.Graticule
   :show-inheritance:

.. autoclass:: mappyng.Tile
   :show-inheritance:

.. autoclass:: mappyng.Raster
   :show-inheritance:

.. autoclass:: mappyng.DropShadow
   :show-inheritance:

.. autoclass:: mappyng.OceanGradient
   :show-inheritance:

Reports
-------

.. autoclass:: mappyng.ClassificationReport
   :members: to_dataframe, to_dict

.. autoclass:: mappyng.CategoryReport
   :members: to_dataframe, to_dict
