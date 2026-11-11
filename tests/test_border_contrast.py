"""Tests for border_contrast: visible borders between similar neighbours."""

import xml.etree.ElementTree as ET

import numpy as np
import pytest
from shapely.geometry import Polygon, box

from mappyng import BorderContrast, Map
from mappyng.border_contrast import (
    contrast_ratio,
    find_weak_borders,
    luminance,
    parse_border_contrast,
)
from mappyng.layers import Category, Choropleth

SVG = "{http://www.w3.org/2000/svg}"
LIGHT_A, LIGHT_B, DARK_A, DARK_B = "#f0f0f0", "#e6e6e6", "#101010", "#181818"


def _squares(n):
    """n unit squares in a row: square k touches k-1 and k+1 along an edge."""
    return [box(k, 0, k + 1, 1) for k in range(n)]


class TestParse:
    def test_off(self):
        assert parse_border_contrast(None) is None
        assert parse_border_contrast(False) is None

    def test_true_and_fix_are_the_defaults(self):
        assert parse_border_contrast(True) == BorderContrast()
        assert parse_border_contrast("fix") == BorderContrast()

    def test_check(self):
        assert parse_border_contrast("check").mode == "check"

    def test_dict_and_instance(self):
        cfg = parse_border_contrast({"fill_ratio": 1.2, "dark": "#000"})
        assert cfg.fill_ratio == 1.2 and cfg.dark == "#000"
        assert parse_border_contrast(cfg) == cfg

    @pytest.mark.parametrize("bad", [
        "fixx", 3, {"nope": 1}, {"fill_ratio": 0}, {"light": "notacolour"},
        {"check_color": "none"},
    ])
    def test_invalid(self, bad):
        with pytest.raises(ValueError):
            parse_border_contrast(bad)

    def test_layer_rejects_a_bad_option_at_construction(self, gdf_departments):
        with pytest.raises(ValueError, match="mode"):
            Choropleth(gdf_departments, column="fid", border_contrast="oops")


class TestColourMaths:
    def test_extremes(self):
        assert contrast_ratio(luminance("#ffffff"), luminance("#000000")) == \
            pytest.approx(21.0)
        assert contrast_ratio(0.3, 0.3) == pytest.approx(1.0)

    def test_short_hex_and_names(self):
        assert luminance("#fff") == pytest.approx(luminance("white"))
        assert luminance("#000") == pytest.approx(luminance("black"))

    def test_unreadable_colour(self):
        with pytest.raises(ValueError, match="(?i)cannot read"):
            luminance("not-a-colour")

    def test_css_colour_forms(self):
        assert luminance("rgb(255, 255, 255)") == pytest.approx(luminance("white"))
        assert luminance("darkred") == pytest.approx(luminance("#8b0000"))


class TestFindWeakBorders:
    def cfg(self, **kw):
        return BorderContrast(**kw)

    def test_two_light_neighbours_with_a_light_outline(self):
        out = find_weak_borders(_squares(2), [LIGHT_A, LIGHT_B], "#ffffff",
                                self.cfg())
        assert len(out) == 1
        b = out[0]
        assert (b.i, b.j) == (0, 1)
        assert b.color == "#222222"            # a dark line on light fills
        assert b.geometry.length == pytest.approx(1.0)

    def test_two_dark_neighbours_with_a_dark_outline(self):
        out = find_weak_borders(_squares(2), [DARK_A, DARK_B], "#202020",
                                self.cfg())
        assert [b.color for b in out] == ["#ffffff"]   # a light line

    def test_strong_fill_contrast_needs_no_help(self):
        assert find_weak_borders(_squares(2), [LIGHT_A, DARK_A], "#ffffff",
                                 self.cfg()) == []

    def test_a_visible_outline_needs_no_help(self):
        assert find_weak_borders(_squares(2), [LIGHT_A, LIGHT_B], "#222222",
                                 self.cfg()) == []

    def test_no_outline_counts_as_weak(self):
        for stroke in (None, "none"):
            out = find_weak_borders(_squares(2), [LIGHT_A, LIGHT_B], stroke,
                                    self.cfg())
            assert len(out) == 1

    def test_only_the_affected_pair_is_reported(self):
        fills = [LIGHT_A, LIGHT_B, DARK_A]
        out = find_weak_borders(_squares(3), fills, "#ffffff", self.cfg())
        assert [(b.i, b.j) for b in out] == [(0, 1)]

    def test_corner_contact_is_not_a_border(self):
        a, b = box(0, 0, 1, 1), box(1, 1, 2, 2)
        assert find_weak_borders([a, b], [LIGHT_A, LIGHT_B], "#fff",
                                 self.cfg()) == []

    def test_separate_areas_have_no_border(self):
        a, b = box(0, 0, 1, 1), box(3, 0, 4, 1)
        assert find_weak_borders([a, b], [LIGHT_A, LIGHT_B], "#fff",
                                 self.cfg()) == []

    def test_a_border_made_of_several_parts(self):
        # a U-shaped area and a block that fills its notch and sticks out
        # above it: they share three separate stretches of border
        u = Polygon([(0, 0), (3, 0), (3, 2), (2, 2), (2, 1), (1, 1), (1, 2),
                     (0, 2)])
        block = box(1, 1, 2, 3)
        out = find_weak_borders([u, block], [LIGHT_A, LIGHT_B], "#ffffff",
                                self.cfg())
        assert len(out) == 1
        assert out[0].geometry.length == pytest.approx(3.0)

    def test_check_mode_uses_the_check_colour(self):
        out = find_weak_borders(_squares(2), [LIGHT_A, LIGHT_B], "#ffffff",
                                self.cfg(mode="check", check_color="#ff00ff"))
        assert [b.color for b in out] == ["#ff00ff"]

    def test_thresholds_are_configurable(self):
        fills = [LIGHT_A, LIGHT_B]
        assert find_weak_borders(_squares(2), fills, "#ffffff",
                                 self.cfg(fill_ratio=1.0)) == []
        assert find_weak_borders(_squares(2), fills, "#ffffff",
                                 self.cfg(stroke_ratio=1.0)) == []

    def test_fewer_than_two_areas(self):
        assert find_weak_borders(_squares(1), [LIGHT_A], "#fff",
                                 self.cfg()) == []


def _border_paths(svg):
    return [p for p in ET.fromstring(svg).iter(SVG + "path")
            if p.get("class") == "choropleth-border"]


def _polygon_paths(svg):
    return sorted(
        (p.get("id"), p.get("d"), p.get("fill"), p.get("stroke"))
        for p in ET.fromstring(svg).iter(SVG + "path")
        if (p.get("id") or "").startswith("choro-"))


@pytest.fixture
def light_gdf(gdf_departments):
    """Departments with a light two-tone palette: many weak borders."""
    g = gdf_departments.copy()
    g["v"] = np.linspace(0, 1, len(g)) ** 3
    return g


def _svg(gdf, **kw):
    m = Map(gdf, width=700, height=700)
    m.add(Choropleth(gdf, column="v", cmap="Blues", method="Quantiles",
                     num_classes=5, stroke="#eeeeee", stroke_width=0.4, **kw))
    return m.to_string()


class TestChoropleth:
    def test_off_by_default(self, light_gdf):
        assert _border_paths(_svg(light_gdf)) == []

    def test_fix_draws_only_the_shared_borders_on_top(self, light_gdf):
        off, on = _svg(light_gdf), _svg(light_gdf, border_contrast=True)
        assert _border_paths(on)
        # the polygons, their fills and their own outline are untouched
        assert _polygon_paths(on) == _polygon_paths(off)

    def test_redrawn_borders_do_not_catch_the_pointer(self, light_gdf):
        for p in _border_paths(_svg(light_gdf, border_contrast=True)):
            assert p.get("pointer-events") == "none"
            assert p.get("fill") == "none"

    def test_fix_colours_are_the_light_and_dark_candidates(self, light_gdf):
        colors = {p.get("stroke") for p in
                  _border_paths(_svg(light_gdf, border_contrast=True))}
        assert colors <= {"#222222", "#ffffff"} and colors

    def test_fix_does_not_warn(self, light_gdf):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            _svg(light_gdf, border_contrast=True)

    def test_check_warns_and_marks_the_borders(self, light_gdf):
        with pytest.warns(UserWarning, match="hard to see"):
            svg = _svg(light_gdf, border_contrast="check")
        paths = _border_paths(svg)
        assert paths and {p.get("stroke") for p in paths} == {"#ff00ff"}
        assert float(paths[0].get("stroke-width")) == pytest.approx(1.2)

    def test_options_dict(self, light_gdf):
        svg = _svg(light_gdf, border_contrast={"light": "#ffff00",
                                               "width_factor": 2.0})
        paths = _border_paths(svg)
        assert paths and float(paths[0].get("stroke-width")) == \
            pytest.approx(0.8)

    def test_a_visible_outline_adds_nothing(self, light_gdf):
        m = Map(light_gdf, width=700, height=700)
        m.add(Choropleth(light_gdf, column="v", cmap="Blues",
                         method="Quantiles", num_classes=5, stroke="#000000",
                         border_contrast=True))
        assert _border_paths(m.to_string()) == []

    @pytest.mark.parametrize("extra", [
        {"dissolve": True}, {"simplify": "auto"}, {"simplify": 5000},
        {"opacity_column": "v"},
        {"opacity_column": "v", "blend_background": "#ffffff"},
    ])
    def test_combines_with_other_options(self, light_gdf, extra):
        svg = _svg(light_gdf, border_contrast=True, **extra)
        assert ET.fromstring(svg) is not None

    def test_zoom_and_cartouches_get_their_own_borders(self, light_gdf):
        from mappyng import Inset, Insets, Zoom

        def count(**kw):
            m = Map(light_gdf, bbox=[90000, 6040000, 1280000, 7150000],
                    width=800, height=800)
            m.add(Zoom([500000, 6740000, 780000, 6940000], x=520, y=90,
                       width=250, height=250))
            m.add(Insets([Inset("Corse", crs=2154,
                                bbox=[1150000, 6040000, 1250000, 6200000])]))
            m.add(Choropleth(light_gdf, column="v", cmap="Blues",
                             method="Quantiles", num_classes=5,
                             stroke="#eeeeee", border_contrast=True, **kw))
            return len(_border_paths(m.to_string()))
        assert count() > count(on_zoom=False, on_cartouches=False)

    def test_yaml_round_trip_keeps_the_option(self, light_gdf):
        m = Map(light_gdf, width=400, height=400)
        m.add(Choropleth(light_gdf, column="v",
                         border_contrast=BorderContrast(mode="check")))
        text = m.to_yaml()
        assert "border_contrast" in text and "check" in text


class TestCategory:
    def test_similar_categories(self, gdf_departments):
        g = gdf_departments.copy()
        g["cat"] = [("A", "B")[i % 2] for i in range(len(g))]
        fill = {"A": "#f4f4f4", "B": "#eaeaea"}

        def svg(**kw):
            m = Map(g, width=600, height=600)
            m.add(Category(g, column="cat", fill_map=fill, stroke="#ffffff",
                           **kw))
            return m.to_string()
        assert _border_paths(svg()) == []
        assert _border_paths(svg(border_contrast=True))
