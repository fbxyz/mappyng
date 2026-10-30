"""Tests for element placement: fractions, percentages, pixels, geographic."""

import xml.etree.ElementTree as ET

import pytest
from pyproj import Transformer
from shapely.geometry import LineString

from mappyng import Map
from mappyng.errors import LayoutError
from mappyng.layers import Basemap, Choropleth
from mappyng.legend import BaseLegendConfig, compute_legend_position
from mappyng.position import resolve_position

SVG = "{http://www.w3.org/2000/svg}"


@pytest.fixture
def m(gdf_departments, bbox_metro):
    return Map(gdf_departments, bbox=bbox_metro, width=900, height=800)


@pytest.fixture
def vb(m):
    m.to_string()
    return m.main.viewbox


def _lonlat_to_map(lon, lat):
    return Transformer.from_crs("EPSG:4326", "EPSG:2154", always_xy=True).transform(lon, lat)


class TestResolvePosition:
    def test_none(self, vb):
        assert resolve_position(None, vb) is None

    def test_fractions_pair_and_dict_agree(self, vb):
        expected = (vb.content_x + 0.25 * vb.content_width,
                    vb.content_y + 0.75 * vb.content_height)
        assert resolve_position((0.25, 0.75), vb) == pytest.approx(expected)
        assert resolve_position({"x": 0.25, "y": 0.75}, vb) == pytest.approx(expected)

    def test_percentages_equal_fractions(self, vb):
        assert resolve_position({"x": "25%", "y": "75%"}, vb) == pytest.approx(
            resolve_position((0.25, 0.75), vb))
        assert resolve_position(("25%", 0.75), vb) == pytest.approx(
            resolve_position((0.25, 0.75), vb))

    def test_fractions_may_leave_the_map(self, vb):
        x, y = resolve_position((0.5, 1.05), vb)
        assert y > vb.content_y + vb.content_height

    def test_pixels(self, vb):
        assert resolve_position({"px": 120, "py": 80}, vb) == (120, 80)

    def test_geo_in_map_crs(self, vb):
        assert resolve_position({"geo": (700000, 6600000)}, vb) == pytest.approx(
            vb.geo_to_svg(700000, 6600000))

    def test_lon_lat(self, vb):
        x, y = _lonlat_to_map(2.35, 48.85)
        assert resolve_position({"lon": 2.35, "lat": 48.85}, vb) == pytest.approx(
            vb.geo_to_svg(x, y))

    def test_geo_with_explicit_crs(self, vb):
        assert resolve_position(
            {"geo": (2.35, 48.85), "crs": "EPSG:4326"}, vb
        ) == pytest.approx(resolve_position({"lon": 2.35, "lat": 48.85}, vb))

    def test_geo_with_same_crs_is_not_reprojected(self, vb):
        assert resolve_position(
            {"geo": (700000, 6600000), "crs": "EPSG:2154"}, vb
        ) == pytest.approx(vb.geo_to_svg(700000, 6600000))

    @pytest.mark.parametrize("bad", [
        "centre", (0.5,), {"geo": 3}, {"lon": 2.0}, {"x": "abc"}, {"x": None},
    ])
    def test_invalid(self, vb, bad):
        with pytest.raises(LayoutError):
            resolve_position(bad, vb)

    def test_non_finite_projection(self, vb):
        with pytest.raises(LayoutError):
            resolve_position({"geo": (float("inf"), 0.0)}, vb)

    def test_geo_crs_needs_map_crs(self, gdf_departments):
        bare = gdf_departments.copy().set_crs(None, allow_override=True)
        mm = Map(bare, bbox=[90000, 6040000, 1280000, 7150000])
        mm.to_string()
        with pytest.raises(LayoutError):
            resolve_position({"lon": 2.0, "lat": 48.0}, mm.main.viewbox)
        # coordinates in the map's own system need no CRS
        assert resolve_position({"geo": (700000, 6600000)}, mm.main.viewbox)


class TestLegendPosition:
    def test_geographic(self, vb):
        cfg = BaseLegendConfig(position={"lon": 4.3, "lat": 42.5})
        x, y = _lonlat_to_map(4.3, 42.5)
        assert compute_legend_position(cfg, vb) == pytest.approx(vb.geo_to_svg(x, y))

    def test_fractions_unchanged(self, vb):
        cfg = BaseLegendConfig(position={"x": 0.1, "y": 0.2})
        assert compute_legend_position(cfg, vb) == pytest.approx(
            (vb.content_x + 0.1 * vb.content_width,
             vb.content_y + 0.2 * vb.content_height))

    def test_pixels_unchanged(self, vb):
        cfg = BaseLegendConfig(position={"px": 33, "py": 44})
        assert compute_legend_position(cfg, vb) == (33, 44)


def _scale_bar_line(svg):
    """The long horizontal line of the scale bar (the bar, not its ticks)."""
    root = ET.fromstring(svg)
    lines = [l for l in root.iter(SVG + "line")
             if l.get("y1") == l.get("y2") and l.get("x1") != l.get("x2")]
    assert lines, "no scale bar line found"
    return max(lines, key=lambda l: float(l.get("x2")) - float(l.get("x1")))


class TestScaleBarInGulfOfLion:
    """Scale bar placed in the Gulf of Lion, clear of the coast."""

    POSITION = {"lon": 4.0, "lat": 42.6}
    LENGTH = 100_000

    def test_bar_starts_at_the_requested_point(self, m):
        m.add(Basemap())
        m.scale_bar(length=self.LENGTH, position=self.POSITION)
        svg = m.to_string()
        x, y = _lonlat_to_map(4.0, 42.6)
        ex, ey = m.main.viewbox.geo_to_svg(x, y)
        line = _scale_bar_line(svg)
        assert float(line.get("x1")) == pytest.approx(ex, abs=0.01)
        assert float(line.get("y1")) == pytest.approx(ey, abs=0.01)

    def test_bar_does_not_touch_the_coast(self, m, gdf_departments):
        x, y = _lonlat_to_map(4.0, 42.6)
        bar = LineString([(x, y), (x + self.LENGTH, y)])
        # keep 10 km of clearance for the label and ticks
        assert not bar.buffer(10_000).intersects(gdf_departments.union_all())

    def test_percent_and_geo_forms_render(self, m):
        m.scale_bar(length=self.LENGTH, position={"x": "50%", "y": "92%"})
        assert _scale_bar_line(m.to_string()) is not None


class TestOtherElements:
    def test_north_arrow_tip_geo(self, m):
        m.north_arrow(position={"lon": 4.0, "lat": 42.6})
        m.to_string()  # renders without error

    def test_source_geo(self, m):
        m.source("Source : IGN", position={"lon": 4.0, "lat": 42.6})
        root = ET.fromstring(m.to_string())
        x, y = _lonlat_to_map(4.0, 42.6)
        ex, ey = m.main.viewbox.geo_to_svg(x, y)
        texts = [t for t in root.iter(SVG + "text") if t.text == "Source : IGN"]
        assert len(texts) == 1
        assert float(texts[0].get("x")) == pytest.approx(ex, abs=0.01)
        assert float(texts[0].get("y")) == pytest.approx(ey, abs=0.01)

    def test_title_position_overrides_default_placement(self, m):
        m.title("Golfe du Lion", position={"px": 300, "py": 500}, loc="center")
        root = ET.fromstring(m.to_string())
        t = [t for t in root.iter(SVG + "text") if t.text == "Golfe du Lion"][0]
        assert float(t.get("x")) == pytest.approx(300)
        assert float(t.get("y")) == pytest.approx(500)
        assert t.get("text-anchor") == "middle"

    def test_title_default_placement_unchanged(self, m):
        m.title("Titre")
        root = ET.fromstring(m.to_string())
        t = [t for t in root.iter(SVG + "text") if t.text == "Titre"][0]
        assert float(t.get("y")) < m.main.viewbox.content_y

    def test_legend_geo_position(self, m, gdf_departments):
        gdf = gdf_departments.copy()
        gdf["v"] = range(len(gdf))
        m.add(Choropleth(gdf, column="v", legend={
            "orientation": "vertical", "position": {"lon": 4.0, "lat": 42.6}}))
        root = ET.fromstring(m.to_string())
        x, y = _lonlat_to_map(4.0, 42.6)
        ex, ey = m.main.viewbox.geo_to_svg(x, y)
        swatch = [r for r in root.iter(SVG + "rect")
                  if r.get("id") == "choropleth-legend-swatch-0"][0]
        assert float(swatch.get("x")) == pytest.approx(ex, abs=0.01)
        assert float(swatch.get("y")) >= ey - 0.01

    def test_geo_position_survives_yaml_round_trip(self, m):
        m.scale_bar(length=100_000,
                    position={"lon": 4.0, "lat": 42.6})
        yaml_text = m.to_yaml()
        assert "lon" in yaml_text and "42.6" in yaml_text
