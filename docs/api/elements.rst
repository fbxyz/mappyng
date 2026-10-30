Elements
========

Map elements other than layers: chrome, cartouches, zoom window,
tooltips and gradients. They are added to a map with ``+`` or
:meth:`mappyng.Map.add`, like layers.

Chrome
------

.. autoclass:: mappyng.Title

.. autoclass:: mappyng.Source

.. autoclass:: mappyng.ScaleBar

.. autoclass:: mappyng.NorthArrow

Legend
------

.. autoclass:: mappyng.Legend
   :members: to_dict

Cartouches and zoom
-------------------

.. autoclass:: mappyng.Insets

.. autoclass:: mappyng.Inset

.. autoclass:: mappyng.Zoom

Interactive export
------------------

.. autoclass:: mappyng.Tooltip

Gradients
---------

.. autoclass:: mappyng.RadialGradient
   :members: url
