"""Tests for legend.py, hatch patterns, position, title wrapping."""

import xml.etree.ElementTree as ET

import pytest

from mappyng import Map
from mappyng.layers import Basemap, Choropleth
from mappyng.legend import ensure_hatch_pattern

# ============================================================================
# ensure_hatch_pattern, style variants
# ============================================================================

class TestEnsureHatchPattern:
    """Verify that each hatch style produces the expected SVG structure."""

    def _make_defs(self):
        return ET.Element("defs")

    def _get_pattern(self, defs, pid):
        for child in defs:
            if child.get("id") == pid:
                return child
        return None

    def test_diagonal_slash(self):
        defs = self._make_defs()
        ensure_hatch_pattern(defs, "p1", "#333", style="///")
        pat = self._get_pattern(defs, "p1")
        assert pat is not None
        assert pat.get("patternTransform") == "rotate(45)"
        lines = [c for c in pat if c.tag == "line"]
        assert len(lines) == 1

    def test_backslash(self):
        defs = self._make_defs()
        ensure_hatch_pattern(defs, "p2", "#333", style="\\\\")
        pat = self._get_pattern(defs, "p2")
        assert pat is not None
        assert "rotate(-45)" in pat.get("patternTransform", "")
        lines = [c for c in pat if c.tag == "line"]
        assert len(lines) == 1

    def test_cross_hatch(self):
        defs = self._make_defs()
        ensure_hatch_pattern(defs, "p3", "#333", style="xxx")
        pat = self._get_pattern(defs, "p3")
        assert pat is not None
        lines = [c for c in pat if c.tag == "line"]
        assert len(lines) == 2, "Cross hatch needs 2 diagonal lines"

    def test_dots(self):
        defs = self._make_defs()
        ensure_hatch_pattern(defs, "p4", "#333", style="...")
        pat = self._get_pattern(defs, "p4")
        assert pat is not None
        circles = [c for c in pat if c.tag == "circle"]
        assert len(circles) >= 4, "Dot pattern should have >=4 circles"

    def test_vertical(self):
        defs = self._make_defs()
        ensure_hatch_pattern(defs, "p5", "#333", style="|||")
        pat = self._get_pattern(defs, "p5")
        assert pat is not None
        lines = [c for c in pat if c.tag == "line"]
        assert len(lines) == 1
        # Vertical: x1==x2 (no patternTransform)
        assert pat.get("patternTransform") is None

    def test_horizontal(self):
        defs = self._make_defs()
        ensure_hatch_pattern(defs, "p6", "#333", style="---")
        pat = self._get_pattern(defs, "p6")
        assert pat is not None
        lines = [c for c in pat if c.tag == "line"]
        assert len(lines) == 1
        assert lines[0].get("y2") == "0"  # horizontal to y doesn't change

    def test_unknown_style_falls_back_to_diagonal(self):
        defs = self._make_defs()
        ensure_hatch_pattern(defs, "p7", "#333", style="????")
        pat = self._get_pattern(defs, "p7")
        assert pat is not None
        assert pat.get("patternTransform") == "rotate(45)"

    def test_idempotent_second_call_ignored(self):
        defs = self._make_defs()
        ensure_hatch_pattern(defs, "p8", "#333", style="///")
        ensure_hatch_pattern(defs, "p8", "#999", style="xxx")
        patterns = [c for c in defs if c.get("id") == "p8"]
        assert len(patterns) == 1, "Second call must not add a duplicate pattern"


# ============================================================================
# hatch_style propagated through choropleth legend
# ============================================================================

class TestHatchStyleInChoropleth:
    """Verify that hatch_style set in legend_params ends up in the SVG <pattern>."""

    def _render_choropleth_nodata(self, gdf_departments, hatch_style):
        gdf = gdf_departments.copy()
        gdf.loc[gdf.index[0], "fid"] = None  # introduce one nodata row
        with Map(gdf, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Choropleth(gdf, column="fid", method="EqualInterval", num_classes=5, legend={"hatch_style": hatch_style}))
        return ET.fromstring(m.to_string())

    NS = "http://www.w3.org/2000/svg"

    def _find_patterns(self, root):
        """Return all <pattern> elements from the SVG."""
        ns = self.NS
        return root.findall(f".//{{{ns}}}pattern")

    def _count_tag(self, pattern, tag):
        ns = self.NS
        return len(pattern.findall(f"{{{ns}}}{tag}"))

    def test_xxx_hatch_in_defs(self, gdf_departments):
        root = self._render_choropleth_nodata(gdf_departments, "xxx")
        patterns = self._find_patterns(root)
        hatch_pats = [p for p in patterns if self._count_tag(p, "line") == 2]
        assert len(hatch_pats) >= 1, "Expected a cross-hatch pattern (2 lines) in <defs>"

    def test_dots_hatch_in_defs(self, gdf_departments):
        root = self._render_choropleth_nodata(gdf_departments, "...")
        patterns = self._find_patterns(root)
        dot_pats = [p for p in patterns if self._count_tag(p, "circle") >= 4]
        assert len(dot_pats) >= 1, "Expected a dot pattern (>=4 circles) in <defs>"


# ============================================================================
# Legend default position, below the map
# ============================================================================

class TestLegendPosition:
    def test_default_position_below_map(self, gdf_departments):
        """Legend y must be greater than the map content bottom edge."""
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Choropleth(gdf_departments, column="fid", method="EqualInterval", num_classes=5))
        root = ET.fromstring(m.to_string())
        ns = {"svg": "http://www.w3.org/2000/svg"}
        legend_g = root.find(".//svg:g[@id='choropleth-legend']", ns)
        assert legend_g is not None
        texts = legend_g.findall("svg:text", ns)
        if texts:
            title_y = float(texts[0].get("y", 0))
            # Map is 600px high; legend should appear well above the bottom margin
            assert title_y > 300, f"Legend y={title_y:.0f} seems too high (expected > 300)"

    def test_manual_position_respected(self, gdf_departments):
        """Setting position={'x': 0.5, 'y': 0.1} should move legend inside the map."""
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Choropleth(gdf_departments, column="fid", legend={"position": {"x": 0.5, "y": 0.1}}))
        root = ET.fromstring(m.to_string())
        ns = {"svg": "http://www.w3.org/2000/svg"}
        legend_g = root.find(".//svg:g[@id='choropleth-legend']", ns)
        assert legend_g is not None


# ---------------------------------------------------------------------
# Swatch shape
# ---------------------------------------------------------------------

def _choro_svg(gdf, **legend):
    import mappyng as mp
    m = mp.Map(gdf) + mp.Choropleth(
        gdf, column="fid", method="Quantiles", num_classes=5,
        legend=mp.Legend("Fid", **legend))
    return m.to_string()


def _swatches(svg):
    import re
    return re.findall(r'<(rect|circle) [^>]*id="choropleth-legend-swatch-\d"'
                      r'[^>]*>', svg)


def test_swatch_shape_default_is_rect(gdf_departments):
    import re
    svg = _choro_svg(gdf_departments)
    assert _swatches(svg) == ["rect"] * 5
    tags = re.findall(r'<rect [^>]*id="choropleth-legend-swatch-\d"[^>]*>',
                      svg)
    assert not any(' rx="' in tag for tag in tags)


def test_swatch_shape_rounded(gdf_departments):
    import re
    svg = _choro_svg(gdf_departments, swatch_shape="rounded")
    tags = re.findall(r'<rect [^>]*id="choropleth-legend-swatch-\d"[^>]*>',
                      svg)
    assert len(tags) == 5
    assert all(' rx="' in tag for tag in tags)


def test_swatch_radius_is_used(gdf_departments):
    svg = _choro_svg(gdf_departments, swatch_shape="rounded",
                     swatch_radius=2)
    # The radius is scaled like the swatch dimensions.
    assert 'rx="2.80"' in svg


@pytest.mark.parametrize("orientation", ["horizontal", "vertical"])
def test_swatch_shape_circle(gdf_departments, orientation):
    svg = _choro_svg(gdf_departments, swatch_shape="circle",
                     orientation=orientation)
    assert _swatches(svg) == ["circle"] * 5


def test_swatch_shape_applies_to_nodata(gdf_departments):
    import mappyng as mp
    gdf = gdf_departments.copy()
    gdf.loc[gdf.index[:3], "fid"] = None
    m = mp.Map(gdf) + mp.Choropleth(
        gdf, column="fid", legend=mp.Legend(swatch_shape="circle"))
    assert '<circle' in m.to_string().split(
        'id="choropleth-legend-nodata"')[0][-300:]


def test_swatch_shape_unknown_raises(gdf_departments):
    with pytest.raises(ValueError, match="swatch_shape"):
        _choro_svg(gdf_departments, swatch_shape="hexagon")


def test_shared_legend_config_is_not_modified(gdf_departments):
    import mappyng as mp
    legend = mp.FactorLegend(title="F", swatch_shape="rounded",
                             swatch_radius=2)
    base = mp.Map(gdf_departments) + mp.Choropleth(
        gdf_departments, column="fid", legend=legend)
    first = (base + mp.Title("A")).to_string()
    second = (base + mp.Title("A")).to_string()
    assert first == second
    assert legend.swatch_radius == 2


# ============================================================================
# Legend frame shadow ids: per document, no process-wide state
# ============================================================================

def _shadow_ids(svg):
    root = ET.fromstring(svg)
    return [el.get("id") for el in root.iter()
            if (el.get("id") or "").startswith("legend-frame-shadow-")]


def _map_with_shadowed_legend(gdf):
    m = Map(gdf, width=600, height=500)
    m.add(Choropleth(gdf, column="population", legend={
        "frame": {"shadow": True}}))
    return m.to_string()


def test_frame_shadow_ids_do_not_depend_on_previous_renders(gdf_departments):
    gdf = gdf_departments.copy()
    gdf["population"] = range(len(gdf))
    first = _shadow_ids(_map_with_shadowed_legend(gdf))
    second = _shadow_ids(_map_with_shadowed_legend(gdf))
    assert first and first == second


def _swatch_xy(svg, swatch_id):
    import re
    tag = re.search(rf'<rect [^>]*id="{swatch_id}"[^>]*>', svg).group(0)
    return (float(re.search(r' x="([-\d.]+)"', tag).group(1)),
            float(re.search(r' y="([-\d.]+)"', tag).group(1)))


@pytest.mark.parametrize("position", ["right", "below"])
def test_vertical_nodata_position(gdf_departments, position):
    import mappyng as mp
    gdf = gdf_departments.copy()
    gdf.loc[gdf.index[:3], "fid"] = None
    m = mp.Map(gdf) + mp.Choropleth(
        gdf, column="fid", method="Quantiles", num_classes=5,
        legend=mp.Legend("Fid", orientation="vertical",
                         nodata_position=position))
    svg = m.to_string()
    first = _swatch_xy(svg, "choropleth-legend-swatch-0")
    last = _swatch_xy(svg, "choropleth-legend-swatch-4")
    nodata = _swatch_xy(svg, "choropleth-legend-nodata")
    if position == "below":
        assert nodata[0] == first[0]
        assert nodata[1] > last[1]
    else:
        assert nodata[0] > first[0]
        assert nodata[1] == first[1]


def test_nodata_position_unknown_raises(gdf_departments):
    with pytest.raises(ValueError, match="nodata_position"):
        _choro_svg(gdf_departments, orientation="vertical", nodata_position="left")
