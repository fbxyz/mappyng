Glossary and conventions
========================

The API is in English, and the documentation is written in English and French
(guides and examples that discuss French geography use French place names).
Terms that exist in both languages:

.. list-table::
   :header-rows: 1

   * - French
     - mappyng term
     - Meaning
   * - cartouche
     - ``Inset``, ``Insets``, ``cartouche_params``
     - A small framed map of a territory placed on the main map (overseas
       departments, Alaska...). Both words mean the same thing here; ``inset``
       is the class name, ``cartouche`` appears in parameter and option names
       (``on_cartouches``, ``cartouche_spacing``).
   * - aplat
     - ``Choropleth``
     - Areas filled with a colour that encodes a class.
   * - symboles proportionnels
     - ``Proportional``
     - Circles whose area encodes a quantity.
   * - habillage
     - elements
     - Title, source, scale bar, north arrow, legends.
   * - fond de carte
     - ``Basemap``, ``Tile``
     - Base geometry or raster background.
   * - toponymes
     - ``Label``
     - Placed place names.
   * - classes, bornes
     - classes, bins/breaks
     - Intervals of a classification and their bounds.
   * - surcouche
     - overlay (``Vector``)
     - A layer drawn above the data layers (positive ``z_index``).

Conventions: class and parameter names are English; French only where the
term is the cartographic standard (``cartouche``). A page mixing both
languages should keep one language per paragraph.
