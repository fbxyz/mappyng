"""
Factor maps of a principal component analysis
=============================================

A choropleth of the first factor of a principal component analysis on 42
African countries (demographic, social and economic indicators). The axis
is diverging and centred on zero. :class:`~mappyng.FactorLegend` adds what
such a map needs: the factor and its share of variance, an interpretation
text at each pole, a no-data entry and a methodology note.

By default the legend sits below the map. The same map is shown twice: a
vertical legend, then a horizontal one. The legend reads high to low: the
positive pole (mostly agricultural, young, high fertility) and the
negative pole (high GNP and GDP), each marked by an arrow.
"""

from pathlib import Path

import geopandas as gpd

import mappyng as mp

countries = gpd.read_file(Path("data") / "afrique_acp_cp1.geojson")

POLES = dict(
    title="Coordinates on the first factor",
    variance=0.588,
    pole_high="Mostly agricultural, under 15, high fertility",
    pole_low="High GNP and GDP",
    note="Standardised PCA on 42 African countries, late 20th century.",
    nodata_label="No data",
    decimals=2,
)


def _factor_map(orientation):
    return (
        mp.Map(countries, width=720, height="auto", facecolor="#ffffff")
        + mp.Choropleth(
            countries, column="cp1", cmap="RdYlGn", method="Quantiles",
            num_classes=5, stroke_width=0.2,
            legend=mp.FactorLegend(orientation=orientation, **POLES))
        + mp.Title("African development",
                   subtitle="First factor of a standardised PCA")
        + mp.Source("Source: ENSG L1 cartostat, TD3 (African country "
                    "indicators)")
        + mp.Tooltip(["nom", "cp1"],
                     aliases={"nom": "Country", "cp1": "Factor 1"})
    )


# Vertical legend, then horizontal: both render on this page.
vertical = _factor_map("vertical")
horizontal = _factor_map("horizontal")
