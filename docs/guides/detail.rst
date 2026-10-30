Finer geometry in zooms and cartouches
======================================

A map is often drawn from a **generalised** (simplified) layer: the file stays
light and the main map looks clean. Once a dense area is magnified in a
:class:`~mappyng.Zoom` window or an :class:`~mappyng.Inset`, the same outlines
look coarse. If you have the same areas at a finer level of generalisation, the
``detail`` option draws the zoom and the cartouches from it, **without losing the
layer's symbology**.

How it works
------------

#. The layer is classified, coloured and given its opacity from **its own data**,
   exactly as without ``detail``.
#. For a zoom or a cartouche, the finer geometries are joined to those results
   through a key (``detail_join``), so each finer outline takes the class, colour
   and values of its area.
#. The finer outlines are drawn instead of the generalised ones. The main map is
   not touched.

.. code-block:: python

   m = (
       mp.Map(gdf_generalised, bbox=bbox)
       + mp.Basemap(detail=gdf_fine)
       + mp.Choropleth(
           gdf_generalised, column="rate",
           detail=gdf_fine,          # finer outlines for the zoom and the insets
           detail_join="COD_GEO",    # column present in both frames
       )
       + mp.Zoom(paris_bbox, x=520, y=90, width=250, height=250)
   )

The gallery shows the result side by side, with and without ``detail``:
:doc:`../gallery/plot_17_detail`.

The two options
---------------

``detail``
   The finer geometry, as a GeoDataFrame, which is used on the zoom **and** on
   every cartouche. A dict chooses the targets:

   .. code-block:: python

      detail={"zoom": gdf_a, "cartouches": gdf_b, 0: gdf_c}

   ``"zoom"`` is the zoom window, ``"cartouches"`` every cartouche, and an
   integer one cartouche by its index (``0`` is the first). A cartouche index
   wins over ``"cartouches"``. A target with no entry keeps the layer's own
   geometry. The finer frame can be in any CRS: it is reprojected to the layer's.

``detail_join``
   The key shared by the layer's data and the finer geometries.

   .. list-table::
      :header-rows: 1
      :widths: 35 65

      * - Value
        - Join
      * - ``"COD_GEO"``
        - A column with this name, present in **both** frames.
      * - ``("code", "COD_GEO")``
        - ``code`` in the layer's frame, ``COD_GEO`` in the finer one.
      * - ``None`` (default)
        - The index of both frames.

Layers that accept it
---------------------

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Layer
     - What ``detail`` changes
   * - :class:`~mappyng.Choropleth`, :class:`~mappyng.Category`
     - The polygons drawn in the zoom and the cartouches. Classes, colours,
       opacity, ``dissolve`` and the hatching of areas without data follow.
   * - :class:`~mappyng.Proportional`
     - The centres of the circles. Values, radii and colours stay those of the
       layer.
   * - :class:`~mappyng.Situation`
     - The positions of the markers, taken from the centroid of the finer
       outline.
   * - :class:`~mappyng.Label`
     - The positions of the labels of a ``zoom`` or ``cartouche:<i>`` target.
       The text and the priority stay those of the layer; an area made of
       several parts is labelled once. Labels on the main map are unchanged.
   * - :class:`~mappyng.Basemap`, :class:`~mappyng.Vector`
     - The polygons or lines drawn in the zoom and the cartouches. No join is
       needed: the finer geometries replace the layer's, so they have no
       ``detail_join``.

Good to know
------------

**One finer geometry per key, or several.** Several finer rows may share a key
(an area split into islands): each part takes the area's colour. Labels collapse
the parts into one.

**Unique keys on the layer side.** The layer's key must be unique, otherwise its
symbology cannot be matched to the finer geometries unambiguously, and a
``ValueError`` explains it. Rows of the finer frame with no match are ignored.

**Same type of key on both sides.** A key that is text in one frame and numeric
in the other (``"01"`` and ``1``) cannot match, and raises a ``ValueError`` saying
so. Convert one of them first, for example
``gdf["COD_GEO"] = gdf["COD_GEO"].astype(str)``. Text that looks alike but
differs, such as ``"1"`` and ``"01"``, is not detected: it shows as missing
finer geometries (see below).

**Areas without a finer geometry are not drawn** in the zoom and the cartouches,
and a ``UserWarning`` lists the first of them. It usually means that the key
does not match: check ``detail_join``.

**Identifiers stay those of the main map**, so hover tooltips of an interactive
export still work in the zoom.

**Proportional circles and labels at the edge.** A finer outline can move a
centroid into or out of a zoom window, so a symbol close to the edge may appear
or disappear compared with the generalised layer.

**No YAML export.** A GeoDataFrame is not a plain value, so ``to_yaml`` of a map
that uses ``detail`` raises a ``TypeError`` that says so, rather than dropping
the option silently.

Errors you may meet
-------------------

.. list-table::
   :header-rows: 1
   :widths: 50 50

   * - Message
     - Cause
   * - ``detail join: column 'x' is not in the choropleth data``
     - ``detail_join`` names a column missing from the layer's frame (the message
       lists the columns that exist, and names the layer: choropleth, category,
       proportional, situation or label); the same message with ``detail`` for
       the finer frame.
   * - ``detail join: the key of the choropleth data has duplicates``
     - Several rows of the layer share a key.
   * - ``detail join: the key is int64 in the choropleth data but object ...``
     - One frame has text keys and the other numeric keys: convert one side.
   * - ``detail: unknown target 'main'``
     - A dict key other than ``"zoom"``, ``"cartouches"`` or an integer. The
       main map has no ``detail``: it is drawn from the layer itself.
   * - ``detail[...] must be a GeoDataFrame``
     - A dict value is not a GeoDataFrame.
