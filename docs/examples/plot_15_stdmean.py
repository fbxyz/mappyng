"""
Standard-deviation choropleth (double gamme)
============================================

The *StdMean* method places its class breaks at standard-deviation steps
either side of the mean, with a central class straddling it. It is a
*diverging* classification, so it pairs with a *double gamme* (diverging)
palette: one colour ramp below the mean and one above, meeting at a
neutral centre. Only odd class counts make that symmetry work, so StdMean
accepts **5 or 7** classes; any other count snaps to the nearest valid one
with a warning.

``reverse=True`` flips the double ramp (*gamme inversee*) without moving
the neutral centre: handy when high values should read "cool" rather than
"warm".

Hover a department to read its value.
"""

from pathlib import Path

import pandas as pd

import mappyng as mp
from mappyng.data import load_france_departments

# Metropolitan France only (two-character department codes).
deps = load_france_departments().to_crs(2154)
deps = deps[deps["COD_GEO"].str.len() == 2]
df = pd.read_csv(Path("data") / "cardio_mortalite_dep.csv", dtype={"code_dep": str})
deps = deps.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")

# StdMean with 7 classes and a diverging "double gamme" (RdBu). Use
# reverse=True to invert it: departments above the mean read blue, below
# the mean read red, with the neutral class kept in the centre.
m = (
    mp.Map(deps, width=820, height="auto", border_radius=0)
    + mp.Choropleth(
        deps,
        column="taux_mortalite",
        cmap="RdBu",
        method="StdMean",
        num_classes=7,
        reverse=True,
        stroke_width=0.2,
        legend=mp.Legend("Deaths / 100,000 inhab. (std-dev classes)",
                         orientation="horizontal", decimals=0,
                         nodata_label="No data"),
    )
    + mp.Title("Mortality from heart failure",
               subtitle="Standard-deviation classes around the mean")
    + mp.Source("Source: Sante publique France (ODISSE)")
    + mp.Tooltip(["LIB_GEO", "taux_mortalite"],
                 aliases={"LIB_GEO": "Department", "taux_mortalite": "Rate"})
)
