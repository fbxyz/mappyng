Installation
============

Install the latest version directly from the GitHub repository:

.. code-block:: bash

   pip install git+https://github.com/fbxyz/mappyng.git

Optional extras
---------------

.. code-block:: bash

   # XYZ/raster basemap tiles (mercantile, Pillow)
   pip install "mappyng[tile] @ git+https://github.com/fbxyz/mappyng.git"

   # GeoTIFF raster backgrounds (rasterio)
   pip install "mappyng[raster] @ git+https://github.com/fbxyz/mappyng.git"

   # PNG/PDF export (cairosvg)
   pip install "mappyng[export] @ git+https://github.com/fbxyz/mappyng.git"

A PyPI release (``pip install mappyng``) is planned.
