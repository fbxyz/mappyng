"""Tests for map composition: elements, the + operator and chained add."""


import pytest

import mappyng as mp
from mappyng.layers import Layer

GUADELOUPE = [-6890454, 1780151, -6799589, 1874186]
MARTINIQUE = [-6826862, 1609607, -6759494, 1685367]
CHORO = {"column": "fid", "method": "Quantiles", "num_classes": 5}


def _cartouche_params():
    return {
        0: {"bbox": GUADELOUPE, "crs": 3857, "cartouche_title": "Guadeloupe",
            "cartouche_title_size": 7, "border_radius": 6},
        1: {"bbox": MARTINIQUE, "crs": 3857, "cartouche_title": "Martinique",
            "cartouche_title_size": 7, "border_radius": 6},
    }


def _insets():
    return mp.Insets(
        [mp.Inset("Guadeloupe", bbox=GUADELOUPE, crs=3857),
         mp.Inset("Martinique", bbox=MARTINIQUE, crs=3857)],
        title_size=7, border_radius=6,
    )


# ---------------------------------------------------------------------
# + and add
# ---------------------------------------------------------------------

def test_plus_returns_new_map_and_keeps_base(gdf_departments):
    base = mp.Map(gdf_departments) + mp.Basemap()
    m = base + mp.Choropleth(gdf_departments, **CHORO)
    assert m is not base
    assert len(base.layers) == 1
    assert len(m.layers) == 2


def test_plus_accepts_list(gdf_departments):
    m = mp.Map(gdf_departments) + [mp.Basemap(), mp.Title("T")]
    assert len(m.layers) == 1
    assert m._state.chrome["title"]["text"] == "T"


def test_derived_maps_render_independently(gdf_departments):
    base = mp.Map(gdf_departments) + mp.Basemap() + mp.Source("S")
    a = base + mp.Title("First")
    b = base + mp.Title("Second")
    svg_a, svg_b = a.to_string(), b.to_string()
    assert "First" in svg_a and "Second" not in svg_a
    assert "Second" in svg_b and "First" not in svg_b
    # Rendering the derived maps leaves the base unrendered.
    assert not any(lyr._rendered for lyr in base.layers)
    assert "First" not in base.to_string()


def test_plus_on_built_map(gdf_departments):
    base = mp.Map(gdf_departments) + mp.Basemap()
    base.to_string()
    m = base + mp.Title("After")
    assert "After" in m.to_string()


def test_plus_rejects_other_types(gdf_departments):
    with pytest.raises(TypeError):
        mp.Map(gdf_departments) + "title"


def test_add_returns_map_for_chaining(gdf_departments):
    m = mp.Map(gdf_departments)
    assert m.add(mp.Basemap()).add(mp.Title("T")) is m
    assert len(m.layers) == 1


def test_add_several_items(gdf_departments):
    m = mp.Map(gdf_departments)
    m.add(mp.Basemap(), mp.Choropleth(gdf_departments, **CHORO),
          mp.ScaleBar())
    assert [lyr.id for lyr in m.layers] == ["basemap-1", "choropleth-1"]
    assert "scale_bar" in m._state.chrome


def test_plus_and_add_produce_same_svg(gdf_departments):
    plus = (mp.Map(gdf_departments) + mp.Basemap()
            + mp.Choropleth(gdf_departments, **CHORO)
            + mp.Title("T", subtitle="S") + mp.ScaleBar() + mp.Source("Src"))
    chained = (mp.Map(gdf_departments).add(mp.Basemap())
               .add(mp.Choropleth(gdf_departments, **CHORO))
               .add(mp.Title("T", subtitle="S")).add(mp.ScaleBar())
               .add(mp.Source("Src")))
    legacy = mp.Map(gdf_departments)
    legacy.add(mp.Basemap())
    legacy.add(mp.Choropleth(gdf_departments, **CHORO))
    legacy.title("T", subtitle="S")
    legacy.scale_bar()
    legacy.source("Src")
    assert plus.to_string() == chained.to_string() == legacy.to_string()


def test_copy_resets_layers(gdf_departments):
    m = mp.Map(gdf_departments) + mp.Basemap()
    m.to_string()
    c = m.copy()
    assert c.layers[0] is not m.layers[0]
    assert not c.layers[0]._rendered
    assert c.to_string() == m.to_string()


def test_layer_copy_shares_data(gdf_departments):
    layer = mp.Choropleth(gdf_departments, **CHORO)
    layer.id = "choropleth-1"
    c = layer.copy()
    assert c.gdf is layer.gdf
    assert c.params == layer.params and c.params is not layer.params
    assert c.id is None


# ---------------------------------------------------------------------
# Chrome
# ---------------------------------------------------------------------

def test_chrome_is_drawn_at_build(gdf_departments):
    m = mp.Map(gdf_departments) + mp.Title("Late title")
    assert m._state.chrome_bboxes == []
    assert "Late title" in m.to_string()


def test_second_title_replaces_first(gdf_departments):
    m = mp.Map(gdf_departments) + mp.Title("Old") + mp.Title("New")
    svg = m.to_string()
    assert "New" in svg and "Old" not in svg


def test_position_tuple_is_converted():
    assert mp.ScaleBar(position=(0.4, 0.9)).params["position"] == \
        {"x": 0.4, "y": 0.9}
    assert mp.Source("S", position=[0.5, 1.05]).params["position"] == \
        {"x": 0.5, "y": 1.05}
    assert mp.NorthArrow(position={"x": 0.1, "y": 0.2}).params[
        "position"] == {"x": 0.1, "y": 0.2}


def test_unset_options_are_not_stored():
    assert mp.Title("T").params == {"text": "T"}
    assert mp.ScaleBar().params == {}


# ---------------------------------------------------------------------
# Legend
# ---------------------------------------------------------------------

def test_legend_is_stored_as_dict(gdf_departments):
    layer = mp.Choropleth(gdf_departments, **CHORO,
                          legend=mp.Legend("Rate", orientation="horizontal"))
    assert layer.params["legend"] == {"title": "Rate",
                                      "orientation": "horizontal"}


def test_legend_object_matches_dict(gdf_departments):
    obj = mp.Map(gdf_departments) + mp.Choropleth(
        gdf_departments, **CHORO, legend=mp.Legend("Rate", decimals=0))
    raw = mp.Map(gdf_departments) + mp.Choropleth(
        gdf_departments, **CHORO, legend={"title": "Rate", "decimals": 0})
    assert obj.to_string() == raw.to_string()


def test_legend_on_update(gdf_departments):
    layer = mp.Choropleth(gdf_departments, **CHORO)
    layer.update(legend=mp.Legend("Updated"))
    assert layer.params["legend"] == {"title": "Updated"}


# ---------------------------------------------------------------------
# Insets and zoom
# ---------------------------------------------------------------------

def test_insets_to_params():
    assert _insets().to_params() == {
        0: {"bbox": GUADELOUPE, "crs": 3857, "cartouche_title": "Guadeloupe",
            "cartouche_title_size": 7, "border_radius": 6},
        1: {"bbox": MARTINIQUE, "crs": 3857, "cartouche_title": "Martinique",
            "cartouche_title_size": 7, "border_radius": 6},
    }


def test_inset_option_overrides_shared_default():
    insets = mp.Insets([mp.Inset("A", bbox=GUADELOUPE, crs=3857, size=2)],
                       size=1.5)
    assert insets.to_params()[0]["size"] == 2


def test_insets_reject_unknown_option():
    with pytest.raises(TypeError, match="unexpected options"):
        mp.Insets([], colour="red")


def test_insets_match_cartouche_params(gdf_europe, gdf_departments,
                                       bbox_metro):
    kw = dict(bbox=bbox_metro, width=600, height=700)
    layers = [mp.Basemap(),
              mp.Choropleth(gdf_departments, **CHORO)]
    old = mp.Map(gdf_europe, cartouche_params=_cartouche_params(), **kw)
    old.add([lyr.copy() for lyr in layers])
    new = mp.Map(gdf_europe, **kw) + _insets() + layers
    assert new.to_string() == old.to_string()


def test_second_insets_is_rejected(gdf_europe, bbox_metro):
    m = mp.Map(gdf_europe, bbox=bbox_metro) + _insets()
    with pytest.raises(ValueError, match="already has cartouches"):
        m.add(_insets())


def test_vector_drawn_on_cartouches_by_default(gdf_europe, gdf_departments,
                                               bbox_metro):
    def n_paths(**kwargs):
        m = (mp.Map(gdf_europe, bbox=bbox_metro) + _insets()
             + mp.Vector(gdf_departments, stroke="#123456", **kwargs))
        return m.to_string().count('stroke="#123456"')

    assert n_paths() == n_paths(on_cartouches=True)
    assert n_paths() > n_paths(on_cartouches=False)


def test_zoom_matches_add_zoom(gdf_departments):
    params = {"bbox": [634000, 6841000, 674000, 6882000], "border_radius": 8}
    legacy = mp.Map(gdf_departments)
    vp = legacy.add_zoom(dict(params))
    assert vp is legacy.zoom_viewport
    legacy.add(mp.Basemap())
    new = (mp.Map(gdf_departments)
           + mp.Zoom(params["bbox"], border_radius=8) + mp.Basemap())
    assert new.to_string() == legacy.to_string()


def test_second_zoom_is_rejected(gdf_departments):
    m = mp.Map(gdf_departments) + mp.Zoom([0, 0, 1, 1])
    with pytest.raises(ValueError, match="zoom window"):
        m.add(mp.Zoom([0, 0, 1, 1]))


# ---------------------------------------------------------------------
# Drop shadow and gradients
# ---------------------------------------------------------------------

def test_drop_shadow_matches_add_shadow(gdf_europe, bbox_metro):
    legacy = mp.Map(gdf_europe, bbox=bbox_metro)
    legacy.add_shadow(gdf_europe, {"query": "code_pays_iso3=='FRA'",
                                   "stdDeviation": 5})
    new = mp.Map(gdf_europe, bbox=bbox_metro) + mp.DropShadow(
        gdf_europe, query="code_pays_iso3=='FRA'", blur=5)
    svg = new.to_string()
    assert svg == legacy.to_string()
    assert 'stdDeviation="5"' in svg


def test_radial_gradient_id_is_stable():
    stops = [(0.0, "#ffffff"), (1.0, "#000000")]
    a = mp.RadialGradient(stops, fx=0.3)
    b = mp.RadialGradient(stops, fx=0.3)
    c = mp.RadialGradient(stops, fx=0.4)
    assert a.gradient_id == b.gradient_id != c.gradient_id
    assert a.url == f"url(#{a.gradient_id})"
    assert mp.RadialGradient(stops, gradient_id="g").url == "url(#g)"


def test_radial_gradient_in_svg(gdf_departments):
    grad = mp.RadialGradient([(0.0, "#ffffff"), (1.0, "#000000")])
    m = (mp.Map(gdf_departments) + grad
         + mp.Vector(gdf_departments, fill=grad.url))
    svg = m.to_string()
    assert f'<radialGradient id="{grad.gradient_id}"' in svg
    assert f'fill="{grad.url}"' in svg


def test_add_radial_gradient_numbers_ids(gdf_departments):
    m = mp.Map(gdf_departments)
    assert m.add_radial_gradient([(0, "#fff"), (1, "#000")]) == \
        "url(#radial-1)"
    assert m.add_radial_gradient([(0, "#fff"), (1, "#000")]) == \
        "url(#radial-2)"
    assert 'id="radial-2"' in m.copy().to_string()


# ---------------------------------------------------------------------
# Tooltip
# ---------------------------------------------------------------------

def test_tooltip_drives_to_interactive(gdf_departments):
    base = mp.Map(gdf_departments) + mp.Choropleth(gdf_departments, **CHORO)
    with_tooltip = base + mp.Tooltip(["LIB_GEO"], aliases={"LIB_GEO": "Dep"})
    explicit = base.copy().to_interactive(columns=["LIB_GEO"],
                                          aliases={"LIB_GEO": "Dep"})
    assert with_tooltip.to_interactive().svg == explicit.svg


def test_render_html(gdf_departments, tmp_path):
    m = (mp.Map(gdf_departments) + mp.Choropleth(gdf_departments, **CHORO)
         + mp.Tooltip(["LIB_GEO"], style={"hover": {"opacity": 0.5}}))
    out = tmp_path / "map.html"
    m.render(str(out))
    html = out.read_text(encoding="utf-8")
    assert html.startswith("<!DOCTYPE html>") or "<html" in html
    # The stored style is not consumed by a render.
    assert m._tooltip.style == {"hover": {"opacity": 0.5}}


def test_repr_html_only_with_tooltip(gdf_departments):
    m = mp.Map(gdf_departments) + mp.Basemap()
    assert m._repr_html_() is None
    assert (m + mp.Tooltip())._repr_html_() is not None


def test_tooltip_yaml_round_trip(gdf_departments):
    m = (mp.Map(gdf_departments) + mp.Choropleth(gdf_departments, **CHORO)
         + mp.Tooltip(["LIB_GEO"], aliases={"LIB_GEO": "Dep"}))
    text = m.to_yaml()
    assert "interactive:" in text
    back = mp.Map.from_yaml(text, gdf=gdf_departments)
    assert back._tooltip.columns == ["LIB_GEO"]
    assert back._tooltip.aliases == {"LIB_GEO": "Dep"}


# ---------------------------------------------------------------------
# Layer names removed in 2.0
# ---------------------------------------------------------------------

OLD_LAYER_NAMES = [
    "ChoroplethLayer", "CategoryLayer", "ProportionalLayer", "SituationLayer",
    "LabelLayer", "VectorLayer", "BasemapLayer", "TileLayer", "RasterLayer",
    "GraticuleLayer",
]


@pytest.mark.parametrize("name", OLD_LAYER_NAMES)
def test_old_layer_names_are_gone(name):
    assert not hasattr(mp, name)
    assert name not in mp.__all__
    assert not hasattr(mp.layers, name)


def test_old_type_name_fails_with_a_rename_hint():
    with pytest.raises(ValueError, match="renamed 'Basemap' in mappyng 2.0"):
        Layer.from_dict({"type": "BasemapLayer", "params": {}})


def test_unknown_type_name_has_no_rename_hint():
    with pytest.raises(ValueError) as exc:
        Layer.from_dict({"type": "NopeLayer", "params": {}})
    assert "renamed" not in str(exc.value)


# ---------------------------------------------------------------------
# Ocean gradient
# ---------------------------------------------------------------------

def test_gradient_alphas_follow_profile():
    from mappyng._map_background import _gradient_alphas
    opacity, steps = 0.45, 8
    alphas = _gradient_alphas(opacity, steps)
    assert len(alphas) == steps
    # Stacking the bands from the outermost one reproduces the profile.
    covered = 0.0
    for j, alpha in zip(range(steps, 0, -1), alphas):
        covered = 1 - (1 - covered) * (1 - alpha)
        expected = opacity * (1 - (j - 0.5) / steps) ** 2
        assert covered == pytest.approx(expected)


def test_ocean_gradient_draws_bands(gdf_europe, bbox_metro):
    m = (mp.Map(gdf_europe, bbox=bbox_metro, facecolor="#b9d9eb")
         + mp.Basemap()
         + mp.OceanGradient(gdf_europe, color="#123456", steps=5))
    svg = m.to_string()
    assert svg.count('fill="#123456"') >= 5
    # Drawn below the basemap even when added after it.
    assert svg.index('id="main_ocean_gradient_1"') < \
        svg.index('id="main_basemap"')


def test_ocean_gradient_is_optional(gdf_europe, bbox_metro):
    m = mp.Map(gdf_europe, bbox=bbox_metro) + mp.Basemap()
    assert "ocean_gradient" not in m.to_string()


def test_ocean_gradient_on_cartouches(gdf_europe, bbox_metro):
    def count(**kwargs):
        m = (mp.Map(gdf_europe, bbox=bbox_metro) + _insets()
             + mp.OceanGradient(gdf_europe, color="#123456", **kwargs))
        return m.to_string().count('fill="#123456"')

    assert count() > count(on_cartouches=False)


def test_ocean_gradient_empty_query(gdf_europe, bbox_metro):
    m = mp.Map(gdf_europe, bbox=bbox_metro) + mp.OceanGradient(
        gdf_europe, query="code_pays_iso3 == 'XXX'", color="#123456")
    assert 'fill="#123456"' not in m.to_string()


@pytest.mark.parametrize("kwargs", [{"steps": 0}, {"steps": 2.5},
                                    {"width": 0}])
def test_ocean_gradient_rejects_bad_values(gdf_europe, kwargs):
    with pytest.raises(ValueError, match="OceanGradient"):
        mp.OceanGradient(gdf_europe, **kwargs)


def test_ocean_gradient_yaml_round_trip(gdf_europe, bbox_metro):
    m = mp.Map(gdf_europe, bbox=bbox_metro) + mp.OceanGradient(
        gdf_europe, width=16, opacity=0.3)
    back = mp.Map.from_yaml(m.to_yaml(), gdf=gdf_europe)
    assert back.to_string() == m.to_string()
