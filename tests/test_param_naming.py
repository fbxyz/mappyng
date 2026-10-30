"""Lock the harmonized public parameter vocabulary.

The visual concepts share one name across the whole API:

- outline color -> ``stroke``
- outline width -> ``stroke_width``
- fill color    -> ``fill``
- opacity       -> ``opacity``

These tests render with the canonical names and check that the matching
SVG attribute appears, and that the former synonyms are gone.
"""

import pytest

from mappyng import (
    Basemap,
    Choropleth,
    FontConfig,
    Graticule,
    Map,
    ProportionalLegendConfig,
    Situation,
    TileConfig,
)
from mappyng.situation import MarkerConfig


def _svg(m):
    m._build()
    return m.to_string()


# ---------------------------------------------------------------------
# stroke / stroke_width / fill on the layer API
# ---------------------------------------------------------------------

def test_choropleth_uses_stroke(gdf_departments):
    with Map(gdf_departments, width=400, height=300) as m:
        m.add(Choropleth(gdf_departments, column="fid",
                              method="Quantiles", num_classes=5,
                              stroke="#123456", stroke_width=0.7))
        svg = _svg(m)
    assert 'stroke="#123456"' in svg
    assert 'stroke-width="0.7"' in svg


def test_old_contour_name_is_rejected(gdf_departments):
    # The former synonym is no longer a parameter of the layer. Passing
    # it is an error, not a silent no-op, so typos surface at once.
    with pytest.raises(TypeError):
        Choropleth(gdf_departments, column="fid",
                        method="Quantiles", num_classes=5,
                        contour_color="#abcdef")


def test_basemap_uses_fill_and_stroke(gdf_departments):
    with Map(gdf_departments, width=400, height=300) as m:
        m.add(Basemap(fill="#abcdef", stroke="#654321",
                           stroke_width=0.9))
        svg = _svg(m)
    assert 'fill="#abcdef"' in svg
    assert 'stroke="#654321"' in svg
    assert 'stroke-width="0.9"' in svg


def test_situation_uses_fill(gdf_departments):
    pts = gdf_departments.copy()
    pts["geometry"] = pts.geometry.centroid
    with Map(gdf_departments, width=400, height=300) as m:
        m.add(Situation(pts, marker="circle", fill="#0a0b0c", size=6))
        svg = _svg(m)
    assert 'fill="#0a0b0c"' in svg


def test_situation_marker_config_field_is_fill():
    cfg = MarkerConfig(shapes=["circle"], fill="#abcabc")
    assert cfg.fill == "#abcabc"
    assert not hasattr(cfg, "color")


def test_graticule_uses_stroke(gdf_europe):
    with Map(gdf_europe, width=400, height=300) as m:
        m.add(Graticule(step=10.0, stroke="#abcabc"))
        svg = _svg(m)
    assert 'stroke="#abcabc"' in svg


# ---------------------------------------------------------------------
# opacity replaces alpha
# ---------------------------------------------------------------------

def test_tileconfig_uses_opacity():
    cfg = TileConfig(opacity=0.4)
    assert cfg.opacity == 0.4
    assert not hasattr(cfg, "alpha")


def test_fontconfig_uses_opacity():
    cfg = FontConfig(opacity=0.5)
    assert cfg.opacity == 0.5
    assert not hasattr(cfg, "alpha")


def test_scale_bar_opacity(gdf_departments):
    with Map(gdf_departments, width=400, height=300) as m:
        m.add(Basemap())
        m.scale_bar(opacity=0.5)
        svg = _svg(m)
    assert 'opacity="0.5"' in svg


# ---------------------------------------------------------------------
# legend circle stroke vocabulary
# ---------------------------------------------------------------------

def test_proportional_legend_circle_stroke_fields():
    cfg = ProportionalLegendConfig(circle_stroke="#222222",
                                   circle_stroke_width=1.5)
    assert cfg.circle_stroke == "#222222"
    assert cfg.circle_stroke_width == 1.5
    assert not hasattr(cfg, "circle_edgecolor")
    assert not hasattr(cfg, "circle_linewidth")
