"""
The same choropleth, from YAML
==============================

This is the :doc:`Choropleth <plot_02_choropleth>` example rebuilt from a
single YAML document instead of Python. Every parameter -- the framing
``bbox``, the overseas ``cartouche_params``, the drop shadow lifting
France, the layers, the legend and the chrome -- lives in the document.
The data is fetched declaratively too: each ``data:`` block names a
built-in ``dataset`` (reprojected with ``crs``) and the choropleth layer
``join``\\s its values from a CSV. No glue code runs.

:meth:`mappyng.Map.from_yaml` resolves the sources and returns a ready
:class:`~mappyng.Map`; from a shell the same file renders with::

    python -m mappyng choropleth.yaml -o choropleth.svg     # or .png/.pdf/.html

Hover a department to read its value.
"""

from mappyng import Map

# A complete map: configuration, layers (each with its own data source,
# the drop shadow included), chrome and tooltips. Compare it line for line with the
# Python of the Choropleth example -- it is the same map, declared.
YAML = """
mappyng: 1
map:
  width: 900
  height: 1000
  padding: 25
  facecolor: "#B9D9EB"
  border_radius: 10
  box_shadow: {dx: 3, dy: 3, blur: 6, opacity: 0.2}
  bbox: [90000, 6040000, 1280000, 7150000]   # Lambert-93 mainland frame
  cartouche_spacing: 15
  data: {dataset: europe, crs: 2154}          # base geometry (background)
  cartouche_params:
    0: {bbox: [-6890454, 1780151, -6799589, 1874186], crs: 3857,
        cartouche_title: Guadeloupe, cartouche_title_size: 7,
        border_radius: 6, box_shadow: true}
    1: {bbox: [-6826862, 1609607, -6759494, 1685367], crs: 3857,
        cartouche_title: Martinique, cartouche_title_size: 7,
        border_radius: 6, box_shadow: true}
    2: {bbox: [-6136680, 235261, -5707791, 671780], crs: 3857,
        cartouche_title: French Guiana, cartouche_title_size: 7,
        border_radius: 6, box_shadow: true}
    3: {bbox: [6136383, -2448160, 6226316, -2366992], crs: 3857,
        cartouche_title: Reunion, cartouche_title_size: 7,
        border_radius: 6, box_shadow: true}
    4: {bbox: [5006226, -1459183, 5050208, -1416184], crs: 3857,
        cartouche_title: Mayotte, cartouche_title_size: 7,
        border_radius: 6, box_shadow: true}
layers:
- type: OceanGradient
  data: {dataset: europe, crs: 2154}
  params: {}
- type: Basemap
  data: {in_memory: false}
  params: {}
- type: Vector
  data: {dataset: france_regions, crs: 2154}
  params: {stroke: "#4d4d4d", stroke_width: 0.1}
- type: DropShadow
  data: {dataset: europe, crs: 2154}
  params: {query: "code_pays_iso3 == 'FRA'"}
- type: Choropleth
  data:
    dataset: france_departments
    crs: 2154
    join:
      path: data/cardio_mortalite_dep.csv
      left_on: COD_GEO
      right_on: code_dep
      dtype: {code_dep: str}
  params:
    column: taux_mortalite
    cmap: Reds
    method: Quantiles
    num_classes: 5
    stroke_width: 0.15
    legend:
      title: "Deaths / 100,000 inhabitants"
      orientation: horizontal
      decimals: 0
      nodata_label: "No data"
      swatch_shape: rounded
- type: Vector
  data: {dataset: france_regions, crs: 2154}
  params: {stroke: "#333333", stroke_width: 0.4, position: top}
chrome:
  title:
    text: Mortality from heart failure
    subtitle: Standardised rate, 2020-2022 average
  scale_bar:
    length: 100000
    label: 100 km
    position: {x: 0.55, y: 0.855}   # Gulf of Lion
    opacity: 0.8
  source: {text: "Source: Sante publique France (ODISSE)"}
interactive:
  columns: [LIB_GEO, taux_mortalite]
  aliases: {LIB_GEO: Department, taux_mortalite: Rate}
"""

# Relative paths (the join CSV) resolve against base_dir. The
# ``interactive`` block sets the tooltips of the HTML export.
m = Map.from_yaml(YAML, base_dir=".")
