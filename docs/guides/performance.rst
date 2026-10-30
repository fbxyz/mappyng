Performance
===========

Render time and SVG weight on representative workloads, measured with
``benchmarks/bench.py`` (``python benchmarks/bench.py --md`` reproduces the
table on your machine). Figures are medians of three renders, 900 px wide, on
one x86-64 machine with Python 3.12 and mappyng 1.0.0. Timings fluctuate by
about ±30 % between runs, so read them as orders of magnitude.

.. list-table::
   :header-rows: 1

   * - Case
     - Features
     - Vertices
     - Render (s)
     - SVG (KiB)
   * - Basemap, départements
     - 96
     - 2 404
     - 0.03
     - 43
   * - Choropleth, départements
     - 96
     - 2 404
     - 0.13
     - 93
   * - Choropleth, Europe
     - 94
     - 6 764
     - 0.12
     - 227
   * - Choropleth, 36 000 synthetic communes
     - 36 100
     - 180 500
     - 18.3
     - 12 874
   * - Choropleth, 3 600 polygons × 100 vertices
     - 3 600
     - 363 600
     - 3.3
     - 11 374
   * - Same communes, ``simplify="auto"``
     - 36 100
     - 180 500
     - 13.9
     - 12 870
   * - 96 labels on départements
     - 96
     - 2 404
     - 3.3
     - 85

The "communes" are a synthetic grid of jittered polygons (no external data)
sized like metropolitan France's communes. A real commune layer has more
irregular boundaries.

What the figures say
--------------------

- Bundled-size layers (départements, régions, countries) render in well under
  a second.
- Cost grows with the **number of features** first (about 0.5 ms per polygon
  here) and with vertices second.
- An SVG of tens of thousands of polygons weighs about 12 MiB. That is fine for
  a file, heavy for a web page: prefer a coarser geometry for the web.
- Label placement is the slowest step on small maps: a few seconds for 96
  labels, because placement is an optimisation (simulated annealing).
- ``simplify="auto"`` only helps when boundaries have more detail than the
  render resolution. On already coarse polygons the gain is small.

Limits of this benchmark: one machine, synthetic communes, no tiles or
rasters, no PNG/PDF export.
