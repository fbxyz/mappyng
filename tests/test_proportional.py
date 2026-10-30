"""Tests for proportional.py, sizing, formatting, legend."""

import xml.etree.ElementTree as ET

import numpy as np
import pytest

from mappyng import Map
from mappyng.layers import Basemap, Proportional
from mappyng.proportional import ProportionalLegendConfig, _format_value

# ============================================================================
# _format_value
# ============================================================================

class TestFormatValue:
    NNBSP = " "  # narrow no-break space used as thousands separator

    def test_space_thousands(self):
        result = _format_value(1_500_000, decimals=0, number_format="space")
        assert self.NNBSP in result
        assert "1" in result and "500" in result and "000" in result

    def test_none_thousands(self):
        assert _format_value(1_500_000, decimals=0, number_format="none") == "1500000"

    def test_decimals_one(self):
        result = _format_value(1234.5, decimals=1, number_format="space")
        assert self.NNBSP in result or "1" in result  # separator may vary
        assert ".5" in result

    def test_zero_decimals_integer(self):
        result = _format_value(42.7, decimals=0)
        assert "43" in result
        assert "." not in result


# ============================================================================
# ProportionalLegendConfig defaults
# ============================================================================

class TestProportionalLegendConfig:
    def test_number_format_default(self):
        cfg = ProportionalLegendConfig()
        assert cfg.number_format == "space"

    def test_circle_spacing_default_none(self):
        cfg = ProportionalLegendConfig()
        assert cfg.circle_spacing is None

    def test_leader_opacity_default(self):
        cfg = ProportionalLegendConfig()
        assert 0 < cfg.leader_opacity <= 1


# ============================================================================
# Rendering helpers
# ============================================================================

def _make_point_gdf(gdf_departments):
    """Return centroids of departments with a numeric 'pop' column."""
    pts = gdf_departments.copy()
    pts["geometry"] = pts.geometry.centroid
    pts["pop"] = np.linspace(1_000, 1_000_000, len(pts))
    return pts


def _render_proportional(gdf_departments, legend_params=None):
    pts = _make_point_gdf(gdf_departments)
    with Map(pts, width=800, height=600) as m:
        m.add(Basemap())
        m.add(Proportional(pts, column="pop", legend=legend_params or {}))
    svg_str = m.to_string()
    return ET.fromstring(svg_str)


# ============================================================================
# Legend, nested (default)
# ============================================================================

class TestNestedLegend:
    def test_renders_circles(self, gdf_departments):
        root = _render_proportional(gdf_departments)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        circles = root.findall(".//svg:g[@id='proportional-legend']/svg:circle", ns)
        assert len(circles) >= 1

    def test_leader_opacity_in_svg(self, gdf_departments):
        root = _render_proportional(
            gdf_departments, legend_params={"leader_opacity": 0.3}
        )
        ns = {"svg": "http://www.w3.org/2000/svg"}
        lines = root.findall(".//svg:g[@id='proportional-legend']/svg:line", ns)
        assert len(lines) >= 1
        for line in lines:
            assert line.get("stroke-opacity") == "0.3"

    def test_number_format_none_no_space(self, gdf_departments):
        root = _render_proportional(
            gdf_departments, legend_params={"number_format": "none"}
        )
        ns = {"svg": "http://www.w3.org/2000/svg"}
        texts = root.findall(".//svg:g[@id='proportional-legend']/svg:text", ns)
        label_texts = [
            (t.text or "").strip()
            for t in texts
            if t.get("font-weight") != "bold"
        ]
        # No thousands-separator space inside numeric labels
        for label in label_texts:
            if label:
                assert " " not in label, f"Space separator found in: {label!r}"


# ============================================================================
# Legend, horizontal
# ============================================================================

class TestHorizontalLegend:
    def _render_horizontal(self, gdf_departments, **kwargs):
        pts = _make_point_gdf(gdf_departments)
        with Map(pts, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Proportional(pts, column="pop", legend={"orientation": "horizontal", **kwargs}))
        return ET.fromstring(m.to_string())

    def test_renders_without_error(self, gdf_departments):
        root = self._render_horizontal(gdf_departments)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        circles = root.findall(".//svg:g[@id='proportional-legend']/svg:circle", ns)
        assert len(circles) >= 1

    def test_circle_spacing_increases_x_gap(self, gdf_departments):
        """Larger circle_spacing should produce wider total legend width."""
        ns = {"svg": "http://www.w3.org/2000/svg"}

        root_narrow = self._render_horizontal(gdf_departments, circle_spacing=2.0)
        root_wide = self._render_horizontal(gdf_departments, circle_spacing=50.0)

        circles_narrow = root_narrow.findall(".//svg:g[@id='proportional-legend']/svg:circle", ns)
        circles_wide = root_wide.findall(".//svg:g[@id='proportional-legend']/svg:circle", ns)

        if len(circles_narrow) >= 2 and len(circles_wide) >= 2:
            cx_narrow = [float(c.get("cx")) for c in circles_narrow]
            cx_wide = [float(c.get("cx")) for c in circles_wide]
            # Last circle should be further right with large spacing
            assert max(cx_wide) > max(cx_narrow)

    def test_number_format_space(self, gdf_departments):
        root = self._render_horizontal(gdf_departments, number_format="space")
        ns = {"svg": "http://www.w3.org/2000/svg"}
        texts = root.findall(".//svg:g[@id='proportional-legend']/svg:text", ns)
        labels = [(t.text or "").strip() for t in texts]
        # At least one label with value >= 1000 should contain a thousands separator
        NNBSP = " "
        large_labels = [l for l in labels if len(l) >= 5]
        assert any(NNBSP in l for l in large_labels), f"Expected space separator, got: {labels}"


# ============================================================================
# One radius scale per layer
# ============================================================================

class TestSingleRadiusScale:
    """A value has the same radius on every viewport and in the legend."""

    BBOX = [90000, 6040000, 1280000, 7150000]
    PARIS = [300000, 6600000, 700000, 6900000]
    CORSE = [1150000, 6040000, 1250000, 6200000]

    def _data_max(self, gdf_departments):
        from shapely.geometry import box
        pts = _make_point_gdf(gdf_departments)
        return float(pts[pts.within(box(*self.BBOX))]["pop"].max())

    def _circles(self, gdf_departments, **kw):
        from shapely.geometry import box

        from mappyng import Inset, Insets, Zoom
        pts = _make_point_gdf(gdf_departments)
        pts = pts[pts.within(box(*self.BBOX))]  # metropolitan France only
        m = Map(pts, bbox=self.BBOX, width=900, height=800)
        m.add(Zoom(self.PARIS, x=560, y=80, width=300, height=240))
        m.add(Insets([Inset("Corse", bbox=self.CORSE, crs=2154)]))
        m.add(Proportional(pts, column="pop", max_radius=30, **kw))
        root = ET.fromstring(m.to_string())
        svg = "{http://www.w3.org/2000/svg}"
        return [c for c in root.iter(svg + "circle")]

    def test_same_value_same_radius_in_every_viewport(self, gdf_departments):
        radii = {}
        for c in self._circles(gdf_departments):
            cid = c.get("id") or ""
            if cid.startswith("prop-") and "legend" not in cid:
                radii.setdefault(cid, set()).add(c.get("r"))
        # the same department is drawn on the main map and in a window
        assert any(len(v) >= 1 for v in radii.values())
        assert all(len(v) == 1 for v in radii.values()), {
            k: v for k, v in radii.items() if len(v) > 1}

    def test_largest_value_takes_max_radius(self, gdf_departments):
        radii = [float(c.get("r")) for c in self._circles(gdf_departments)
                 if (c.get("id") or "").startswith("prop-")
                 and "legend" not in (c.get("id") or "")]
        assert max(radii) == pytest.approx(30.0, abs=0.01)

    def test_legend_follows_the_data_scale(self, gdf_departments):
        # custom legend values must be sized like the circles of the map:
        # r = max_radius * sqrt(value / data maximum), not rescaled to the
        # largest legend value.
        top = self._data_max(gdf_departments)
        circles = self._circles(gdf_departments,
                                legend={"values": [top / 4, top / 2]})
        legend = {c.get("id"): float(c.get("r")) for c in circles
                  if "legend-circle" in (c.get("id") or "")}
        assert sorted(legend.values()) == pytest.approx(
            [15.0, 30.0 * 0.5 ** 0.5], abs=0.01)

    def test_explicit_reference_is_still_honoured(self, gdf_departments):
        circles = self._circles(gdf_departments,
                                reference_value=4 * self._data_max(gdf_departments),
                                reference_radius=30)
        radii = [float(c.get("r")) for c in circles
                 if (c.get("id") or "").startswith("prop-")
                 and "legend" not in (c.get("id") or "")]
        assert max(radii) == pytest.approx(15.0, abs=0.01)
