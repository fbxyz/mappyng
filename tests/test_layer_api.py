"""Tests for the Map first-class Layer API: add/remove/layers (TICKET_72)."""

import pytest

from mappyng import Map
from mappyng.layers import Basemap, Choropleth

CHORO = {"column": "fid", "method": "Quantiles", "num_classes": 5}


# ---------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------

def test_add_assigns_layer_id(gdf_departments):
    m = Map(gdf_departments)
    layer = Choropleth(gdf_departments, **CHORO)
    m.add(layer)
    assert layer.id == "choropleth-1"


def test_add_assigns_sequential_ids_per_kind(gdf_departments):
    m = Map(gdf_departments)
    a = Basemap()
    m.add(a)
    b = Choropleth(gdf_departments, **CHORO)
    m.add(b)
    c = Choropleth(gdf_departments, column="fid")
    m.add(c)
    assert (a.id, b.id, c.id) == ("basemap-1", "choropleth-1", "choropleth-2")


def test_layers_property_is_ordered_copy(gdf_departments):
    m = Map(gdf_departments)
    a = Basemap()
    m.add(a)
    b = Choropleth(gdf_departments, **CHORO)
    m.add(b)
    assert m.layers == [a, b]
    m.layers.append("tampered")          # mutating the copy
    assert m.layers == [a, b]            # internal state intact


def test_get_layer(gdf_departments):
    m = Map(gdf_departments)
    layer = Choropleth(gdf_departments, **CHORO)
    m.add(layer)
    assert m.get_layer("choropleth-1") is layer


def test_get_layer_missing(gdf_departments):
    m = Map(gdf_departments)
    with pytest.raises(KeyError, match="No layer with id"):
        m.get_layer("ghost-9")


def test_add_rejects_non_layer(gdf_departments):
    m = Map(gdf_departments)
    with pytest.raises(TypeError, match="expects a layer or a map element"):
        m.add({"column": "fid"})


# ---------------------------------------------------------------------
# Removal
# ---------------------------------------------------------------------

def test_remove_by_object(gdf_departments):
    m = Map(gdf_departments)
    a = Basemap()
    m.add(a)
    b = Choropleth(gdf_departments, **CHORO)
    m.add(b)
    m.remove(a)
    assert m.layers == [b]


def test_remove_by_id(gdf_departments):
    m = Map(gdf_departments)
    m.add(Basemap())
    b = Choropleth(gdf_departments, **CHORO)
    m.add(b)
    m.remove("basemap-1")
    assert m.layers == [b]


def test_remove_missing(gdf_departments):
    m = Map(gdf_departments)
    with pytest.raises(KeyError, match="No layer matching"):
        m.remove("nope-1")


# ---------------------------------------------------------------------
# Deferred rendering and lifecycle
# ---------------------------------------------------------------------

def test_deferred_render_produces_svg(gdf_departments):
    m = Map(gdf_departments)
    m.add(Choropleth(gdf_departments, **CHORO))
    svg = m.to_string()
    assert svg.startswith("<?xml")
    assert "choro" in svg


def test_z_index_ordering_is_insertion_independent(gdf_departments):
    """z_index, not insertion order, drives the render order."""
    in_order = Map(gdf_departments)
    in_order.add(Basemap(z_index=0))
    in_order.add(Choropleth(gdf_departments, z_index=1, **CHORO))

    out_of_order = Map(gdf_departments)
    out_of_order.add(Choropleth(gdf_departments, z_index=1, **CHORO))
    out_of_order.add(Basemap(z_index=0))

    assert out_of_order.to_string() == in_order.to_string()


def test_invisible_layer_not_rendered(gdf_departments):
    plain = Map(gdf_departments)
    plain.add(Basemap())

    m = Map(gdf_departments)
    m.add(Basemap())
    m.add(Choropleth(gdf_departments, visible=False, **CHORO))

    assert m.to_string() == plain.to_string()


def test_add_after_build_raises(gdf_departments):
    m = Map(gdf_departments)
    m.add(Choropleth(gdf_departments, **CHORO))
    m.to_string()                         # triggers build
    with pytest.raises(RuntimeError, match="already been built"):
        m.add(Basemap())


def test_remove_after_build_raises(gdf_departments):
    m = Map(gdf_departments)
    m.add(Choropleth(gdf_departments, **CHORO))
    m.to_string()
    with pytest.raises(RuntimeError, match="already been built"):
        m.remove("choropleth-1")


def test_build_is_idempotent_no_double_render(gdf_departments):
    m = Map(gdf_departments)
    m.add(Choropleth(gdf_departments, **CHORO))
    first = m.to_string()
    second = m.to_string()               # second build is a no-op
    assert first == second


# ---------------------------------------------------------------------
# Chrome convenience methods
# ---------------------------------------------------------------------

def test_title_renders(gdf_departments):
    m = Map(gdf_departments)
    m.title("Population")
    assert "Population" in m.to_string()


def test_source_renders(gdf_departments):
    m = Map(gdf_departments)
    m.source("INSEE 2024")
    assert "INSEE 2024" in m.to_string()


def test_north_arrow_renders(gdf_departments):
    m = Map(gdf_departments)
    m.north_arrow()
    # Renders without error and produces SVG.
    assert m.to_string().startswith("<?xml")


def test_full_object_workflow(gdf_departments):
    """A complete v1.0-style map composes and renders without error."""
    m = Map(gdf_departments)
    m.add(Basemap())
    m.add(Choropleth(gdf_departments, **CHORO))
    m.title("Carte de test")
    m.source("Source de test")
    svg = m.to_string()
    assert svg.startswith("<?xml")
    assert len(m.layers) == 2


# ---------------------------------------------------------------------
# Dynamic canvas, width/height="auto" + autosize() (TICKET_77/78)
# ---------------------------------------------------------------------

def _content_aspect(m):
    """SVG aspect ratio of the fitted content area (height / width)."""
    m._build()
    vb = m.main.viewbox
    return vb.content_height / vb.content_width


def _data_aspect(gdf):
    b = gdf.total_bounds
    return (b[3] - b[1]) / (b[2] - b[0])


def test_numeric_dimensions_unchanged(gdf_departments):
    """Explicit numeric sizes are passed through untouched (byte fidelity)."""
    m = Map(gdf_departments, width=800, height=600)
    assert m.width == 800 and m.height == 600
    assert 'viewBox="0 0 800 600"' in m.to_string()


def test_height_auto_matches_data_aspect(gdf_departments):
    """height="auto" snaps the content area to the data aspect ratio."""
    m = Map(gdf_departments, width=800, height="auto")
    assert m.width == 800
    assert m.height != 600
    assert _content_aspect(m) == pytest.approx(_data_aspect(gdf_departments), rel=1e-3)


def test_height_auto_removes_vertical_letterbox(gdf_departments):
    """With height="auto" the content fills the viewport draw area vertically:
    the aspect-ratio centring gap is ~0 (no white letterbox top/bottom)."""
    m = Map(gdf_departments, width=800, height="auto")
    m._build()
    vb = m.main.viewbox
    # content_y sits exactly at the viewport top + padding (no centring offset).
    assert vb.content_y == pytest.approx(vb.svg_y + vb.padding, abs=0.5)


def test_width_auto_keeps_height(gdf_departments):
    """width="auto" keeps the given height and derives the width."""
    m = Map(gdf_departments, width="auto", height=400)
    assert m.height == 400
    assert _content_aspect(m) == pytest.approx(_data_aspect(gdf_departments), rel=1e-3)


def test_both_auto_uses_default_width(gdf_departments):
    m = Map(gdf_departments, width="auto", height="auto")
    assert m.width == 800
    assert _content_aspect(m) == pytest.approx(_data_aspect(gdf_departments), rel=1e-3)


def test_autosize_returns_self_and_snaps(gdf_departments):
    m = Map(gdf_departments, width=800, height=600)
    out = m.autosize()
    assert out is m
    assert m.width == 800 and m.height != 600
    assert _content_aspect(m) == pytest.approx(_data_aspect(gdf_departments), rel=1e-3)


def test_autosize_after_build_raises(gdf_departments):
    from mappyng.layers import LayerStateError
    m = Map(gdf_departments)
    m.add(Basemap())
    m._build()
    with pytest.raises(LayerStateError):
        m.autosize()


def test_autosize_before_add_preserves_layers(gdf_departments):
    """autosize() before adding layers keeps a working render pipeline."""
    m = Map(gdf_departments, width=800).autosize()
    m.add(Choropleth(gdf_departments, **CHORO))
    svg = m.to_string()
    assert svg.startswith("<?xml")
    assert len(m.layers) == 1


def _svg(m, path):
    m.render(str(path))
    return path.read_text()


def _hide_legend_map():
    import geopandas as gpd
    from shapely.geometry import box

    from mappyng import Choropleth, Map
    gdf = gpd.GeoDataFrame({"v": [1, 2, 3, 4]},
                           geometry=[box(i, 0, i + 1, 1) for i in range(4)],
                           crs=4326)
    return gdf, Map, Choropleth


def test_choropleth_legend_false_hides_legend(tmp_path):
    gdf, Map, Choropleth = _hide_legend_map()
    shown = _svg(Map(gdf).add(Choropleth(gdf, column="v")), tmp_path / "a.svg")
    hidden = _svg(Map(gdf).add(Choropleth(gdf, column="v", legend=False)), tmp_path / "b.svg")
    assert "legend" in shown
    assert "legend" not in hidden


def test_vector_positive_z_index_draws_above_choropleth(tmp_path):
    gdf, Map, Choropleth = _hide_legend_map()
    from mappyng import Vector
    m = Map(gdf).add(Choropleth(gdf, column="v"), Vector(gdf, z_index=5))
    svg = _svg(m, tmp_path / "c.svg")
    assert svg.index("layer_top") > svg.index("choropleth")


def test_choropleth_report_records_classes_and_exclusions(tmp_path):

    import numpy as np

    import mappyng as mp
    from mappyng.data import load_france_departments

    gdf = load_france_departments()
    gdf = gdf[gdf["COD_GEO"].str.len() == 2].copy()
    gdf["v"] = np.arange(len(gdf), dtype=float)
    gdf.loc[gdf.index[:3], "v"] = np.nan
    lyr = mp.Choropleth(gdf, column="v", method="Quantiles", num_classes=5)
    m = mp.Map(gdf, width=400, height="auto") + lyr
    m.render(str(tmp_path / "m.svg"))
    rep = lyr.report
    assert rep is m.classification_reports[next(iter(m.classification_reports))]
    assert rep.n_excluded == 3
    assert rep.n_valid == len(gdf) - 3
    assert sum(rep.counts) == rep.n_valid
    assert rep.applied_classes == 5 and len(rep.bins) == 6
    assert rep.adjustments == []
    assert list(rep.to_dataframe()["count"]) == rep.counts
    assert "Quantiles" in str(rep)


def test_choropleth_report_records_stdmean_snap(tmp_path):
    import numpy as np
    import pytest

    import mappyng as mp
    from mappyng.data import load_france_departments

    gdf = load_france_departments()
    gdf = gdf[gdf["COD_GEO"].str.len() == 2].copy()
    gdf["v"] = np.random.default_rng(0).normal(size=len(gdf))
    lyr = mp.Choropleth(gdf, column="v", method="StdMean", num_classes=4,
                        cmap="RdBu")
    m = mp.Map(gdf, width=400, height="auto") + lyr
    with pytest.warns(UserWarning):
        m.render(str(tmp_path / "m.svg"))
    assert lyr.report.requested_classes == 4
    assert lyr.report.applied_classes in (5, 7)
    assert any("snapped" in a for a in lyr.report.adjustments)


def test_category_report_counts(tmp_path):
    import mappyng as mp
    from mappyng.data import load_france_departments

    gdf = load_france_departments()
    gdf = gdf[gdf["COD_GEO"].str.len() == 2].copy()
    gdf["g"] = ["a" if i % 2 else "b" for i in range(len(gdf))]
    gdf.loc[gdf.index[:2], "g"] = None
    lyr = mp.Category(gdf, column="g", fill_map={"a": "#111111", "b": "#eeeeee"})
    m = mp.Map(gdf, width=400, height="auto") + lyr
    m.render(str(tmp_path / "m.svg"))
    assert lyr.report.n_excluded == 2
    assert sum(lyr.report.counts) == len(gdf) - 2
    assert lyr.report.categories == ["a", "b"]


def test_map_recipe_is_deterministic_and_written(tmp_path):
    import json

    import mappyng as mp
    from mappyng.data import load_france_departments

    gdf = load_france_departments()
    gdf = gdf[gdf["COD_GEO"].str.len() == 2].copy()
    gdf["v"] = range(len(gdf))
    m = mp.Map(gdf, width=400, height="auto") + mp.Choropleth(gdf, column="v")
    m.render(str(tmp_path / "m.svg"))
    r1 = m.recipe(str(tmp_path / "r.json"))
    r2 = m.recipe()
    assert r1 == r2 == json.loads((tmp_path / "r.json").read_text())
    assert r1["mappyng_version"] == mp.__version__
    assert r1["seed"] == 42
    assert len(r1["data"]["main"]["sha256"]) == 64
    assert r1["data"]["layers"][0]["rows"] == len(gdf)
    assert r1["classification"]
    gdf2 = gdf.copy()
    gdf2.loc[gdf2.index[0], "v"] = 999
    m2 = mp.Map(gdf2, width=400, height="auto") + mp.Choropleth(gdf2, column="v")
    assert m2.recipe()["data"]["layers"][0]["sha256"] != r1["data"]["layers"][0]["sha256"]


def test_choropleth_report_traces_palette(tmp_path):
    import mappyng as mp
    from mappyng.config import COLORMAP_DEFS
    from mappyng.data import load_france_departments

    gdf = load_france_departments()
    gdf = gdf[gdf["COD_GEO"].str.len() == 2].copy()
    gdf["v"] = range(len(gdf))
    lyr = mp.Choropleth(gdf, column="v", cmap="Blues", num_classes=5,
                        reverse=True)
    m = mp.Map(gdf, width=400, height="auto") + lyr
    m.render(str(tmp_path / "m.svg"))
    assert lyr.report.cmap == "Blues"
    assert lyr.report.colors == list(reversed(COLORMAP_DEFS["Blues"][5]))
    assert lyr.report.adjustments == []
    assert list(lyr.report.to_dataframe()["color"]) == lyr.report.colors


def test_palette_adjustment_explains_truncation():
    from mappyng.choropleth_classify import palette_adjustment
    from mappyng.config import COLORMAP_DEFS

    full = COLORMAP_DEFS["Blues"]
    n = min(full)
    assert palette_adjustment("Blues", full[n]) is None
    assert palette_adjustment("Blues", full[max(full)][:n - 1 or 1]) is not None
    assert palette_adjustment(["#000000"], ["#000000"]) is None


def test_recipe_contract_before_render_and_data_scope(tmp_path):
    import mappyng as mp
    from mappyng.data import load_france_departments

    gdf = load_france_departments()
    gdf = gdf[gdf["COD_GEO"].str.len() == 2].copy()
    gdf["v"] = range(len(gdf))
    m = mp.Map(gdf, width=300, height="auto") + mp.Choropleth(gdf, column="v")
    assert m.recipe()["classification"] == {}
    m.render(str(tmp_path / "a.svg"))
    assert m.recipe()["classification"]
    derived = m + mp.Title("x")
    assert derived.recipe()["classification"] == {}
    # the hash covers every attribute, not only the mapped column
    other = gdf.copy()
    other["note"] = "x"
    m2 = mp.Map(other, width=300, height="auto") + mp.Choropleth(other, column="v")
    h = lambda r: r["data"]["layers"][0]["sha256"]  # noqa: E731
    assert h(m2.recipe()) != h(m.recipe())
    # the CRS is part of the fingerprint
    reproj = gdf.to_crs(2154)
    m3 = mp.Map(reproj, width=300, height="auto") + mp.Choropleth(reproj, column="v")
    assert h(m3.recipe()) != h(m.recipe())
