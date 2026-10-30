"""Tests for interactive.py, tooltips, Tooltip hover_opacity, data-tooltip encoding."""

import pytest

from mappyng import Map, Tooltip
from mappyng.interactive import (
    HoverEffect,
    TooltipStyle,
    _ensure_tooltip_style,
    _format_value,
)
from mappyng.layers import Basemap, Choropleth

# ============================================================================
# _format_value
# ============================================================================

class TestFormatValue:
    def test_integer(self):
        assert _format_value(42) == "42"

    def test_float_whole(self):
        assert _format_value(1000.0) == "1 000"

    def test_nan(self):
        assert _format_value(float("nan")) == ""

    def test_none(self):
        assert _format_value(None) == ""

    def test_string(self):
        assert _format_value("Paris") == "Paris"


# ============================================================================
# HoverEffect / TooltipStyle
# ============================================================================

class TestHoverEffect:
    def test_disabled_has_no_css(self):
        from mappyng.interactive import _build_hover_css
        css = _build_hover_css(HoverEffect(enabled=False))
        assert css == ""

    def test_opacity_below_one_produces_css(self):
        from mappyng.interactive import _build_hover_css
        css = _build_hover_css(HoverEffect(enabled=True, opacity=0.5))
        assert "opacity" in css
        assert "0.5" in css

    def test_ensure_hover_false(self):
        from mappyng.interactive import _ensure_hover_effect
        h = _ensure_hover_effect(False)
        assert h.enabled is False

    def test_ensure_hover_dict(self):
        from mappyng.interactive import _ensure_hover_effect
        h = _ensure_hover_effect({"opacity": 0.3, "scale": 1.2})
        assert h.opacity == 0.3
        assert h.scale == 1.2


class TestTooltipStyle:
    def test_ensure_tooltip_style_none(self):
        style = _ensure_tooltip_style(None)
        assert isinstance(style, TooltipStyle)
        assert isinstance(style.hover, HoverEffect)

    def test_ensure_tooltip_style_dict(self):
        style = _ensure_tooltip_style({"font_size": 14, "hover": {"opacity": 0.4}})
        assert style.font_size == 14
        assert style.hover.opacity == 0.4


# ============================================================================
# Tooltip(hover_opacity=...) in Map.to_interactive
# ============================================================================

class TestHoverOpacity:
    def _make_map(self, gdf_departments):
        pts = gdf_departments.copy()
        pts["geometry"] = pts.geometry.centroid
        return pts

    def test_hover_opacity_sets_style(self, gdf_departments):
        """hover_opacity=0.3 should produce opacity CSS rule."""
        pts = self._make_map(gdf_departments)
        with Map(pts, width=600, height=400) as m:
            m.add(Basemap())
            m.add(Choropleth(pts, column="fid", method="EqualInterval"))
        m.add(Tooltip(["fid"], hover_opacity=0.3))
        result = m.to_interactive()
        assert "opacity: 0.3" in result.svg

    def test_hover_opacity_does_not_override_existing_hover(self, gdf_departments):
        """hover_opacity merges with existing tooltip["hover"] dict."""
        pts = self._make_map(gdf_departments)
        with Map(pts, width=600, height=400) as m:
            m.add(Basemap())
            m.add(Choropleth(pts, column="fid", method="EqualInterval"))
        m.add(Tooltip(["fid"], style={"hover": {"scale": 1.1}},
                      hover_opacity=0.5))
        result = m.to_interactive()
        assert "opacity: 0.5" in result.svg

    def test_no_hover_opacity_no_opacity_rule(self, gdf_departments):
        """Without hover_opacity, no explicit opacity CSS rule (default is 1.0)."""
        pts = self._make_map(gdf_departments)
        with Map(pts, width=600, height=400) as m:
            m.add(Basemap())
            m.add(Choropleth(pts, column="fid", method="EqualInterval"))
        result = m.to_interactive(columns=["fid"])
        # Default opacity is 1.0, no opacity rule emitted
        assert "opacity: 1.0" not in result.svg


# ============================================================================
# data-tooltip injection
# ============================================================================

class TestDataTooltipInjection:
    def _render_interactive(self, gdf_departments, columns=None, aliases=None):
        with Map(gdf_departments, width=600, height=400) as m:
            m.add(Basemap())
            m.add(Choropleth(gdf_departments, column="fid", method="EqualInterval", num_classes=5))
        return m.to_interactive(columns=columns, aliases=aliases)

    def test_data_tooltip_attribute_present(self, gdf_departments):
        result = self._render_interactive(gdf_departments, columns=["fid"])
        assert 'data-tooltip=' in result.svg

    def test_column_value_in_tooltip(self, gdf_departments):
        result = self._render_interactive(gdf_departments, columns=["fid"])
        # JSON keys are XML-escaped in SVG attributes: " to &quot;
        # Check for either encoding
        svg = result.svg
        assert ("&quot;fid&quot;" in svg or '"fid"' in svg), \
            "Column key 'fid' not found in tooltip data"

    def test_alias_used_as_label(self, gdf_departments):
        result = self._render_interactive(
            gdf_departments,
            columns=["fid"],
            aliases={"fid": "Identifiant"},
        )
        svg = result.svg
        assert ("Identifiant" in svg), "Alias 'Identifiant' not found in tooltip data"
        # Original column name should not be a key (may appear in other contexts)
        import html

        # The key should be Identifiant, not fid, check in decoded form
        import re
        tooltip_vals = re.findall(r'data-tooltip=["\']([^"\']+)["\']', svg)
        if not tooltip_vals:
            # Attribute delimited by ", extract &quot; sequences
            tooltip_vals = re.findall(r'data-tooltip="([^"]+)"', svg)
        assert any("Identifiant" in html.unescape(v) for v in tooltip_vals)

    def test_script_injected(self, gdf_departments):
        result = self._render_interactive(gdf_departments)
        assert "<script" in result.svg


# ============================================================================
# HoverEffect(enabled=False), no CSS, tooltip still works
# ============================================================================

class TestHoverDisabled:
    def test_no_hover_css_when_disabled(self, gdf_departments):
        with Map(gdf_departments, width=600, height=400) as m:
            m.add(Basemap())
            m.add(Choropleth(gdf_departments, column="fid"))
        result = m.to_interactive(
            columns=["fid"],
            tooltip={"hover": False},
        )
        assert "[data-tooltip]:hover" not in result.svg

    def test_data_tooltip_still_present_when_hover_disabled(self, gdf_departments):
        with Map(gdf_departments, width=600, height=400) as m:
            m.add(Basemap())
            m.add(Choropleth(gdf_departments, column="fid"))
        result = m.to_interactive(
            columns=["fid"],
            tooltip={"hover": False},
        )
        assert 'data-tooltip=' in result.svg


class TestHoverOpacityParameterRemoved:
    """to_interactive/save_interactive lost their hover_opacity shortcut in 2.0."""

    def test_to_interactive_rejects_it(self, gdf_departments):
        m = Map(gdf_departments, width=600, height=400)
        with pytest.raises(TypeError):
            m.to_interactive(hover_opacity=0.3)

    def test_save_interactive_rejects_it(self, gdf_departments, tmp_path):
        m = Map(gdf_departments, width=600, height=400)
        with pytest.raises(TypeError):
            m.save_interactive(str(tmp_path / "x.html"), hover_opacity=0.3)
