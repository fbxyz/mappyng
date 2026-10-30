"""Tests for situation.py, markers, legend, columns_n."""

import xml.etree.ElementTree as ET

import pytest

from mappyng import Map
from mappyng.layers import Basemap, Situation
from mappyng.situation import SituationLegendConfig

# ============================================================================
# SituationLegendConfig defaults
# ============================================================================

class TestSituationLegendConfig:
    def test_columns_n_default(self):
        cfg = SituationLegendConfig()
        assert cfg.columns_n == 1

    def test_col_gap_default(self):
        cfg = SituationLegendConfig()
        assert cfg.col_gap > 0

    def test_standard_font_fields_present(self):
        """BaseLegendConfig fields must be accessible (no ad-hoc key names)."""
        cfg = SituationLegendConfig(
            fontcolor="#333333",
            fontsize=10,
            title_fontcolor="#000000",
            title_fontsize=12,
        )
        assert cfg.fontcolor == "#333333"
        assert cfg.fontsize == 10
        assert cfg.title_fontcolor == "#000000"
        assert cfg.title_fontsize == 12


# ============================================================================
# Rendering helpers
# ============================================================================

def _make_categorical_gdf(gdf_departments):
    pts = gdf_departments.copy()
    pts["geometry"] = pts.geometry.centroid
    pts["type"] = (pts.index % 3).map({0: "A", 1: "B", 2: "C"})
    return pts


def _render_situation(gdf_departments, legend_params=None):
    pts = _make_categorical_gdf(gdf_departments)
    with Map(pts, width=800, height=600) as m:
        m.add(Basemap())
        m.add(Situation(pts, column="type", symbol={
                "A": {"marker": "circle", "fill": "#e63946", "size": 10},
                "B": {"marker": "square", "fill": "#457b9d", "size": 10},
                "C": {"marker": "star",   "fill": "#2a9d8f", "size": 10},
            }, legend=legend_params or {"title": "Type"}))
    return ET.fromstring(m.to_string())


# ============================================================================
# Rendering, basic
# ============================================================================

class TestSituationRendering:
    def test_renders_without_error(self, gdf_departments):
        root = _render_situation(gdf_departments)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        paths = root.findall(".//svg:path", ns)
        assert len(paths) > 0

    def test_uniform_mode(self, gdf_departments):
        pts = _make_categorical_gdf(gdf_departments)
        with Map(pts, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Situation(pts, marker="diamond", fill="#264653", size=8))
        svg = m.to_string()
        assert "<path" in svg


# ============================================================================
# Legend, single column
# ============================================================================

class TestSituationLegendSingleColumn:
    def test_legend_group_created(self, gdf_departments):
        root = _render_situation(gdf_departments)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        # Legend group has an id starting with legend_situation_
        groups = root.findall(".//svg:g", ns)
        ids = [g.get("id", "") for g in groups]
        assert any("legend_situation" in gid for gid in ids)

    def test_title_rendered(self, gdf_departments):
        root = _render_situation(gdf_departments, legend_params={"title": "Mon titre"})
        svg_str = ET.tostring(root, encoding="unicode")
        assert "Mon titre" in svg_str

    def test_three_labels_rendered(self, gdf_departments):
        root = _render_situation(gdf_departments, legend_params={"title": "Type"})
        ns = {"svg": "http://www.w3.org/2000/svg"}
        # Find legend group
        for g in root.findall(".//svg:g", ns):
            if "legend_situation" in g.get("id", ""):
                texts = g.findall(".//svg:text", ns)
                labels = [t.text for t in texts if t.text in ("A", "B", "C")]
                assert len(labels) == 3
                return
        pytest.fail("Legend group not found")

    def test_fontcolor_applied(self, gdf_departments):
        root = _render_situation(
            gdf_departments,
            legend_params={"title": "Type", "fontcolor": "#aabbcc"},
        )
        svg_str = ET.tostring(root, encoding="unicode")
        assert "#aabbcc" in svg_str


# ============================================================================
# Legend, columns_n
# ============================================================================

class TestSituationLegendColumnsN:
    def _get_legend_texts(self, gdf_departments, columns_n):
        root = _render_situation(
            gdf_departments,
            legend_params={"title": "Type", "columns_n": columns_n},
        )
        ns = {"svg": "http://www.w3.org/2000/svg"}
        for g in root.findall(".//svg:g", ns):
            if "legend_situation" in g.get("id", ""):
                return g.findall(".//svg:text", ns)
        return []

    def test_columns_n_2_label_x_positions_differ(self, gdf_departments):
        """With 2 columns, labels should span at least 2 distinct x positions."""
        texts = self._get_legend_texts(gdf_departments, columns_n=2)
        label_texts = [t for t in texts if t.text in ("A", "B", "C")]
        xs = sorted(set(round(float(t.get("x"))) for t in label_texts))
        assert len(xs) >= 2, f"Expected >=2 distinct x positions, got: {xs}"

    def test_columns_n_1_all_same_x(self, gdf_departments):
        """With 1 column, all labels should share the same x position."""
        texts = self._get_legend_texts(gdf_departments, columns_n=1)
        label_texts = [t for t in texts if t.text in ("A", "B", "C")]
        xs = set(round(float(t.get("x"))) for t in label_texts)
        assert len(xs) == 1, f"Expected single x position, got: {xs}"

    def test_columns_n_3_three_columns(self, gdf_departments):
        """With 3 categories and columns_n=3, all on the same row (same y)."""
        texts = self._get_legend_texts(gdf_departments, columns_n=3)
        label_texts = [t for t in texts if t.text in ("A", "B", "C")]
        ys = set(round(float(t.get("y"))) for t in label_texts)
        assert len(ys) == 1, f"Expected single y (all on one row), got: {ys}"


# ============================================================================
# Categorical readability warning (TICKET_67)
# ============================================================================

class TestCategoricalReadabilityWarning:

    def _make_symbol(self, n: int) -> dict:
        return {f"cat{i}": {"marker": "circle", "fill": "#333333"} for i in range(n)}

    def test_no_warning_at_threshold(self, gdf_departments, recwarn):
        """8 categories or fewer: no readability warning."""
        pts = _make_categorical_gdf(gdf_departments)
        m = Map(pts)
        m.add(Situation(pts, column="type", symbol=self._make_symbol(8)))
        assert not any("categories defined" in str(w.message) for w in recwarn.list)

    def test_warning_above_threshold(self, gdf_departments):
        """More than 8 categories triggers a readability warning."""
        import warnings as _w
        pts = _make_categorical_gdf(gdf_departments)
        m = Map(pts)
        with _w.catch_warnings(record=True) as caught:
            _w.simplefilter("always")
            m.add(Situation(pts, column="type", symbol=self._make_symbol(9)))
        assert any("categories defined" in str(r.message) for r in caught)

    def test_uniform_mode_never_warns(self, gdf_departments, recwarn):
        """Uniform mode (no symbol dict) never warns regardless of data size."""
        pts = _make_categorical_gdf(gdf_departments)
        m = Map(pts)
        m.add(Situation(pts, marker="star", fill="#f4a261"))
        assert not any("categories defined" in str(w.message) for w in recwarn.list)

    def test_warning_emitted_once(self, gdf_departments, recwarn):
        """The warning fires once per add_situation call, not per viewport."""
        pts = _make_categorical_gdf(gdf_departments)
        m = Map(pts)
        m.add(Situation(pts, column="type", symbol=self._make_symbol(10)))
        n = sum("categories defined" in str(w.message) for w in recwarn.list)
        assert n == 1


# ============================================================================
# Custom SVG markers
# ============================================================================

def test_svg_marker_offset_viewbox_and_legend(gdf_departments, tmp_path):
    """A viewBox not starting at 0 is centred on the point, and the legend
    shows the SVG marker itself, not a circle placeholder."""
    icon = tmp_path / "icon.svg"
    icon.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="-5 -5 10 10">'
                    '<rect id="icone" x="-5" y="-5" width="10" height="10" fill="#123456"/></svg>',
                    encoding="utf-8")
    pts = gdf_departments.head(2).copy()
    pts["type"] = "A"
    m = Map(gdf_departments) + Situation(
        pts, column="type", symbol={"A": {"marker": str(icon), "size": 20}},
        legend={"title": "T"})
    svg = m.to_string()
    import re
    assert svg.count('id="icone"') == 3          # two points and the legend
    groups = re.findall(r'<g (?:id="[^"]*" )?transform="translate\(([-\d.]+),([-\d.]+)\) '
                        r'scale\(([\d.]+)\)">\s*<(?:\w+:)?rect id="icone"', svg)
    assert len(groups) == 3
    assert all(float(s) == 2.0 for _, _, s in groups)
