"""Regression tests for bugs found in the 1.0.0 review."""

import re
import struct
import warnings
import xml.etree.ElementTree as ET

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point

from mappyng import (
    Basemap,
    Category,
    Choropleth,
    Label,
    Map,
    Proportional,
    RadialGradient,
    Vector,
    Zoom,
)

SVG = "{http://www.w3.org/2000/svg}"
ZOOM_BBOX = [586377, 6780533, 739396, 6904563]
FILL_MAP = {0: "#1f78b4", 1: "#33a02c", 2: "#e31a1c"}


@pytest.fixture
def dep(gdf_departments):
    gdf = gdf_departments.copy()
    rng = np.random.default_rng(0)
    gdf["rate"] = rng.random(len(gdf)) * 10
    gdf["count"] = rng.integers(1000, 100000, len(gdf))
    gdf["group"] = np.arange(len(gdf)) % 3
    return gdf


@pytest.fixture
def make(dep, bbox_metro):
    def _make(**kwargs):
        return Map(dep, bbox=bbox_metro, width=800, height=900, **kwargs)
    return _make


def _paths(svg, prefix="choro-"):
    return [p for p in ET.fromstring(svg).iter(SVG + "path")
            if (p.get("id") or "").startswith(prefix)]


def _prop_radii(svg):
    return [float(c.get("r")) for c in ET.fromstring(svg).iter(SVG + "circle")
            if (c.get("id") or "").startswith("prop-")
            and "legend" not in (c.get("id") or "")]


# ---------------------------------------------------------------------------
# Canvas
# ---------------------------------------------------------------------------

class TestAutosize:
    def test_zoom_survives_autosize(self, make):
        m = make().add(Zoom(ZOOM_BBOX), Basemap())
        m.autosize()
        assert 'id="zoom"' in m.to_string()

    def test_gradient_survives_autosize(self, make):
        gradient = RadialGradient([(0.0, "#ffffff"), (1.0, "#000000")])
        m = make().add(gradient, Basemap())
        m.autosize()
        assert f'id="{gradient.gradient_id}"' in m.to_string()

    def test_zoom_is_not_duplicated(self, make):
        m = make().add(Zoom(ZOOM_BBOX), Basemap())
        m.autosize()
        assert m.to_string().count('<g id="zoom"') == 1


class TestPngDpi:
    def test_dpi_scales_the_image(self, make, tmp_path):
        pytest.importorskip("cairosvg")
        sizes = {}
        for dpi in (96, 192):
            path = tmp_path / f"map_{dpi}.png"
            Map(make().gdf, width=400, height=450).add(Basemap()).render(
                str(path), dpi=dpi)
            sizes[dpi] = struct.unpack(">II", path.read_bytes()[16:24])
        assert sizes[96] == (400, 450)
        assert sizes[192] == (800, 900)


# ---------------------------------------------------------------------------
# Layers
# ---------------------------------------------------------------------------

class TestLayerReuse:
    def test_layer_added_to_two_maps_is_drawn_on_both(self, dep, make):
        layer = Choropleth(dep, column="rate", legend=False)
        first = make().add(layer).to_string()
        second = make().add(layer).to_string()
        assert len(_paths(first)) > 0
        assert len(_paths(second)) == len(_paths(first))

    def test_first_map_keeps_the_original_object(self, dep, make):
        layer = Choropleth(dep, column="rate", legend=False)
        m1 = make().add(layer)
        m2 = make().add(layer)
        assert m1.layers[0] is layer
        assert m2.layers[0] is not layer


class TestLayerCrs:
    @pytest.mark.parametrize("build", [
        lambda g: Choropleth(g, column="rate", legend=False),
        lambda g: Vector(g, stroke="#ff0000"),
    ])
    def test_polygons_in_another_crs_are_reprojected(self, dep, make, build):
        same = make().add(build(dep)).to_string()
        other = make().add(build(dep.to_crs(4326))).to_string()
        assert other.count("<path") == same.count("<path") > 0

    def test_proportional_in_another_crs(self, dep, make):
        pts = dep.copy()
        pts["geometry"] = pts.geometry.centroid
        same = make().add(Proportional(pts, column="count", legend=False))
        other = make().add(
            Proportional(pts.to_crs(4326), column="count", legend=False))
        assert len(_prop_radii(other.to_string())) == len(
            _prop_radii(same.to_string())) > 0


class TestStrokeWidthZero:
    def test_choropleth(self, dep, make):
        svg = make().add(
            Choropleth(dep, column="rate", stroke_width=0, legend=False)
        ).to_string()
        assert {p.get("stroke-width") for p in _paths(svg)} == {"0"}

    def test_category(self, dep, make):
        svg = make().add(Category(dep, column="group", fill_map=FILL_MAP,
                                  stroke_width=0, legend=False)).to_string()
        assert {p.get("stroke-width") for p in _paths(svg)} == {"0"}

    def test_basemap(self, make):
        svg = make().add(Basemap(stroke_width=0)).to_string()
        widths = {p.get("stroke-width")
                  for p in ET.fromstring(svg).iter(SVG + "path")}
        assert widths == {"0"}


class TestMissingColumn:
    @pytest.mark.parametrize("build", [
        lambda g: Choropleth(g, column="typo"),
        lambda g: Category(g, column="typo", fill_map=FILL_MAP),
        lambda g: Proportional(g, column="typo"),
        lambda g: Label(g, column="typo"),
    ])
    def test_plain_error_at_construction(self, dep, build):
        with pytest.raises(ValueError, match="'typo' is not a column of gdf"):
            build(dep)


# ---------------------------------------------------------------------------
# Missing values
# ---------------------------------------------------------------------------

class TestMissingValues:
    def test_missing_label_text_draws_no_label(self, dep, make):
        pts = gpd.GeoDataFrame(
            {"name": ["A", np.nan, None, "C"]},
            geometry=[Point(600000, 6600000), Point(700000, 6700000),
                      Point(500000, 6500000), Point(400000, 6400000)],
            crs=dep.crs)
        svg = make().add(Label(pts, column="name")).to_string()
        assert svg.count('class="mappyng-label"') == 2
        assert ">nan<" not in svg and ">None<" not in svg

    def test_missing_opacity_counts_as_zero(self, dep, make):
        dep = dep.copy()
        dep["p"] = 1.0
        dep.loc[dep.index[0], "p"] = np.nan
        svg = make().add(Choropleth(dep, column="rate", opacity_column="p",
                                    min_opacity=0.2, legend=False)).to_string()
        opacities = {p.get("fill-opacity") for p in _paths(svg)}
        assert opacities == {"0.2", "1.0"}

    def test_column_without_any_value(self, dep, make):
        dep = dep.copy()
        dep["empty"] = np.nan
        m = make().add(Choropleth(dep, column="empty", legend=False))
        with pytest.raises(ValueError, match="holds no value"):
            m.to_string()


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class TestCustomBreaks:
    def _report(self, make, dep, breaks, cmap="YlOrRd"):
        m = make().add(Choropleth(dep, column="rate", method=breaks,
                                  cmap=cmap, legend=False))
        m.to_string()
        return next(iter(m.classification_reports.values()))

    def test_breaks_below_the_data_maximum_keep_the_class_count(
            self, make, dep):
        with pytest.warns(UserWarning, match="above the last break"):
            report = self._report(make, dep, [0, 2, 4, 6, 8])
        assert report.applied_classes == 4
        assert sum(report.counts) == len(dep)
        # the upper bound is the data maximum, at the legend's precision
        assert report.bins[-1] == pytest.approx(dep["rate"].max(), abs=0.1)

    def test_explicit_colour_list_with_overflowing_data(self, make, dep):
        colours = ["#111111", "#222222", "#333333", "#444444"]
        with pytest.warns(UserWarning, match="above the last break"):
            report = self._report(make, dep, [0, 2, 4, 6, 8], cmap=colours)
        assert report.colors == colours

    @pytest.mark.parametrize("breaks", [
        (0, 2.5, 5, 7.5, 10), np.array([0, 2.5, 5, 7.5, 10])])
    def test_any_sequence_of_breaks(self, make, dep, breaks):
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            report = self._report(make, dep, breaks)
        assert report.applied_classes == 4


class TestClassificationReports:
    def test_choropleth_and_category_reports_do_not_collide(self, dep, make):
        m = make().add(
            Choropleth(dep, column="rate", legend=False),
            Category(dep, column="group", fill_map=FILL_MAP, legend=False))
        m.to_string()
        names = sorted(type(r).__name__
                       for r in m.classification_reports.values())
        assert names == ["CategoryReport", "ClassificationReport"]

    def test_their_element_ids_do_not_collide(self, dep, make):
        m = make().add(
            Choropleth(dep, column="rate", legend=False),
            Category(dep, column="group", fill_map=FILL_MAP, legend=False))
        ids = [p.get("id") for p in _paths(m.to_string())]
        assert len(ids) == len(set(ids)) > 0


# ---------------------------------------------------------------------------
# Proportional
# ---------------------------------------------------------------------------

class TestProportionalOptions:
    def test_legend_false_draws_no_legend(self, dep, make):
        with_legend = make().add(Proportional(dep, column="count"))
        without = make().add(Proportional(dep, column="count", legend=False))
        assert "proportional-legend" in with_legend.to_string()
        assert "proportional-legend" not in without.to_string()

    def test_reference_value_alone_maps_to_max_radius(self, dep, make):
        top = float(dep["count"].max())
        svg = make().add(Proportional(
            dep, column="count", max_radius=30, reference_value=4 * top,
            legend=False)).to_string()
        assert max(_prop_radii(svg)) == pytest.approx(15.0, abs=0.01)


# ---------------------------------------------------------------------------
# Interactive export
# ---------------------------------------------------------------------------

class TestTooltips:
    def test_dissolved_polygons_show_their_class(self, dep, make):
        m = make().add(Choropleth(dep, column="rate", dissolve=True,
                                  legend=False))
        svg = m.to_interactive(columns=["LIB_GEO", "rate"]).svg
        tips = re.findall(r'data-tooltip="([^"]*)"', svg)
        assert tips
        # a class range, never the name of one department of the class
        assert all("LIB_GEO" not in t for t in tips)
        assert all("–" in t for t in tips)

    def test_category_layer_gets_tooltips(self, dep, make):
        m = make().add(Category(dep, column="group", fill_map=FILL_MAP,
                                legend=False))
        svg = m.to_interactive(columns=["LIB_GEO"]).svg
        drawn = len(_paths(svg))
        assert svg.count("data-tooltip=") == drawn > 0

    def test_quoted_font_family_keeps_the_script_valid(self, dep, make):
        m = make().add(Choropleth(dep, column="rate", legend=False))
        svg = m.to_interactive(
            columns=["rate"],
            tooltip={"font_family": "'Helvetica Neue', sans-serif"}).svg
        assert "'font-family','\\'Helvetica Neue\\', sans-serif'" in svg


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

class TestNumberedLabels:
    def test_data_label_is_escaped_once(self, dep, make):
        pts = gpd.GeoDataFrame(
            {"name": ["A & B", "C"]},
            geometry=[Point(600000, 6600000), Point(400000, 6400000)],
            crs=dep.crs)
        svg = make().add(
            Label(pts, column="name", numbered_above=1)).to_string()
        assert 'data-label="A &amp; B"' in svg
        assert "&amp;amp;" not in svg


class TestLabelDisplacement:
    def test_wide_label_can_move(self):
        """A label wider than twice max_displacement still gets moved."""
        import random

        from mappyng.toponyme import (
            LabelCandidate,
            LabelConfig,
            LabelPlacer,
            ObstacleIndex,
        )
        cfg = LabelConfig(max_displacement=10)
        lab = LabelCandidate(text="x" * 40, anchor_x=200, anchor_y=200,
                             anchor_r=2, width=120, height=12,
                             x=204, y=184, pos="NE")
        placer = LabelPlacer([lab], ObstacleIndex([]), [],
                             (0, 0, 400, 400), cfg, random.Random(1))
        moved = 0
        for _ in range(200):
            before = (lab.x, lab.y)
            placer.mcmove(0.05)
            moved += (lab.x, lab.y) != before
        assert moved > 0


# ---------------------------------------------------------------------------
# YAML
# ---------------------------------------------------------------------------

class TestYamlRoundTrip:
    def test_font_scale(self, dep, make):
        m = make(font_scale=2.0).add(Basemap())
        assert Map.from_yaml(m.to_yaml(), gdf=dep).font_scale == 2.0

    def test_auto_font_scale_stays_auto(self, dep, make):
        assert "font_scale" not in make().add(Basemap()).to_yaml()

    def test_fill_map_with_integer_keys(self, dep, make):
        m = make().add(Category(dep, column="group", fill_map=FILL_MAP,
                                legend=False))
        again = Map.from_yaml(m.to_yaml(), gdf=dep)
        assert len(_paths(again.to_string())) == len(_paths(m.to_string())) > 0

    def test_missing_file_is_reported_as_such(self, dep):
        with pytest.raises(FileNotFoundError, match="no such file"):
            Map.from_yaml("does_not_exist.yaml", gdf=dep)


# ---------------------------------------------------------------------------
# Tiles
# ---------------------------------------------------------------------------

class TestTileCache:
    def test_url_templates_of_one_server_do_not_share_a_cache(self, tmp_path):
        from mappyng.tile import _cache_path_for
        base = "https://server.example.org/a/very/long/common/prefix/"
        a = _cache_path_for(tmp_path, base + "one/{z}/{x}/{y}.png", 3, 1, 2)
        b = _cache_path_for(tmp_path, base + "two/{z}/{x}/{y}.png", 3, 1, 2)
        assert a != b

    def test_alias_cache_path_is_unchanged(self, tmp_path):
        from mappyng.tile import _cache_path_for
        path = _cache_path_for(tmp_path, "cartodb_positron", 3, 1, 2)
        assert path == tmp_path / "cartodb_positron" / "3" / "1" / "2.png"


# ---------------------------------------------------------------------------
# Second review: chrome, legends, rasters, colours, situation
# ---------------------------------------------------------------------------

def _legend_groups(svg, base="choropleth-legend"):
    return [g for g in ET.fromstring(svg).iter(SVG + "g")
            if re.fullmatch(base + r"(-\d+)?", g.get("id") or "")]


class TestChrome:
    def test_negative_source_rotation_is_valid_svg(self, make):
        m = make()
        m.add(Basemap())
        m.source("Src", layout="horizontal", rotation=-90)
        svg = m.to_string()
        assert "rotate(--" not in svg
        assert "rotate(90," in svg

    def test_source_opacity_zero_is_kept(self, make):
        m = make()
        m.source("Src", opacity=0)
        assert re.search(r'opacity="0"[^>]*>Src', m.to_string())

    def test_scale_bar_in_metres_for_a_small_map(self, dep):
        small = dep.iloc[:1].copy()
        small["geometry"] = small.geometry.centroid.buffer(150)
        m = Map(small, width=800, height=900)
        m.scale_bar()
        labels = re.findall(r">(\d[^<]*) (k?m)<", m.to_string())
        assert labels and labels[0][1] == "m"
        assert float(labels[0][0]) >= 1

    def test_scale_bar_on_a_map_in_degrees(self, dep):
        metro = dep.cx[90000:1280000, 6040000:7150000].to_crs(4326)
        m = Map(metro, width=800, height=900)
        with pytest.warns(UserWarning, match="degrees"):
            m.scale_bar()
            svg = m.to_string()
        value, unit = re.findall(r">(\d[^<]*) (k?m)<", svg)[0]
        assert unit == "km" and 50 <= float(value) <= 500

    def test_north_arrow_label_follows_font_scale(self, make):
        def size(scale):
            m = make(font_scale=scale)
            m.north_arrow()
            return float(re.search(
                r'font-size="([\d.]+)"[^>]*class="north-arrow"',
                m.to_string()).group(1))
        assert size(2) == pytest.approx(2 * size(1))


class TestLegends:
    def test_two_legends_are_stacked_with_unique_ids(self, make, dep):
        m = make()
        m.add(Choropleth(dep, column="rate", legend={"title": "A"}))
        m.add(Choropleth(dep, column="count", method="Quantiles",
                         legend={"title": "B"}))
        svg = m.to_string()
        first, second = _legend_groups(svg)
        assert first.get("id") != second.get("id")

        def extent(group):
            ys = [float(r.get("y")) for r in group.iter(SVG + "rect")]
            return min(ys), max(ys)
        assert extent(second)[0] > extent(first)[1]
        ids = [e.get("id") for e in ET.fromstring(svg).iter()
               if "legend" in (e.get("id") or "")]
        assert len(ids) == len(set(ids))

    def test_explicit_position_is_not_moved(self, make, dep):
        m = make()
        m.add(Choropleth(dep, column="rate", legend={"title": "A"}))
        m.add(Choropleth(dep, column="count", method="Quantiles",
                         legend={"title": "B", "position": {"px": 500, "py": 100}}))
        second = _legend_groups(m.to_string())[1]
        assert float(next(second.iter(SVG + "text")).get("y")) == pytest.approx(100)

    def test_custom_labels_in_a_horizontal_legend(self, make, dep):
        m = make()
        m.add(Choropleth(dep, column="rate", num_classes=4, legend={
            "orientation": "horizontal", "labels": ["a", "b", "c", "d"]}))
        texts = [t.text for t in _legend_groups(m.to_string())[0].iter(SVG + "text")]
        assert texts == ["a", "b", "c", "d"]

    def test_wrong_number_of_labels_is_an_error(self, make, dep):
        m = make()
        m.add(Choropleth(dep, column="rate", num_classes=4,
                         legend={"labels": ["a", "b"]}))
        with pytest.raises(ValueError, match="one label per class"):
            m.to_string()

    def test_unknown_legend_option_names_the_typo(self, make, dep):
        m = make()
        m.add(Choropleth(dep, column="rate", legend={"titel": "A"}))
        with pytest.raises(ValueError, match="did you mean 'title'"):
            m.to_string()

    def test_frame_can_be_disabled_from_a_dict(self, make, dep):
        m = make()
        m.add(Choropleth(dep, column="rate",
                         legend={"frame": {"enabled": False}}))
        assert 'class="legend-frame"' not in m.to_string()

    def test_unknown_frame_option_is_an_error(self, make, dep):
        m = make()
        m.add(Choropleth(dep, column="rate", legend={"frame": {"colour": "red"}}))
        with pytest.raises(ValueError, match="legend frame"):
            m.to_string()

    def test_horizontal_frame_encloses_the_nodata_entry(self, make, dep):
        gdf = dep.copy()
        gdf.loc[gdf.index[:5], "rate"] = np.nan
        m = make()
        m.add(Choropleth(gdf, column="rate", legend={
            "orientation": "horizontal", "frame": True}))
        group = _legend_groups(m.to_string())[0]
        rects = list(group.iter(SVG + "rect"))
        frame = next(r for r in rects if r.get("class") == "legend-frame")
        nodata = next(r for r in rects if (r.get("id") or "").endswith("nodata"))
        right = lambda r: float(r.get("x")) + float(r.get("width"))  # noqa: E731
        assert right(frame) > right(nodata)

    @pytest.mark.parametrize("options", [
        {"histogram": True, "histogram_height": 200},
        {"label_rotation": -90, "label_anchor": "end", "decimals": 6},
    ])
    def test_horizontal_legend_fits_in_the_canvas(self, make, dep, options):
        m = make()
        m.add(Choropleth(dep, column="rate", legend={
            "orientation": "horizontal", **options}))
        root = ET.fromstring(m.to_string())
        height = float(root.get("viewBox").split()[3])
        group = _legend_groups(m.to_string())[0]
        if "histogram" in options:
            bottom = max(float(r.get("y")) + float(r.get("height"))
                         for r in group.iter(SVG + "rect"))
        else:
            text = [t for t in group.iter(SVG + "text") if t.get("transform")][-1]
            bottom = (float(text.get("y"))
                      + len(text.text) * float(text.get("font-size")) * 0.5)
        assert bottom <= height

    def test_subtitle_follows_the_title_offset_once(self, make, dep):
        def ys(**extra):
            m = make()
            m.add(Choropleth(dep, column="rate", legend={
                "title": "T", "subtitle": "S", **extra}))
            texts = list(_legend_groups(m.to_string())[0].iter(SVG + "text"))
            return float(texts[0].get("y")), float(texts[1].get("y"))
        base, moved = ys(), ys(title_offset_y=30)
        assert moved[0] - base[0] == pytest.approx(30)
        assert moved[1] - base[1] == pytest.approx(30)

    def test_backslash_hatch_leans_backwards(self):
        from mappyng.legend import ensure_hatch_pattern
        defs = ET.Element("defs")
        ensure_hatch_pattern(defs, "p", "#000", style="\\\\\\")
        assert defs[0].get("patternTransform") == "rotate(-45)"

    def test_range_wording_can_be_translated(self, make, dep):
        m = make()
        m.add(Choropleth(dep, column="rate", legend={
            "label_position": "center", "label_format": "range",
            "range_format": "de {low} à {high}"}))
        svg = m.to_string()
        assert ">de " in svg and ">from " not in svg


class TestColours:
    @pytest.mark.parametrize("background", ["white", "#fff", "rgb(255,255,255)"])
    def test_blend_background_accepts_css_colours(self, make, dep, background):
        def fills(bg):
            m = make()
            m.add(Choropleth(dep, column="rate", opacity_column="count",
                             blend_background=bg, legend=False))
            return [p.get("fill") for p in _paths(m.to_string())]
        assert fills(background) == fills("#ffffff")

    def test_border_contrast_accepts_css_colour_names(self, make, dep):
        m = make()
        m.add(Choropleth(dep, column="rate", num_classes=4, border_contrast=True,
                         cmap=["lightyellow", "gold", "orangered", "darkred"]))
        assert m.to_string()

    def test_colormap_is_a_copy(self):
        from mappyng.config import ConfigManager
        ConfigManager.get_colormap("Blues", 5).append("x")
        assert len(ConfigManager.get_colormap("Blues", 5)) == 5

    def test_unknown_style_key_is_an_error(self, dep):
        with pytest.raises(ValueError, match="title_colour"):
            Map(dep, style={"title_colour": "#ff0000"})


class TestSituationSymbols:
    def test_float_column_matches_integer_keys(self, make, dep):
        from mappyng import Situation
        gdf = dep.copy()
        gdf["kind"] = (np.arange(len(gdf)) % 2).astype(float)
        m = make()
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            m.add(Situation(gdf, column="kind", symbol={
                0: {"fill": "#00ff00"}, 1: {"fill": "#0000ff"}}))
            svg = m.to_string()
        assert "#00ff00" in svg and "#0000ff" in svg and "#e63946" not in svg

    def test_unmapped_category_warns(self, make, dep):
        from mappyng import Situation
        m = make()
        m.add(Situation(dep, column="group", symbol={0: {"fill": "#00ff00"}}))
        with pytest.warns(UserWarning, match="no entry in symbol"):
            m.to_string()

    def test_unknown_marker_warns(self, make, dep):
        from mappyng import Situation
        m = make()
        m.add(Situation(dep, marker="hexagone"))
        with pytest.warns(UserWarning, match="unknown marker"):
            m.to_string()


class TestRasterReading:
    @pytest.fixture
    def write(self, tmp_path):
        rasterio = pytest.importorskip("rasterio")
        from rasterio.transform import from_bounds

        def _write(array, crs="EPSG:2154", nodata=None,
                   bounds=(90000, 6040000, 1280000, 7150000)):
            count, height, width = array.shape
            path = tmp_path / f"r{len(list(tmp_path.iterdir()))}.tif"
            with rasterio.open(
                path, "w", driver="GTiff", height=height, width=width,
                count=count, dtype=array.dtype, crs=crs, nodata=nodata,
                transform=from_bounds(*bounds, width, height),
            ) as dst:
                dst.write(array)
            return str(path)
        return _write

    @staticmethod
    def _image(make, paths):
        from mappyng import Raster
        image = pytest.importorskip("PIL.Image")
        import base64
        import io
        m = make()
        m.add(Raster(paths=paths))
        found = re.search(r"base64,([A-Za-z0-9+/=]+)", m.to_string())
        if found is None:
            return None
        return image.open(io.BytesIO(base64.b64decode(found.group(1))))

    def test_elevation_model_is_stretched(self, make, write):
        rows, cols = np.mgrid[0:50, 0:50]
        dem = (cols * 40.0)[None].astype("float32")      # 0 to 1960 m
        pixels = np.asarray(self._image(make, {"dem": write(dem)}))[..., 0]
        assert pixels.min() == 0 and pixels.max() == 255
        assert (np.diff(pixels.astype(int), axis=1) >= 0).all()

    def test_nodata_is_transparent(self, make, write):
        data = np.full((1, 40, 40), 200, "uint8")
        data[0, :20] = 0
        img = self._image(make, {"r": write(data, nodata=0)})
        assert img.mode == "RGBA"
        alpha = np.asarray(img)[..., 3]
        assert alpha[:20].max() == 0 and alpha[20:].min() == 255

    def test_gray_alpha_raster(self, make, write):
        data = np.stack([np.full((40, 40), 120, "uint8"),
                         np.full((40, 40), 255, "uint8")])
        img = self._image(make, {"r": write(data)})
        assert np.asarray(img.convert("RGB")).max() == 120

    def test_large_raster_is_resampled(self, make, write):
        data = np.full((3, 3000, 3000), 90, "uint8")
        img = self._image(make, {"r": write(data)})
        assert max(img.size) <= 2 * 900

    def test_other_crs_warns_and_is_skipped(self, make, write):
        data = np.full((3, 20, 20), 90, "uint8")
        path = write(data, crs="EPSG:4326", bounds=(-5, 41, 10, 51))
        with pytest.warns(UserWarning, match="not reprojected"):
            assert self._image(make, {"r": path}) is None

    def test_single_path_and_missing_file(self, make, write, tmp_path):
        from mappyng import Raster
        assert self._image(make, write(np.full((3, 20, 20), 90, "uint8")))
        m = make()
        m.add(Raster(paths=str(tmp_path / "missing.tif")))
        with pytest.raises(FileNotFoundError, match="does not exist"):
            m.to_string()
