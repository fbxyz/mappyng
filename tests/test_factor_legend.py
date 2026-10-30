"""Tests for FactorLegend, the principal-component (factor) map legend."""

import numpy as np
import pytest

from mappyng import Choropleth, FactorLegend, Map


@pytest.fixture
def factor_gdf(gdf_departments):
    """A choropleth-ready frame with a signed factor-like column."""
    g = gdf_departments.copy()
    n = len(g)
    # A diverging score centred near zero.
    g["cp1"] = np.linspace(-3.0, 3.0, n)
    return g


def _factor_svg(gdf, **legend_kwargs):
    m = Map(gdf, width=600, height=600)
    m.add(Choropleth(gdf, column="cp1", cmap="RdYlGn",
                          method="Quantiles", num_classes=5,
                          legend=FactorLegend(**legend_kwargs)))
    return m.to_string()


def test_factor_legend_is_choropleth_legend_subclass():
    """FactorLegend reuses the choropleth legend machinery."""
    from mappyng.choropleth import ChoroplethLegendConfig
    assert issubclass(FactorLegend, ChoroplethLegendConfig)


def test_title_with_variance_appends_percentage():
    leg = FactorLegend(title="First factor", variance=0.588)
    assert leg.title_with_variance() == "First factor (58.8% of total variance)"


def test_title_with_variance_none_keeps_title():
    leg = FactorLegend(title="First factor")
    assert leg.title_with_variance() == "First factor"


def test_vertical_renders_all_elements(factor_gdf):
    svg = _factor_svg(
        factor_gdf, title="First factor", variance=0.588,
        pole_high="Young and agricultural", pole_low="Rich economies",
        note="Standardised PCA.", nodata_label="No data",
        orientation="vertical")
    assert "factor-legend" in svg
    assert "58.8%" in svg
    assert "Young and agricultural" in svg
    assert "Rich economies" in svg
    assert "Standardised PCA." in svg


def test_horizontal_renders_all_elements(factor_gdf):
    svg = _factor_svg(
        factor_gdf, title="First factor", variance=0.42,
        pole_high="Young and agricultural", pole_low="Rich economies",
        note="Standardised PCA.", orientation="horizontal")
    assert "factor-legend" in svg
    assert "42.0%" in svg
    # Horizontal poles carry the sign markers.
    assert "- Rich economies" in svg
    assert "Young and agricultural +" in svg


def test_missing_optional_fields_are_omitted(factor_gdf):
    """A legend with no poles or note still renders without error."""
    svg = _factor_svg(factor_gdf, title="First factor", orientation="vertical")
    assert "factor-legend" in svg


def test_nodata_entry_present_when_data_missing(factor_gdf):
    factor_gdf.loc[factor_gdf.index[:3], "cp1"] = np.nan
    svg = _factor_svg(factor_gdf, title="F1", nodata_label="No data",
                      orientation="vertical")
    assert "factor-legend-nodata" in svg
    assert "No data" in svg
