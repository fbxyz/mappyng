Inspecting and reproducing a map
================================

Two tools make a map's decisions inspectable and its result reproducible.

Classification report
---------------------

mappyng sometimes adjusts what you asked for: ``StdMean`` snaps the class
count to 5 or 7, coinciding breaks merge classes, ``PrettyBreaks`` rounds its
bounds. Warnings tell you at the time; the report keeps the outcome.
After the map is built, a :class:`~mappyng.Choropleth` or
:class:`~mappyng.Category` layer holds a ``report``:

.. code-block:: python

   layer = mp.Choropleth(gdf, column="rate", method="StdMean",
                         num_classes=4, cmap="RdBu")
   m = mp.Map(gdf) + layer
   m.render("map.svg")

   print(layer.report)
   layer.report.to_dataframe()      # one row per class
   m.classification_reports         # every layer, keyed by layer id

For a choropleth (:class:`~mappyng.ClassificationReport`): the method really
applied, requested and applied class counts, the bounds, the palette requested and the colour really used for each class, the number of
features per class, the number of features classified and excluded (missing
value), and the list of automatic adjustments with their reason (class count snapped, classes merged, palette cut to fewer colours). For a category layer
(:class:`~mappyng.CategoryReport`): the features per category, the excluded
features and the values that fell back to ``default_fill``.

Recipe
------

``Map.recipe()`` returns, and optionally writes, what is needed to reproduce a
render:

.. code-block:: python

   m.render("map.svg")
   m.recipe("map.recipe.yaml")      # .yaml/.yml or JSON

It holds the mappyng, Python and library versions, the seed, the map document
(the same as ``to_yaml``), a fingerprint of the main geometry and of each
layer's data (rows, CRS, columns, SHA-256 of geometry and values) and, once
the map is built, the classification reports. Keep it next to the SVG: if a
render changes later, compare the two recipes to see whether the data, the
parameters or the library versions moved.

What the recipe promises
~~~~~~~~~~~~~~~~~~~~~~~~

The recipe is a **provenance record**, not a rebuild kit.

- *Fingerprints verify data, they do not recover it.* Equal hashes mean the
  data are the same; the recipe does not contain them. A faithful rebuild also
  needs the same data and compatible library versions.
- *Scope of the hash.* In row order: the CRS, every geometry at full
  precision, and every non-geometry column (name and values as text), not only
  the column being mapped. Index labels and column dtypes are not hashed, and
  reordering the rows changes the hash.
- *Timing.* Before the map is built, ``classification`` is empty. A built map
  is frozen; a map derived with ``m + item`` is a new map, and has no report
  until it is rendered in turn. The recipe always describes the map as it is
  now.
- To rebuild a map from a file, use ``to_yaml`` / ``from_yaml`` with a
  declared data source.
