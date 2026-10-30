"""
Borderless choropleth
======================

Metropolitan France alone, with no chrome around the map: no ocean panel,
no frame and no drop shadow. Leaving ``facecolor`` unset and
``border_radius=0`` places the choropleth directly on the page background,
for a clean figure to drop into a document. The legend uses round
swatches (``swatch_shape="circle"``).

Hover a department to read its value.
"""

from pathlib import Path

import pandas as pd

import mappyng as mp
from mappyng.data import load_france_departments

deps = load_france_departments().to_crs(2154)
# Metropolitan France only: its department codes have two characters,
# while every overseas department or collectivity has three.
deps = deps[deps["COD_GEO"].str.len() == 2]
df = pd.read_csv(Path("data") / "cardio_mortalite_dep.csv", dtype={"code_dep": str})
deps = deps.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")

m = (
    mp.Map(deps, width=820, height="auto", border_radius=0)
    + mp.Choropleth(
        deps, column="taux_mortalite", cmap="Reds",
        method="Quantiles", num_classes=5, stroke_width=0.2,
        legend=mp.Legend("Deaths / 100,000 inhabitants",
                         orientation="horizontal", decimals=0,
                         nodata_label="No data", swatch_shape="circle"),
    )
    + mp.Title("Mortality from heart failure",
               subtitle="Metropolitan France, standardised rate")
    + mp.Source("Source: Sante publique France (ODISSE)")
    + mp.Tooltip(["LIB_GEO", "taux_mortalite"],
                 aliases={"LIB_GEO": "Department", "taux_mortalite": "Rate"})
)
