Installation
============

Install from PyPI:

.. code-block:: bash

   pip install mappyng-svg

The package is imported as ``mappyng`` (``import mappyng as mp``).

Optional extras
---------------

.. code-block:: bash

   # XYZ/raster basemap tiles (mercantile, Pillow)
   pip install "mappyng-svg[tile]"

   # GeoTIFF raster backgrounds (rasterio)
   pip install "mappyng-svg[raster]"

   # PNG/PDF export (cairosvg)
   pip install "mappyng-svg[export]"

Development version
-------------------

.. code-block:: bash

   pip install git+https://github.com/fbxyz/mappyng.git
