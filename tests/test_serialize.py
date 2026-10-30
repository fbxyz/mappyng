"""YAML serialisation round-trip (TICKET_7A)."""

import pytest

from mappyng import Map
from mappyng.layers import Basemap, Choropleth
from mappyng.serialize import SCHEMA_VERSION, map_to_dict

CHORO = dict(column="fid", method="Quantiles", num_classes=4, cmap="Blues")


def _make(gdf):
    m = Map(gdf, width=800, height="auto", style="modern", seed=7,
            facecolor="#cce")
    m.add(Basemap())
    m.add(Choropleth(gdf, z_index=2, **CHORO))
    m.title("Carte", subtitle="sub")
    m.source("INSEE")
    m.scale_bar()
    return m


# ---------------------------------------------------------------------
# to_yaml: structure
# ---------------------------------------------------------------------

def test_to_yaml_has_versioned_root(gdf_departments):
    doc = map_to_dict(_make(gdf_departments))
    assert doc["mappyng"] == SCHEMA_VERSION
    assert doc["map"]["height"] == "auto"     # auto preserved, not resolved
    assert doc["map"]["width"] == 800
    assert doc["map"]["style"] == "modern"
    assert doc["map"]["seed"] == 7
    assert [l["type"] for l in doc["layers"]] == ["Basemap", "Choropleth"]


def test_to_yaml_records_chrome(gdf_departments):
    doc = map_to_dict(_make(gdf_departments))
    assert doc["chrome"]["title"]["text"] == "Carte"
    assert doc["chrome"]["title"]["subtitle"] == "sub"
    assert doc["chrome"]["source"]["text"] == "INSEE"
    assert "scale_bar" in doc["chrome"]


def test_to_yaml_is_valid_yaml_string(gdf_departments):
    yaml = pytest.importorskip("yaml")
    text = _make(gdf_departments).to_yaml()
    reparsed = yaml.safe_load(text)
    assert reparsed["mappyng"] == SCHEMA_VERSION


def test_to_yaml_writes_file(gdf_departments, tmp_path):
    out = tmp_path / "map.yaml"
    text = _make(gdf_departments).to_yaml(str(out))
    assert out.read_text(encoding="utf-8") == text


# ---------------------------------------------------------------------
# round-trip
# ---------------------------------------------------------------------

def test_round_trip_is_byte_identical(gdf_departments):
    """A map rebuilt from its own YAML renders identical SVG."""
    svg_orig = _make(gdf_departments).to_string()
    svg_rt = Map.from_yaml(_make(gdf_departments).to_yaml(),
                           gdf=gdf_departments).to_string()
    assert svg_orig == svg_rt


def _make_with_zoom(gdf):
    from mappyng import Zoom
    return (Map(gdf, width=500, height=600)
            + Zoom([634000, 6841000, 674000, 6882000], x=350, y=80,
                   width=100, height=110, border_radius=8, box_shadow=True)
            + Basemap()
            + Choropleth(gdf, column="fid", method="Quantiles",
                         num_classes=5))


def test_to_yaml_records_zoom(gdf_departments):
    doc = map_to_dict(_make_with_zoom(gdf_departments))
    assert doc["zoom"] == {"bbox": [634000, 6841000, 674000, 6882000],
                           "x": 350, "y": 80, "width": 100, "height": 110,
                           "border_radius": 8, "box_shadow": True}


def test_zoom_round_trip_is_byte_identical(gdf_departments):
    svg_orig = _make_with_zoom(gdf_departments).to_string()
    text = _make_with_zoom(gdf_departments).to_yaml()
    svg_rt = Map.from_yaml(text, gdf=gdf_departments).to_string()
    assert svg_orig == svg_rt


def test_from_yaml_zoom_without_bbox_raises(gdf_departments):
    text = _make_with_zoom(gdf_departments).to_yaml()
    text = text.replace("zoom:\n  bbox:", "zoom:\n  old_bbox:")
    with pytest.raises(ValueError, match="needs a 'bbox'"):
        Map.from_yaml(text, gdf=gdf_departments)


def test_from_yaml_reconstructs_layers_and_config(gdf_departments):
    m = Map.from_yaml(_make(gdf_departments).to_yaml(), gdf=gdf_departments)
    assert [l.id for l in m.layers] == ["basemap-1", "choropleth-1"]
    assert m.get_layer("choropleth-1").params["cmap"] == "Blues"
    assert m._auto_height is True
    assert m._seed == 7
    assert m.facecolor == "#cce"


def test_from_yaml_accepts_file_path(gdf_departments, tmp_path):
    out = tmp_path / "map.yaml"
    _make(gdf_departments).to_yaml(str(out))
    m = Map.from_yaml(str(out), gdf=gdf_departments)
    assert len(m.layers) == 2


def test_from_yaml_per_layer_data_override(gdf_departments):
    doc_map = _make(gdf_departments)
    m = Map.from_yaml(doc_map.to_yaml(), gdf=gdf_departments,
                      data={"choropleth-1": gdf_departments})
    assert m.get_layer("choropleth-1").gdf is gdf_departments


# ---------------------------------------------------------------------
# errors
# ---------------------------------------------------------------------

def test_from_yaml_without_gdf_or_source_raises(gdf_departments):
    with pytest.raises(ValueError, match="no geometry to build from"):
        Map.from_yaml(_make(gdf_departments).to_yaml())


def test_from_yaml_unknown_version_raises(gdf_departments):
    text = _make(gdf_departments).to_yaml().replace("mappyng: 1", "mappyng: 999")
    with pytest.raises(ValueError, match="Unsupported mappyng serialisation"):
        Map.from_yaml(text, gdf=gdf_departments)


def test_to_yaml_rejects_non_serialisable_param(gdf_departments):
    m = Map(gdf_departments)
    m.add(Choropleth(gdf_departments, column="fid", stroke=lambda x: x))
    with pytest.raises(TypeError, match="Cannot serialise"):
        m.to_yaml()


# ---------------------------------------------------------------------
# data sources: build a map from a YAML alone (no gdf passed)
# ---------------------------------------------------------------------

LAYER_SRC = """
mappyng: 1
map: {width: 800, height: auto}
layers:
- type: Choropleth
  data: {dataset: france_departments, crs: 2154}
  params: {column: fid, method: Quantiles, num_classes: 4, cmap: Blues}
"""


def test_from_yaml_resolves_layer_dataset_source():
    m = Map.from_yaml(LAYER_SRC)
    layer = m.get_layer("choropleth-1")
    assert not layer.gdf.empty
    assert layer.gdf.crs.to_epsg() == 2154
    assert m.to_string().startswith("<?xml")


def test_from_yaml_resolves_map_level_source():
    doc = """
mappyng: 1
map: {width: 800, height: auto, data: {dataset: france_departments}}
layers:
- type: Basemap
  data: {in_memory: false}
  params: {}
"""
    m = Map.from_yaml(doc)
    assert not m.gdf.empty


def test_from_yaml_path_source_resolves_relative_to_base_dir(gdf_departments, tmp_path):
    geo = tmp_path / "deps.geojson"
    gdf_departments.to_file(geo, driver="GeoJSON")
    (tmp_path / "map.yaml").write_text(
        "mappyng: 1\n"
        "map: {width: 800, height: auto}\n"
        "layers:\n"
        "- type: Choropleth\n"
        "  data: {path: deps.geojson}\n"
        "  params: {column: fid, method: Quantiles, num_classes: 4, cmap: Blues}\n",
        encoding="utf-8",
    )
    m = Map.from_yaml(str(tmp_path / "map.yaml"))
    assert len(m.get_layer("choropleth-1").gdf) == len(gdf_departments)


def test_from_yaml_csv_join(gdf_departments, tmp_path):
    import pandas as pd

    codes = gdf_departments["COD_GEO"].tolist()
    pd.DataFrame({"code": codes, "val": range(len(codes))}).to_csv(
        tmp_path / "vals.csv", index=False)
    gdf_departments.to_file(tmp_path / "deps.geojson", driver="GeoJSON")
    (tmp_path / "map.yaml").write_text(
        "mappyng: 1\n"
        "map: {width: 800, height: auto}\n"
        "layers:\n"
        "- type: Choropleth\n"
        "  data:\n"
        "    path: deps.geojson\n"
        "    join: {path: vals.csv, left_on: COD_GEO, right_on: code}\n"
        "  params: {column: val, method: Quantiles, num_classes: 4, cmap: Blues}\n",
        encoding="utf-8",
    )
    m = Map.from_yaml(str(tmp_path / "map.yaml"))
    assert "val" in m.get_layer("choropleth-1").gdf.columns


def test_from_yaml_unknown_dataset_raises():
    doc = LAYER_SRC.replace("france_departments", "atlantis")
    with pytest.raises(ValueError, match="Unknown built-in dataset"):
        Map.from_yaml(doc)


def test_explicit_gdf_overrides_declared_source(gdf_europe):
    """Passing gdf wins over the declared dataset (back-compat / override)."""
    m = Map.from_yaml(LAYER_SRC, gdf=gdf_europe)
    assert m.get_layer("choropleth-1").gdf is gdf_europe


def test_cli_renders_yaml_to_svg(tmp_path):
    from mappyng.__main__ import main

    (tmp_path / "map.yaml").write_text(LAYER_SRC, encoding="utf-8")
    out = tmp_path / "out.svg"
    rc = main([str(tmp_path / "map.yaml"), "-o", str(out)])
    assert rc == 0
    assert out.exists() and out.read_text(encoding="utf-8").startswith("<?xml")


# ---------------------------------------------------------------------
# full Map constructor params + declarative shadows
# ---------------------------------------------------------------------

def test_constructor_params_round_trip(gdf_departments):
    bbox = [90000, 6040000, 1280000, 7150000]
    m = Map(gdf_departments, bbox=bbox, width=900, height=1000, padding=25,
            facecolor="#B9D9EB", border_radius=10,
            box_shadow={"dx": 3, "dy": 3, "blur": 6, "opacity": 0.2},
            cartouche_params={0: {"bbox": [1, 2, 3, 4], "crs": 3857}},
            cartouche_spacing=15)
    doc = map_to_dict(m)
    assert doc["map"]["bbox"] == bbox
    assert doc["map"]["padding"] == 25
    assert doc["map"]["border_radius"] == 10
    assert doc["map"]["box_shadow"] == {"dx": 3, "dy": 3, "blur": 6, "opacity": 0.2}
    assert doc["map"]["cartouche_spacing"] == 15
    # Integer cartouche keys survive the round-trip (YAML stores them as str).
    m2 = Map.from_yaml(m.to_yaml(), gdf=gdf_departments)
    assert m2.bbox == bbox
    assert 0 in m2.cartouche_params
    assert m2._main_box_shadow == {"dx": 3, "dy": 3, "blur": 6, "opacity": 0.2}


def test_declarative_shadow_replayed(gdf_europe):
    doc = """
mappyng: 1
map: {width: 800, height: auto, data: {dataset: europe, crs: 2154}}
layers:
- type: Basemap
  data: {in_memory: false}
  params: {}
shadows:
- data: {dataset: europe, crs: 2154}
  params: {query: "code_pays_iso3=='FRA'"}
"""
    m = Map.from_yaml(doc)
    assert 'id="shadow-' in m.to_string()
