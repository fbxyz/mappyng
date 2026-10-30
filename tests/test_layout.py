"""Tests for A6, add_title (loc), add_scale_bar (alpha), add_source."""

import xml.etree.ElementTree as ET

import pytest

from mappyng import Map
from mappyng.layers import Basemap

NS = {"svg": "http://www.w3.org/2000/svg"}


def _svg_root(m):
    return ET.fromstring(m.to_string())


# ============================================================================
# add_title, loc alignment
# ============================================================================

class TestAddTitleLoc:
    def _title_texts(self, gdf_departments, loc):
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.title(text="Mon titre", loc=loc)
        root = _svg_root(m)
        return root.findall(".//svg:text", NS)

    def test_loc_left_anchor_start(self, gdf_departments):
        texts = self._title_texts(gdf_departments, "left")
        title = next(t for t in texts if t.text == "Mon titre")
        assert title.get("text-anchor") == "start"

    def test_loc_center_anchor_middle(self, gdf_departments):
        texts = self._title_texts(gdf_departments, "center")
        title = next(t for t in texts if t.text == "Mon titre")
        assert title.get("text-anchor") == "middle"

    def test_loc_right_anchor_end(self, gdf_departments):
        texts = self._title_texts(gdf_departments, "right")
        title = next(t for t in texts if t.text == "Mon titre")
        assert title.get("text-anchor") == "end"

    def test_center_x_greater_than_left_x(self, gdf_departments):
        """Center-aligned title must have a larger x than left-aligned."""
        texts_left = self._title_texts(gdf_departments, "left")
        texts_center = self._title_texts(gdf_departments, "center")
        x_left = float(next(t for t in texts_left if t.text == "Mon titre").get("x"))
        x_center = float(next(t for t in texts_center if t.text == "Mon titre").get("x"))
        assert x_center > x_left

    def test_right_x_greater_than_center_x(self, gdf_departments):
        """Right-aligned title must have a larger x than center-aligned."""
        texts_center = self._title_texts(gdf_departments, "center")
        texts_right = self._title_texts(gdf_departments, "right")
        x_center = float(next(t for t in texts_center if t.text == "Mon titre").get("x"))
        x_right = float(next(t for t in texts_right if t.text == "Mon titre").get("x"))
        assert x_right > x_center

    def test_default_is_left(self, gdf_departments):
        """Without loc param, title should be left-aligned."""
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.title(text="Titre")
        root = _svg_root(m)
        texts = root.findall(".//svg:text", NS)
        title = next(t for t in texts if t.text == "Titre")
        assert title.get("text-anchor") == "start"


# ============================================================================
# add_title, subtitle wrapping
# ============================================================================

class TestSubtitleWrap:
    # A subtitle whose length exceeds the title's max_chars but fits within the
    # (wider) subtitle budget derived from the font-size ratio.
    _LONG = "Cumul du 30 juin 2026 au 6 juillet 2026, vigilance maximale"

    def _title_texts(self, gdf_departments, **kw):
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.title(text="Titre court", font_size=11, subtitle_font_size=9,
                    max_chars=50, **kw)
        return _svg_root(m).findall(".//svg:text", NS)

    def _sub_lines(self, texts):
        return [t.text for t in texts if t.text and t.text.startswith(("Cumul", "maximale"))]

    def test_subtitle_not_wrapped_at_title_budget(self, gdf_departments):
        """A 59-char subtitle must stay on ONE line: its own budget (~97 at the
        default 11/9 ratio) is wider than the title's 50."""
        texts = self._title_texts(gdf_departments, subtitle=self._LONG)
        lines = self._sub_lines(texts)
        assert lines == [self._LONG]

    def test_subtitle_max_chars_forces_wrap(self, gdf_departments):
        """An explicit subtitle_max_chars wraps the subtitle like the title."""
        texts = self._title_texts(gdf_departments, subtitle=self._LONG,
                                   subtitle_max_chars=50)
        lines = self._sub_lines(texts)
        assert len(lines) == 2
        assert lines[0].startswith("Cumul")

    def test_no_subtitle_max_chars_leak_into_title(self, gdf_departments):
        """subtitle_max_chars must not surface as an SVG attribute on the title."""
        texts = self._title_texts(gdf_departments, subtitle_max_chars=40)
        title = next(t for t in texts if t.text == "Titre court")
        assert title.get("subtitle_max_chars") is None
        assert title.get("subtitle-max-chars") is None


# ============================================================================
# add_scale_bar, alpha opacity
# ============================================================================

class TestAddScaleBarAlpha:
    def _scale_bar_elements(self, gdf_departments, alpha):
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.scale_bar(opacity=alpha)
        root = _svg_root(m)
        lines = root.findall(".//svg:line", NS)
        texts = root.findall(".//svg:text", NS)
        return lines, texts

    def test_alpha_1_no_opacity_attr(self, gdf_departments):
        """Full opacity: no explicit opacity attribute needed."""
        lines, texts = self._scale_bar_elements(gdf_departments, 1.0)
        scale_lines = [l for l in lines if l.get("opacity")]
        # At alpha=1.0 no opacity attribute is set
        assert len(scale_lines) == 0

    def test_alpha_half_sets_opacity(self, gdf_departments):
        """opacity=0.5 should produce opacity='0.5' on scale bar elements."""
        lines, texts = self._scale_bar_elements(gdf_departments, 0.5)
        opaque_lines = [l for l in lines if l.get("opacity") == "0.5"]
        assert len(opaque_lines) >= 1  # bar + ticks

    def test_alpha_applied_to_label_text(self, gdf_departments):
        """The scale bar label text should also carry the opacity."""
        _, texts = self._scale_bar_elements(gdf_departments, 0.3)
        opaque_texts = [t for t in texts if t.get("opacity") == "0.3"]
        assert len(opaque_texts) >= 1


# ============================================================================
# add_source, basic rendering
# ============================================================================

class TestAddSource:
    def test_source_text_rendered(self, gdf_departments):
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.source(text="IGN 2024")
        root = _svg_root(m)
        texts = root.findall(".//svg:text", NS)
        assert any(t.text and "IGN 2024" in t.text for t in texts)

    def test_source_layout_horizontal(self, gdf_departments):
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.source(text="Source: IGN", layout="horizontal")
        svg = m.to_string()
        assert "IGN" in svg

    @pytest.mark.parametrize("text", ["INSEE\nAuteur", "INSEE\\nAuteur"])
    def test_source_vertical_lines_side_by_side(self, gdf_departments, text):
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.source(text=text)
        texts = {t.text: t for t in _svg_root(m).findall(".//svg:text", NS)}
        first, second = texts["INSEE"], texts["Auteur"]
        # Rotated text: lines share the same baseline start y, shifted in x
        assert first.get("y") == second.get("y")
        assert float(second.get("x")) > float(first.get("x"))

    def test_source_horizontal_lines_stacked(self, gdf_departments):
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.source(text="INSEE\nAuteur", layout="horizontal")
        texts = {t.text: t for t in _svg_root(m).findall(".//svg:text", NS)}
        first, second = texts["INSEE"], texts["Auteur"]
        assert first.get("x") == second.get("x")
        assert float(second.get("y")) > float(first.get("y"))


# ============================================================================
# B1, font_scale
# ============================================================================

class TestFontScale:
    def _title_font_size(self, gdf_departments, font_scale):
        m = Map(gdf_departments, width=800, height=600, font_scale=font_scale)
        m.add(Basemap())
        m.title(text="Titre")
        root = ET.fromstring(m.to_string())
        texts = root.findall(".//svg:text", NS)
        title = next(t for t in texts if t.text == "Titre")
        return float(title.get("font-size"))

    def test_scale_1_equals_default(self, gdf_departments):
        from mappyng import defaults as D
        size = self._title_font_size(gdf_departments, 1.0)
        assert abs(size - D.TITLE_FONT_SIZE) < 0.1

    def test_scale_1_5_multiplies_title(self, gdf_departments):
        from mappyng import defaults as D
        size = self._title_font_size(gdf_departments, 1.5)
        assert abs(size - D.TITLE_FONT_SIZE * 1.5) < 0.5

    def test_scale_auto_gt_1_for_wide_map(self, gdf_departments):
        m = Map(gdf_departments, width=1600, height=900, font_scale="auto")
        assert m.font_scale > 1.0

    def test_scale_auto_equals_ratio(self, gdf_departments):
        import math

        from mappyng import defaults as D
        m = Map(gdf_departments, width=1200, height=900, font_scale="auto")
        expected = D.FONT_SCALE_AUTO_COEFF * math.sqrt((1200 * 900) / (D.FONT_SCALE_REFERENCE_WIDTH * D.FONT_SCALE_REFERENCE_HEIGHT))
        assert abs(m.font_scale - expected) < 0.001

    def test_scale_applies_to_scale_bar_label(self, gdf_departments):
        """font_scale=2.0 should produce a scale bar label font twice the default."""
        from mappyng import defaults as D
        m = Map(gdf_departments, width=800, height=600, font_scale=2.0)
        m.add(Basemap())
        m.scale_bar(length=100000, label="100 km")
        root = ET.fromstring(m.to_string())
        texts = root.findall(".//svg:text", NS)
        scale_label = next((t for t in texts if t.text and "km" in t.text), None)
        assert scale_label is not None
        assert float(scale_label.get("font-size")) == pytest.approx(D.SCALE_BAR_FONT_SIZE * 2.0)


# ============================================================================
# B3, cartouche viewport overflow / auto-expansion
# ============================================================================

class TestCartoucheOverflow:
    CARTOUCHE_PARAMS = {
        0: {
            "bbox": [-6890454, 1780151, -6799589, 1874186],
            "crs": 3857,
            "cartouche_title": "Test",
        }
    }

    def test_no_cartouche_viewbox_unchanged(self, gdf_departments):
        """Without cartouches, SVG viewBox starts at (0 0)."""
        m = Map(gdf_departments, width=800, height=600)
        svg = m.to_string()
        assert 'viewBox="0 0 800 600"' in svg

    def test_cartouche_viewbox_expands(self, gdf_departments, gdf_europe):
        """With left-side cartouches, SVG width should be larger than requested."""
        m = Map(gdf_europe, width=900, height=700,
                cartouche_params=self.CARTOUCHE_PARAMS)
        svg = m.to_string()
        root = ET.fromstring(svg)
        # viewBox x should be negative (cartouche extends left)
        viewbox = root.get("viewBox", "")
        parts = [float(v) for v in viewbox.split()]
        vb_x = parts[0]
        assert vb_x < 0, f"viewBox x={vb_x} should be negative with left cartouche"

    def test_cartouche_svg_width_larger(self, gdf_departments, gdf_europe):
        """SVG total width should exceed original width to include cartouche area."""
        m = Map(gdf_europe, width=900, height=700,
                cartouche_params=self.CARTOUCHE_PARAMS)
        svg = m.to_string()
        root = ET.fromstring(svg)
        svg_w = float(root.get("width", 0))
        assert svg_w > 900, f"SVG width {svg_w} should be > 900 (original)"

    def test_all_cartouche_svg_x_within_viewbox(self, gdf_departments, gdf_europe):
        """All cartouche viewport x-coordinates must be >= viewBox.x (no negative clip)."""
        m = Map(gdf_europe, width=900, height=700,
                cartouche_params=self.CARTOUCHE_PARAMS)
        svg = m.to_string()
        root = ET.fromstring(svg)
        vb_x = float(root.get("viewBox", "0 0 0 0").split()[0])
        for vp in m.cartouche_viewports.values():
            assert vp.viewbox.svg_x >= vb_x - 1  # 1px tolerance
