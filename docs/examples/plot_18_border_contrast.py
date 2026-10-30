"""
Borders between similar colours
===============================

In a choropleth, two neighbours of similar colour (both pale, or both dark)
merge into one patch when the outline is close to them in tone: the border
between them disappears. ``border_contrast`` finds those shared borders and
redraws **only them**, in a colour that stands out; the polygons keep their own
outline.

The same map is drawn three times with a pale outline (``stroke="#eeeeee"``)
on a blue palette:

* without the option, where the pale departments run together;
* with ``border_contrast="check"``, which reveals the weak borders in magenta
  (and warns with their number);
* with ``border_contrast=True``, which redraws them dark.

Data: mortality from heart failure, rate per 100,000 inhabitants
(Sante publique France, ODISSE).
"""

import warnings
from pathlib import Path

import pandas as pd

import mappyng as mp
from mappyng.data import load_france_departments

deps = load_france_departments().to_crs(2154)
deps = deps[deps["COD_GEO"].str.len() == 2]    # metropolitan France
df = pd.read_csv(Path("data") / "cardio_mortalite_dep.csv", dtype={"code_dep": str})
deps = deps.merge(df, left_on="COD_GEO", right_on="code_dep", how="left")


def build(title, **options):
    return (
        mp.Map(deps, width=620, height="auto", border_radius=0)
        + mp.Choropleth(
            deps, column="taux_mortalite", cmap="Blues", method="Quantiles",
            num_classes=5, stroke="#eeeeee", stroke_width=0.6,
            legend=mp.Legend("Deaths / 100,000", orientation="horizontal",
                             decimals=0, swatch_width=18, fontsize=7,
                             label_rotation=0, nodata_label="No data"),
            **options,
        )
        + mp.Title(title)
    )


# Without the option: pale neighbours run together.
m_off = build("Without border_contrast")

# Check: the weak borders in magenta. The warning that counts them is silenced
# here only to keep the example output short.
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    m_check = build("border_contrast='check'", border_contrast="check")

# Fix: only those shared borders are redrawn, dark on pale areas.
m_fix = build("border_contrast=True", border_contrast=True)
