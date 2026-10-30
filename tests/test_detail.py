"""Tests for finer zoom/cartouche geometry (``detail``) keeping the symbology."""

import xml.etree.ElementTree as ET

import numpy as np
import pytest

from mappyng import Inset, Insets, Map, Zoom
from mappyng.detail import CARTOUCHES, ZOOM, detail_for, join_detail, normalize_detail
from mappyng.layers import (
    Basemap,
    Category,
    Choropleth,
    Label,
    Proportional,
    Situation,
    Vector,
)

SVG = "{http://www.w3.org/2000/svg}"
BBOX = [90000, 6040000, 1280000, 7150000]
PARIS = [600000, 6820000, 700000, 6900000]
CORSE = [1150000, 6040000, 1250000, 6200000]
KEY = "COD_GEO"


@pytest.fixture(scope="module")
def fine(gdf_departments_module):
    g = gdf_departments_module.copy()
    g["v"] = np.linspace(0, 1, len(g))
    g["cat"] = [("A", "B", "C")[i % 3] for i in range(len(g))]
    return g


@pytest.fixture(scope="module")
def gdf_departments_module():
    from mappyng.data import load_france_departments
    return load_france_departments().to_crs(2154)


@pytest.fixture(scope="module")
def general(fine):
    """Over-generalised copy of ``fine``: same rows and columns."""
    g = fine.copy()
    g["geometry"] = g.geometry.simplify(20000)
    return g


def _map(general, *, zoom=True, insets=False):
    m = Map(general, bbox=BBOX, width=900, height=800)
    m.add(Basemap())
    if zoom:
        m.add(Zoom(PARIS, x=560, y=80, width=300, height=240))
    if insets:
        m.add(Insets([Inset("Corse", bbox=CORSE, crs=2154),
                      Inset("Paris", bbox=PARIS, crs=2154)], spacing=10))
    return m


def _fills_by_id(svg):
    """{element id: set of fills} over the choropleth paths of every viewport."""
    out = {}
    for el in ET.fromstring(svg).iter(SVG + "path"):
        eid = el.get("id") or ""
        if eid.startswith("choro-"):
            out.setdefault(eid, set()).add(el.get("fill"))
    return out


def _path_data(svg, prefix="choro-"):
    return [el.get("d") for el in ET.fromstring(svg).iter(SVG + "path")
            if (el.get("id") or "").startswith(prefix)]


class TestNormalize:
    def test_none(self):
        assert normalize_detail(None) == {}

    def test_single_frame_applies_to_zoom_and_cartouches(self, fine):
        d = normalize_detail(fine)
        assert set(d) == {ZOOM, CARTOUCHES}

    def test_dict(self, fine):
        d = normalize_detail({"zoom": fine, 1: fine})
        assert set(d) == {"zoom", 1}

    @pytest.mark.parametrize("bad", [
        {"main": None}, {"zoom": "x"}, 3, "frame", {True: None},
    ])
    def test_invalid(self, bad):
        with pytest.raises(ValueError):
            normalize_detail(bad)

    def test_cartouche_index_beats_cartouches(self, fine, general):
        d = normalize_detail({CARTOUCHES: general, 1: fine})
        assert detail_for(d, 0) is general
        assert detail_for(d, 1) is fine
        assert detail_for(d, ZOOM) is None


class TestJoinDetail:
    def test_symbology_follows_the_key(self, fine, general):
        frame = general.copy()
        frame["_class"] = range(len(frame))
        out = join_detail(frame, fine, KEY)
        assert len(out) == len(frame)
        assert (out["_class"].to_numpy() == frame["_class"].to_numpy()).all()
        # geometry comes from the finer layer
        assert out.geometry.iloc[0].equals(fine.geometry.iloc[0])
        assert out.crs == frame.crs

    def test_index_is_kept(self, fine, general):
        frame = general.copy()
        frame.index = [f"u{i}" for i in range(len(frame))]
        out = join_detail(frame, fine, KEY)
        assert set(out.index) == set(frame.index)

    def test_join_on_index(self, fine, general):
        out = join_detail(general.assign(_class=1), fine, None)
        assert len(out) == len(general)

    def test_pair_of_columns(self, fine, general):
        f = fine.rename(columns={KEY: "code"})
        out = join_detail(general.assign(_class=1), f, (KEY, "code"))
        assert len(out) == len(general)

    def test_other_crs_is_reprojected(self, fine, general):
        out = join_detail(general.assign(_class=1), fine.to_crs(4326), KEY)
        assert out.crs == general.crs
        assert out.geometry.iloc[0].area == pytest.approx(
            fine.geometry.iloc[0].area, rel=1e-3)

    def test_several_finer_rows_per_key(self, fine, general):
        parts = fine.explode(index_parts=False)
        out = join_detail(general.assign(_class=1), parts, KEY)
        assert len(out) == len(parts)

    def test_missing_finer_geometry_warns(self, fine, general):
        with pytest.warns(UserWarning, match="no geometry in the finer layer"):
            out = join_detail(general.assign(_class=1), fine.iloc[5:], KEY)
        assert len(out) == len(general) - 5

    def test_unknown_column(self, fine, general):
        with pytest.raises(ValueError, match="not in the"):
            join_detail(general.assign(_class=1), fine, "nope")

    def test_duplicate_keys(self, fine, general):
        frame = general.assign(_class=1)
        frame[KEY] = "same"
        with pytest.raises(ValueError, match="duplicates"):
            join_detail(frame, fine, KEY)

    def test_empty_frame(self, fine, general):
        empty = general.iloc[:0]
        assert join_detail(empty, fine, KEY).empty


class TestChoropleth:
    def _svg(self, general, fine, **kw):
        m = _map(general, insets=kw.pop("insets", False))
        m.add(Choropleth(general, column="v", method="Quantiles", **kw))
        return m.to_string()

    def test_colours_are_unchanged_and_zoom_geometry_is_finer(self, fine, general):
        plain = self._svg(general, fine)
        finer = self._svg(general, fine, detail=fine, detail_join=KEY)
        # same symbology: every area keeps one colour everywhere it is drawn
        for svg in (plain, finer):
            assert all(len(v) == 1 for v in _fills_by_id(svg).values())
        assert _fills_by_id(plain) == _fills_by_id(finer)
        # ... but the zoom is drawn from other, finer, outlines
        assert set(_path_data(plain)) != set(_path_data(finer))

    def test_main_map_is_untouched(self, fine, general):
        """With no zoom and no cartouche, detail has nothing to change."""
        def svg(**kw):
            m = Map(general, bbox=BBOX, width=900, height=800)
            m.add(Basemap())
            m.add(Choropleth(general, column="v", method="Quantiles", **kw))
            return m.to_string()
        assert svg() == svg(detail=fine, detail_join=KEY)

    def test_without_detail_output_is_identical(self, fine, general):
        assert self._svg(general, fine) == self._svg(
            general, fine, detail=None)

    def test_dissolve_applies_to_the_finer_geometry(self, fine, general):
        svg = self._svg(general, fine, dissolve=True, detail=fine,
                        detail_join=KEY)
        assert _path_data(svg)

    def test_nodata_follows(self, fine, general):
        g = general.copy()
        g.loc[g.index[:5], "v"] = np.nan
        m = _map(g)
        m.add(Choropleth(g, column="v", method="Quantiles",
                         detail=fine, detail_join=KEY))
        assert "hatch" in m.to_string()

    def test_cartouche_targets(self, fine, general):
        def paths(detail):
            m = _map(general, zoom=False, insets=True)
            m.add(Choropleth(general, column="v", method="Quantiles",
                             detail=detail, detail_join=KEY))
            return set(_path_data(m.to_string()))
        none, first, second, every = (
            paths(None), paths({0: fine}), paths({1: fine}), paths(fine))
        assert len({frozenset(x) for x in (none, first, second, every)}) == 4

    def test_detail_for_zoom_only_leaves_cartouches(self, fine, general):
        zoom_only = self._svg(general, fine, insets=True,
                              detail={"zoom": fine}, detail_join=KEY)
        both = self._svg(general, fine, insets=True,
                         detail=fine, detail_join=KEY)
        assert set(_path_data(zoom_only)) != set(_path_data(both))

    def test_bad_join_column_fails_clearly(self, fine, general):
        m = _map(general)
        m.add(Choropleth(general, column="v", detail=fine, detail_join="nope"))
        with pytest.raises(ValueError, match="nope"):
            m.to_string()

    def test_yaml_export_refuses_a_frame(self, fine, general):
        m = _map(general)
        m.add(Choropleth(general, column="v", detail=fine, detail_join=KEY))
        with pytest.raises(TypeError, match="GeoDataFrame"):
            m.to_yaml()


class TestCategory:
    def test_colours_follow(self, fine, general):
        fill = {"A": "#e41a1c", "B": "#377eb8", "C": "#4daf4a"}
        m = _map(general)
        m.add(Category(general, column="cat", fill_map=fill,
                       detail=fine, detail_join=KEY))
        fills = _fills_by_id(m.to_string())
        assert fills and all(len(v) == 1 for v in fills.values())

    def test_dissolve(self, fine, general):
        fill = {"A": "#e41a1c", "B": "#377eb8", "C": "#4daf4a"}
        m = _map(general)
        m.add(Category(general, column="cat", fill_map=fill, dissolve=True,
                       detail=fine, detail_join=KEY))
        assert _path_data(m.to_string())


class TestBasemapAndVector:
    def test_basemap_detail_changes_zoom_outlines(self, fine, general):
        def basemap_paths(detail):
            m = Map(general, bbox=BBOX, width=900, height=800)
            m.add(Basemap(detail=detail) if detail is not None else Basemap())
            m.add(Zoom(PARIS, x=560, y=80, width=300, height=240))
            root = ET.fromstring(m.to_string())
            return [p.get("d") for p in root.iter(SVG + "path")]
        assert set(basemap_paths(None)) != set(basemap_paths(fine))

    def test_vector_detail(self, fine, general):
        def paths(detail):
            m = _map(general)
            kw = {"detail": detail} if detail is not None else {}
            m.add(Vector(general, stroke="#000", on_zoom=True, **kw))
            root = ET.fromstring(m.to_string())
            return [p.get("d") for p in root.iter(SVG + "path")]
        assert set(paths(None)) != set(paths(fine))

    def test_detail_in_another_crs(self, fine, general):
        def paths(detail):
            m = Map(general, bbox=BBOX, width=900, height=800)
            m.add(Basemap(detail=detail))
            m.add(Zoom(PARIS, x=560, y=80, width=300, height=240))
            root = ET.fromstring(m.to_string())
            return len([p for p in root.iter(SVG + "path")])
        assert paths(fine.to_crs(4326)) == paths(fine)


class TestProportional:
    def _svg(self, general, **kw):
        g = general.assign(pop=np.linspace(1e3, 1e6, len(general)))
        m = _map(general, insets=True)
        m.add(Proportional(g, column="pop", **kw))
        return m.to_string()

    @staticmethod
    def _circles(svg):
        return [(c.get("id"), c.get("cx"), c.get("cy"), c.get("r"),
                 c.get("fill"))
                for c in ET.fromstring(svg).iter(SVG + "circle")
                if (c.get("id") or "").startswith("prop-")]

    def test_same_geometry_gives_identical_output(self, general):
        assert self._svg(general) == self._svg(
            general, detail=general, detail_join=KEY)

    def test_centres_come_from_the_finer_geometry(self, fine, general):
        # a fixed reference keeps radii comparable between the two renders
        fixed = dict(reference_value=1e6, reference_radius=30)
        plain = self._circles(self._svg(general, **fixed))
        finer = self._circles(self._svg(general, detail=fine,
                                        detail_join=KEY, **fixed))
        # A finer outline can move a centre into or out of a window, so the
        # set of circles may differ at the edges; every circle they share keeps
        # its radius and colour ...
        def by_id(cs):
            return {i: (r, f) for i, _, _, r, f in cs}

        shared = set(by_id(plain)) & set(by_id(finer))
        assert shared
        assert all(by_id(plain)[i] == by_id(finer)[i] for i in shared)
        # ... only the centres move
        assert {(cx, cy) for _, cx, cy, _, _ in plain} != \
            {(cx, cy) for _, cx, cy, _, _ in finer}

    def test_fill_map_survives_the_join(self, fine, general):
        fill = {"A": "#e41a1c", "B": "#377eb8", "C": "#4daf4a"}
        svg = self._svg(general, fill_column="cat", fill_map=fill,
                        detail=fine, detail_join=KEY)
        assert {f for *_, f in self._circles(svg)} <= set(fill.values())

    def test_points_with_polygon_detail(self, fine, general):
        pts = general.copy()
        pts["geometry"] = pts.geometry.centroid
        pts["pop"] = np.linspace(1e3, 1e6, len(pts))
        m = _map(general)
        m.add(Proportional(pts, column="pop", detail=fine, detail_join=KEY))
        assert self._circles(m.to_string())


class TestSituation:
    def _svg(self, general, **kw):
        m = _map(general, insets=True)
        m.add(Situation(general, column="cat", symbol={
            "A": {"marker": "circle", "fill": "#e41a1c"},
            "B": {"marker": "square", "fill": "#377eb8"},
            "C": {"marker": "circle", "fill": "#4daf4a"},
        }, **kw))
        return m.to_string()

    def test_same_geometry_gives_identical_output(self, general):
        assert self._svg(general) == self._svg(
            general, detail=general, detail_join=KEY)

    def test_markers_move_with_the_finer_geometry(self, fine, general):
        assert self._svg(general) != self._svg(
            general, detail=fine, detail_join=KEY)

    def test_unknown_key_fails_clearly(self, fine, general):
        m = _map(general)
        m.add(Situation(general, marker="circle", detail=fine,
                        detail_join="nope"))
        with pytest.raises(ValueError, match="nope"):
            m.to_string()


class TestLabels:
    def _svg(self, general, *, target="zoom", insets=True, **kw):
        m = _map(general, insets=insets)
        m.add(Label(general, column="LIB_GEO", target=target, **kw))
        return m.to_string()

    @staticmethod
    def _label_texts(svg, names):
        return [t for t in ET.fromstring(svg).iter(SVG + "text")
                if t.text in names]

    def test_same_geometry_gives_identical_output(self, general):
        assert self._svg(general) == self._svg(
            general, detail=general, detail_join=KEY)

    def test_zoom_labels_follow_the_finer_geometry(self, fine, general):
        assert self._svg(general) != self._svg(
            general, detail=fine, detail_join=KEY)

    def test_cartouche_target(self, fine, general):
        plain = self._svg(general, target="cartouche:1")
        finer = self._svg(general, target="cartouche:1", detail={1: fine},
                          detail_join=KEY)
        assert plain != finer
        # a detail for another target does not touch this one
        other = self._svg(general, target="cartouche:1", detail={0: fine},
                          detail_join=KEY)
        assert other == plain

    def test_main_map_labels_ignore_detail(self, fine, general):
        assert self._svg(general, target="main", insets=False) == self._svg(
            general, target="main", insets=False, detail=fine,
            detail_join=KEY)

    def test_text_comes_from_the_layer_data(self, fine, general):
        names = set(general["LIB_GEO"])
        svg = self._svg(general, detail=fine, detail_join=KEY)
        assert {t.text for t in self._label_texts(svg, names)} <= names

    def test_a_unit_in_several_parts_is_labelled_once(self, fine, general):
        parts = fine.explode(index_parts=False)
        assert len(parts) > len(fine)
        names = set(general["LIB_GEO"])
        whole = self._label_texts(
            self._svg(general, detail=fine, detail_join=KEY), names)
        split = self._label_texts(
            self._svg(general, detail=parts, detail_join=KEY), names)
        # a label is two <text> elements (halo + fill); splitting the finer
        # layer into parts must not add labels
        def per_name(texts):
            counts = {}
            for t in texts:
                counts[t.text] = counts.get(t.text, 0) + 1
            return counts
        assert max(per_name(split).values()) == max(per_name(whole).values())

    def test_unknown_join_column_fails_clearly(self, fine, general):
        m = _map(general)
        m.add(Label(general, column="LIB_GEO", target="zoom", detail=fine,
                    detail_join="nope"))
        with pytest.raises(ValueError, match="nope"):
            m.to_string()


class TestKeyTypes:
    def test_text_key_against_numeric_key_is_explained(self, fine, general):
        coarse = general.assign(_class=1, num=range(len(general)))
        finer = fine.assign(txt=[str(i) for i in range(len(fine))])
        with pytest.raises(ValueError, match="same type"):
            join_detail(coarse, finer, ("num", "txt"))

    def test_int_key_against_float_key_matches(self, fine, general):
        coarse = general.assign(_class=1, num=range(len(general)))
        finer = fine.assign(flt=[float(i) for i in range(len(fine))])
        assert len(join_detail(coarse, finer, ("num", "flt"))) == len(general)
