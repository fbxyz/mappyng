"""Tests for map.py, MapState container (TICKET_61) and layer id counters (TICKET_60)."""

from mappyng import Map
from mappyng._state import MapState
from mappyng.layers import Basemap, Choropleth, Label, Situation


def _points(gdf):
    """Centroid point GeoDataFrame derived from a polygon layer."""
    pts = gdf.copy()
    pts["geometry"] = pts.geometry.centroid
    return pts


# ============================================================================
# Per-instance layer id counters
# ============================================================================

def test_layer_counters_start_at_one_per_instance(gdf_departments):
    """Each new Map starts layer counters from 1."""
    m1 = Map(gdf_departments)
    m1.add(Choropleth(gdf_departments, column="fid"))
    m1.add(Choropleth(gdf_departments, column="fid"))

    m2 = Map(gdf_departments)
    m2.add(Choropleth(gdf_departments, column="fid"))

    m1._build()
    m2._build()
    # m1 has used ids 1 and 2, m2 starts fresh at 1
    assert m1._state.layer_counters["choropleth"] == 2
    assert m2._state.layer_counters["choropleth"] == 1


def test_layer_counters_independent_per_kind(gdf_departments):
    """choropleth and situation counters do not collide."""
    pts = _points(gdf_departments)
    m = Map(gdf_departments)
    m.add(Choropleth(gdf_departments, column="fid"))
    m.add(Situation(pts, marker="circle"))
    m.add(Choropleth(gdf_departments, column="fid"))

    m._build()
    assert m._state.layer_counters["choropleth"] == 2
    assert m._state.layer_counters["situation"] == 1


def test_next_layer_id_creates_unknown_kind(gdf_departments):
    """_next_layer_id tolerates a previously unseen kind."""
    m = Map(gdf_departments)
    assert m._next_layer_id("future_kind") == 1
    assert m._next_layer_id("future_kind") == 2


# ============================================================================
# MapState container (TICKET_61)
# ============================================================================

def test_map_has_state_container(gdf_departments):
    """Map exposes a MapState via _state."""
    m = Map(gdf_departments)
    assert isinstance(m._state, MapState)


def test_overflow_property_delegates_to_state(gdf_departments):
    """Public m.overflow returns the same object as m._state.overflow."""
    m = Map(gdf_departments)
    assert m.overflow is m._state.overflow


def test_state_accumulates_interactive_layers(gdf_departments):
    """add_choropleth records an interactive layer in MapState."""
    m = Map(gdf_departments)
    m.add(Choropleth(gdf_departments, column="fid"))
    m._build()
    assert len(m._state.interactive_layers) == 1
    assert m._state.interactive_layers[0]["type"] == "choropleth"


def test_layer_counters_live_in_state(gdf_departments):
    """_next_layer_id reads/writes through MapState."""
    m = Map(gdf_departments)
    m._next_layer_id("choropleth")
    assert m._state.layer_counters["choropleth"] == 1


def test_fresh_map_has_empty_state(gdf_departments):
    """A new Map starts with empty accumulated state."""
    m = Map(gdf_departments)
    assert m._state.interactive_layers == []
    assert m._state.chrome_bboxes == []
    assert m._state.layer_counters == {}


# ============================================================================
# _build() / save() / to_string() pipeline (TICKET_62)
# ============================================================================

def test_build_is_idempotent(gdf_departments):
    """_build() can be called multiple times without error or rework."""
    m = Map(gdf_departments)
    m.add(Basemap())
    m._build()
    viewports_first = m.svg._built_viewports
    m._build()
    assert m.svg._built_viewports is viewports_first
    assert m._built is True


def test_build_resolves_overflow(gdf_departments):
    """_build() resolves overflow before any serialisation."""
    m = Map(gdf_departments)
    m.add(Basemap())
    assert m._built is False
    m._build()
    assert getattr(m, "_overflow_resolved", False) is True


def test_build_constructs_viewports(gdf_departments):
    """_build() builds viewport XML in memory."""
    m = Map(gdf_departments)
    m.add(Basemap())
    m._build()
    assert hasattr(m.svg, "_built_viewports")


def test_render_triggers_build(gdf_departments, tmp_path):
    """render() finalises via _build() and writes a valid SVG."""
    m = Map(gdf_departments)
    m.add(Basemap())
    out = tmp_path / "map.svg"
    m.render(str(out))
    assert m._built is True
    assert out.exists()
    assert out.read_text(encoding="utf-8").lstrip().startswith("<?xml")


def test_to_string_triggers_build(gdf_departments):
    """to_string() finalises via _build() and returns SVG markup."""
    m = Map(gdf_departments)
    m.add(Basemap())
    svg = m.to_string()
    assert m._built is True
    assert "<svg" in svg


def test_build_then_render_no_double_work(gdf_departments, tmp_path):
    """Calling _build() before render() does not rebuild viewports."""
    m = Map(gdf_departments)
    m.add(Basemap())
    m._build()
    viewports_first = m.svg._built_viewports
    m.render(str(tmp_path / "map.svg"))
    assert m.svg._built_viewports is viewports_first


def test_to_interactive_still_works(gdf_departments):
    """to_interactive() routes through _build() via to_string()."""
    m = Map(gdf_departments)
    m.add(Choropleth(gdf_departments, column="fid"))
    im = m.to_interactive()
    assert m._built is True
    assert "<svg" in im.svg


# ============================================================================
# seed= au niveau Map (TICKET_63)
# ============================================================================

def test_map_default_seed_is_42(gdf_departments):
    """Map uses seed=42 by default (backwards-compatible)."""
    m = Map(gdf_departments)
    assert m._seed == 42


def test_map_seed_is_stored(gdf_departments):
    """A custom seed is stored on the Map."""
    m = Map(gdf_departments, seed=7)
    assert m._seed == 7


def test_map_seed_none_is_respected(gdf_departments):
    """seed=None is stored as-is (non-deterministic)."""
    m = Map(gdf_departments, seed=None)
    assert m._seed is None


def test_add_labels_inherits_map_seed(gdf_departments):
    """add_labels uses the Map seed when none is given locally."""
    import mappyng.toponyme as topo

    m = Map(gdf_departments, seed=7)
    captured = {}
    orig = topo.place_labels

    def spy(gdf, column, viewbox, viewport, chrome_bboxes_svg, config,
            **kw):
        captured["seed"] = config.seed
        return orig(gdf, column, viewbox, viewport, chrome_bboxes_svg,
                    config, **kw)

    topo.place_labels = spy
    try:
        m.add(Label(gdf_departments, column="LIB_GEO", n_sweeps=1))
        m._build()
    finally:
        topo.place_labels = orig

    assert captured["seed"] == 7


def test_add_labels_local_seed_overrides_map_seed(gdf_departments):
    """An explicit seed in add_labels wins over the Map seed."""
    import mappyng.toponyme as topo

    m = Map(gdf_departments, seed=7)
    captured = {}
    orig = topo.place_labels

    def spy(gdf, column, viewbox, viewport, chrome_bboxes_svg, config,
            **kw):
        captured["seed"] = config.seed
        return orig(gdf, column, viewbox, viewport, chrome_bboxes_svg,
                    config, **kw)

    topo.place_labels = spy
    try:
        m.add(Label(gdf_departments, column="LIB_GEO", n_sweeps=1, seed=99))
        m._build()
    finally:
        topo.place_labels = orig

    assert captured["seed"] == 99


def test_same_seed_same_label_placement(gdf_departments):
    """Two maps with the same seed produce identical label SVG."""
    m1 = Map(gdf_departments, seed=123)
    m1.add(Label(gdf_departments, column="LIB_GEO", n_sweeps=20, max_labels=15))
    svg1 = m1.to_string()

    m2 = Map(gdf_departments, seed=123)
    m2.add(Label(gdf_departments, column="LIB_GEO", n_sweeps=20, max_labels=15))
    svg2 = m2.to_string()

    assert svg1 == svg2


# ============================================================================
# add_north_arrow (TICKET_68)
# ============================================================================

def test_north_arrow_absent_by_default(gdf_departments):
    """No north arrow unless explicitly added."""
    m = Map(gdf_departments)
    m.add(Basemap())
    assert 'class="north-arrow"' not in m.to_string()


def test_north_arrow_renders(gdf_departments):
    """add_north_arrow draws a north-arrow group."""
    m = Map(gdf_departments)
    m.add(Basemap())
    m.north_arrow()
    svg = m.to_string()
    assert 'class="north-arrow"' in svg
    assert ">N<" in svg


def test_north_arrow_custom_label(gdf_departments):
    """Empty label suppresses the N text."""
    m = Map(gdf_departments)
    m.add(Basemap())
    m.north_arrow(label="")
    svg = m.to_string()
    assert 'class="north-arrow"' in svg
    assert ">N<" not in svg


def test_north_arrow_registers_chrome_bbox(gdf_departments):
    """The arrow registers a chrome bbox for label avoidance."""
    without = Map(gdf_departments).add(Basemap())
    without._build()
    with_arrow = Map(gdf_departments).add(Basemap()).north_arrow()
    with_arrow._build()
    assert (len(with_arrow._state.chrome_bboxes)
            == len(without._state.chrome_bboxes) + 1)


def test_north_arrow_position_override(gdf_departments):
    """A manual position is accepted without error."""
    m = Map(gdf_departments)
    m.add(Basemap())
    m.north_arrow(position={"x": 0.9, "y": 0.1})
    assert 'class="north-arrow"' in m.to_string()


def test_north_arrow_rotation(gdf_departments):
    """A non-zero rotation applies an SVG rotate transform."""
    m = Map(gdf_departments)
    m.add(Basemap())
    m.north_arrow(rotation=15)
    assert "rotate(" in m.to_string()


def test_north_arrow_all_locations(gdf_departments):
    """All four preset locations render without error."""
    for loc in ("upper right", "upper left", "lower right", "lower left"):
        m = Map(gdf_departments)
        m.add(Basemap())
        m.north_arrow(location=loc)
        assert 'class="north-arrow"' in m.to_string()


# ============================================================================
# Export by extension (TICKET_69)
# ============================================================================

import builtins  # noqa: E402

import pytest  # noqa: E402


def test_render_svg_writes_native(gdf_departments, tmp_path):
    """.svg writes native SVG markup."""
    m = Map(gdf_departments)
    m.add(Basemap())
    out = tmp_path / "carte.svg"
    m.render(str(out))
    text = out.read_text(encoding="utf-8")
    assert text.lstrip().startswith("<?xml")
    assert "<svg" in text


def test_render_no_extension_is_svg(gdf_departments, tmp_path):
    """A path without extension is written as SVG."""
    m = Map(gdf_departments)
    out = tmp_path / "carte"
    m.render(str(out))
    assert out.read_text(encoding="utf-8").lstrip().startswith("<?xml")


def test_render_unsupported_extension_raises(gdf_departments, tmp_path):
    """An unknown extension raises a clear ValueError."""
    m = Map(gdf_departments)
    with pytest.raises(ValueError, match="Unsupported export format"):
        m.render(str(tmp_path / "carte.jpeg"))


def test_render_png_without_cairosvg_raises(gdf_departments, tmp_path, monkeypatch):
    """PNG export without cairosvg raises ImportError pointing to the extra."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "cairosvg":
            raise ImportError("simulated missing cairosvg")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    m = Map(gdf_departments)
    with pytest.raises(ImportError, match=r"mappyng\[export\]"):
        m.render(str(tmp_path / "carte.png"))


def test_render_png_works(gdf_departments, tmp_path):
    """PNG export produces a valid file when cairosvg is available."""
    pytest.importorskip("cairosvg")
    m = Map(gdf_departments)
    m.add(Basemap())
    out = tmp_path / "carte.png"
    m.render(str(out), dpi=72)
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_pdf_works(gdf_departments, tmp_path):
    """PDF export produces a valid file when cairosvg is available."""
    pytest.importorskip("cairosvg")
    m = Map(gdf_departments)
    m.add(Basemap())
    out = tmp_path / "carte.pdf"
    m.render(str(out))
    assert out.read_bytes()[:4] == b"%PDF"


def test_render_returns_self(gdf_departments, tmp_path):
    """render() returns the Map for chaining."""
    m = Map(gdf_departments)
    assert m.render(str(tmp_path / "carte.svg")) is m


def test_save_was_removed(gdf_departments):
    """Map.save() (deprecated alias of render) is gone in 2.0."""
    assert not hasattr(Map(gdf_departments), "save")
