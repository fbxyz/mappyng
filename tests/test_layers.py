"""Tests for the first-class Layer object model (TICKET_71)."""

import pytest

from mappyng import Map
from mappyng.layers import (
    Basemap,
    Choropleth,
    Graticule,
    Label,
    Layer,
    LayerStateError,
    Proportional,
    Raster,
    RenderContext,
    Situation,
)
from mappyng.layers.base import _LAYER_REGISTRY

# A numeric column present in the departments fixture, low magnitude so
# the choropleth stock-data warning (TICKET_66) does not fire.
CHORO_PARAMS = {"column": "fid", "method": "Quantiles", "num_classes": 5}


# ---------------------------------------------------------------------
# Construction and validation
# ---------------------------------------------------------------------

def test_choropleth_requires_column(gdf_departments):
    with pytest.raises(ValueError, match="column"):
        Choropleth(gdf_departments)


def test_proportional_requires_column(gdf_departments):
    with pytest.raises(ValueError, match="column"):
        Proportional(gdf_departments)


def test_label_requires_column(gdf_departments):
    with pytest.raises(ValueError, match="column"):
        Label(gdf_departments)


def test_data_layer_requires_gdf():
    with pytest.raises(ValueError, match="non-empty GeoDataFrame"):
        Choropleth(None, column="fid")


def test_data_layer_rejects_empty_gdf(gdf_departments):
    empty = gdf_departments.iloc[0:0]
    with pytest.raises(ValueError, match="non-empty GeoDataFrame"):
        Situation(empty)


def test_reference_layers_need_no_gdf():
    # Reference layers construct without data.
    assert Basemap().gdf is None
    assert Graticule().gdf is None


def test_raster_requires_params():
    with pytest.raises(ValueError, match="raster"):
        Raster()


def test_defaults(gdf_departments):
    layer = Choropleth(gdf_departments, **CHORO_PARAMS)
    assert layer.z_index == 0
    assert layer.visible is True
    assert layer.id is None
    assert layer.kind == "choropleth"


def test_meta_kwargs(gdf_departments):
    layer = Choropleth(gdf_departments, z_index=3, visible=False,
                            **CHORO_PARAMS)
    assert layer.z_index == 3
    assert layer.visible is False
    assert "z_index" not in layer.params
    assert "visible" not in layer.params


# ---------------------------------------------------------------------
# update()
# ---------------------------------------------------------------------

def test_update_returns_self_and_mutates(gdf_departments):
    layer = Choropleth(gdf_departments, **CHORO_PARAMS)
    out = layer.update(cmap="Blues", z_index=2)
    assert out is layer
    assert layer.params["cmap"] == "Blues"
    assert layer.z_index == 2


def test_update_revalidates(gdf_departments):
    layer = Choropleth(gdf_departments, **CHORO_PARAMS)
    # Removing the column via update is not possible, but an invalid
    # construction is caught; here we confirm update keeps validating.
    layer.update(num_classes=6)
    assert layer.params["num_classes"] == 6


def test_update_forbidden_after_render(gdf_departments):
    m = Map(gdf_departments)
    layer = Choropleth(gdf_departments, **CHORO_PARAMS)
    layer.render(RenderContext(m))
    with pytest.raises(LayerStateError, match="already been rendered"):
        layer.update(cmap="Reds")


# ---------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------

def test_to_dict_shape(gdf_departments):
    layer = Choropleth(gdf_departments, z_index=1, **CHORO_PARAMS)
    layer.id = "choropleth-1"
    d = layer.to_dict()
    assert d["type"] == "Choropleth"
    assert d["id"] == "choropleth-1"
    assert d["z_index"] == 1
    assert d["visible"] is True
    assert d["params"] == CHORO_PARAMS
    assert d["data"] == {"in_memory": True}


def test_from_dict_roundtrip(gdf_departments):
    layer = Choropleth(gdf_departments, z_index=2, visible=False,
                            **CHORO_PARAMS)
    layer.id = "choropleth-7"
    rebuilt = Layer.from_dict(layer.to_dict(), gdf=gdf_departments)
    assert isinstance(rebuilt, Choropleth)
    assert rebuilt.id == "choropleth-7"
    assert rebuilt.z_index == 2
    assert rebuilt.visible is False
    assert rebuilt.params == CHORO_PARAMS


def test_from_dict_unknown_type():
    with pytest.raises(ValueError, match="Unknown layer type"):
        Layer.from_dict({"type": "NopeLayer", "params": {}})


def test_registry_contains_all():
    expected = {
        "Choropleth", "Proportional", "Situation",
        "Label", "Vector", "Basemap", "Tile",
        "Raster", "Graticule",
    }
    assert expected <= set(_LAYER_REGISTRY)


def test_repr(gdf_departments):
    layer = Choropleth(gdf_departments, **CHORO_PARAMS)
    r = repr(layer)
    assert "Choropleth" in r
    assert "fid" in r


# ---------------------------------------------------------------------
# Render invariant: direct render == add-then-build
# ---------------------------------------------------------------------

def test_choropleth_direct_render_equals_add(gdf_departments):
    direct = Map(gdf_departments)
    Choropleth(gdf_departments, **CHORO_PARAMS).render(
        RenderContext(direct))

    via_add = Map(gdf_departments)
    via_add.add(Choropleth(gdf_departments, **CHORO_PARAMS))

    assert direct.to_string() == via_add.to_string()


def test_proportional_direct_render_equals_add(gdf_departments):
    params = {"column": "fid", "max_radius": 20}
    direct = Map(gdf_departments)
    Proportional(gdf_departments, **params).render(RenderContext(direct))

    via_add = Map(gdf_departments)
    via_add.add(Proportional(gdf_departments, **params))

    assert direct.to_string() == via_add.to_string()


def test_situation_direct_render_equals_add(gdf_departments):
    direct = Map(gdf_departments)
    Situation(gdf_departments).render(RenderContext(direct))

    via_add = Map(gdf_departments)
    via_add.add(Situation(gdf_departments))

    assert direct.to_string() == via_add.to_string()


def test_basemap_direct_render_equals_add(gdf_departments):
    direct = Map(gdf_departments)
    Basemap(fill="#eee").render(RenderContext(direct))

    via_add = Map(gdf_departments)
    via_add.add(Basemap(fill="#eee"))

    assert direct.to_string() == via_add.to_string()


def test_render_sets_flag(gdf_departments):
    m = Map(gdf_departments)
    layer = Basemap()
    assert layer._rendered is False
    layer.render(RenderContext(m))
    assert layer._rendered is True
