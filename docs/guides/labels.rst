Label Placement
===============

:class:`~mappyng.Label` places text labels using a
simulated-annealing algorithm with overlap avoidance via
``shapely.STRtree``.  The text column is passed as ``column``; the
remaining keyword arguments map directly to
:class:`~mappyng.toponyme.LabelConfig`.

.. code-block:: python

   from mappyng import Map, Basemap, Label

   m = Map(gdf, width=800, height="auto")
   m.add(Basemap())
   m.add(Label(
       gdf_villes,
       column="nom",
       priority_col="population",
       max_labels=25,
       font_size=9,
       font_weight="bold",
       halo_color="#ffffff",
       halo_width=2.0,
       leader_lines=True,
       avoid_overlap=True,
       n_sweeps=80,
       seed=42,
   ))

   # Numbered circles mode (for dense datasets)
   m.add(Label(
       gdf_villes,
       column="nom",
       numbered_above=15,
       numbered_legend_position={"x": 0.75, "y": 0.1},
       priority_col="population",
   ))

Appearance
----------

.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Parameter
     - Default
     - Description
   * - ``font_size``
     - 10.0
     - Label font size in SVG px.
   * - ``font_family``
     - ``"sans-serif"``
     - Label font family.
   * - ``font_weight``
     - ``"normal"``
     - Label font weight.
   * - ``color``
     - ``"#000000"``
     - Label text color.
   * - ``halo_color``
     - ``"#ffffff"``
     - Text halo color.  Set to ``None`` to disable the halo.
   * - ``halo_width``
     - 2.0
     - Halo stroke width in SVG px.

Filtering
---------

.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Parameter
     - Default
     - Description
   * - ``priority_col``
     - ``None``
     - Column used for rank ordering (higher value = placed first).
   * - ``min_priority``
     - ``None``
     - Rows below this value are skipped.
   * - ``max_labels``
     - ``None``
     - Hard cap on the number of labels placed.

Placement
---------

Labels avoid the point symbols of the map: situation markers and
proportional circles, in every viewport. A label placed on a feature that
carries a symbol keeps ``label_offset`` from the edge of the largest
symbol drawn at that point, not from its centre, so a marker drawn over a
larger circle is cleared too. With ``allow_hide``, a label that cannot be
placed without covering a symbol is hidden; ``allow_symbol_overlap=True``
keeps it instead. Labels are placed after every other layer, whatever the
order in which they are added.

.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Parameter
     - Default
     - Description
   * - ``initial_position``
     - ``"NE"``
     - Starting candidate direction.  One of ``"N"``, ``"NE"``, ``"E"``,
       ``"SE"``, ``"S"``, ``"SW"``, ``"W"``, ``"NW"``.
   * - ``candidate_positions``
     - all 8
     - List of candidate directions tried by the annealing.
   * - ``label_offset``
     - 4.0
     - Distance from anchor point to label edge (SVG px).
   * - ``max_displacement``
     - 40.0
     - Maximum total displacement before a label is hidden (SVG px).
   * - ``avoid_overlap``
     - ``True``
     - Enable label-label overlap energy.
   * - ``allow_hide``
     - ``True``
     - Allow labels to be hidden when placement fails, including labels
       that still cover a map symbol.
   * - ``allow_symbol_overlap``
     - ``False``
     - Keep labels that cover a map symbol instead of hiding them.
   * - ``wrap``
     - ``True``
     - Wrap long labels at dashes (French typographic convention).
   * - ``wrap_max_chars``
     - 12
     - Characters per line before wrapping.
   * - ``target``
     - ``"main"``
     - Viewport: ``"main"``, ``"zoom"``, or ``"cartouche:<index>"``.

Leader lines
------------

.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Parameter
     - Default
     - Description
   * - ``leader_lines``
     - ``True``
     - Draw leader lines when label is displaced.
   * - ``leader_threshold``
     - 1.5
     - Minimum displacement (× label height) that triggers a leader line.
   * - ``leader_color``
     - ``"#666666"``
     - Leader line color.
   * - ``leader_width``
     - 0.5
     - Leader line stroke width (SVG px).

Numbered-circles mode
---------------------

When the number of features exceeds ``numbered_above``, labels are replaced
by numbered circles on the map and a legend box listing the names.

.. list-table::
   :header-rows: 1
   :widths: 28 15 57

   * - Parameter
     - Default
     - Description
   * - ``numbered_above``
     - ``None``
     - Switch to numbered mode when label count exceeds this value.
   * - ``numbered_legend_position``
     - ``None``
     - Legend position ``{"x": frac, "y": frac}`` (figure fractions,
       (0,0) = bottom-left).  Auto-computed if None.
   * - ``numbered_circle_r``
     - 5.0
     - Circle radius in SVG px.
   * - ``numbered_circle_fill``
     - ``"#ffffff"``
     - Circle fill color.
   * - ``numbered_circle_stroke``
     - ``"#333333"``
     - Circle stroke color.
   * - ``numbered_legend_bg``
     - ``"white"``
     - Legend box background color.
   * - ``numbered_legend_bg_opacity``
     - 0.88
     - Legend box background opacity.
   * - ``numbered_legend_border``
     - ``"#cccccc"``
     - Legend box border color.
   * - ``numbered_legend_title``
     - ``None``
     - Legend box title text.

Simulated annealing
-------------------

.. list-table::
   :header-rows: 1
   :widths: 22 12 66

   * - Parameter
     - Default
     - Description
   * - ``n_sweeps``
     - 50
     - Number of annealing sweeps (more = better quality, slower).
   * - ``initial_temperature``
     - 1.0
     - Starting annealing temperature.
   * - ``final_temperature``
     - 0.01
     - Ending annealing temperature.
   * - ``seed``
     - 42
     - Random seed.  Set to ``None`` for non-reproducible placement.

Energy weights (advanced)
--------------------------

These control the relative importance of each penalty term.
Increase a weight to make the placer prioritize avoiding that conflict.

.. list-table::
   :header-rows: 1
   :widths: 10 8 82

   * - Parameter
     - Default
     - Description
   * - ``w_LL``
     - 30.0
     - Label-label overlap energy.
   * - ``w_LO``
     - 25.0
     - Label-obstacle overlap energy (proportional symbols, markers).
   * - ``w_LC``
     - 100.0
     - Label-chrome overlap energy (title, scale bar, source).
   * - ``w_LA``
     - 30.0
     - Label-anchor overlap energy.
   * - ``w_D``
     - 1.0
     - Distance from anchor penalty.
   * - ``w_OR``
     - 3.0
     - Orientation bias (prefer NE over other positions).
   * - ``w_OOB``
     - 1000.0
     - Out-of-bounds penalty.
