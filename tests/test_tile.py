"""Tests pour tile.py, TICKET_31."""

import io
import re
from unittest.mock import patch

import pytest

from mappyng import Map, TileConfig, list_tile_providers
from mappyng.data import load_france_departments
from mappyng.layers import Tile
from mappyng.tile import (
    TILE_PROVIDERS,
    _assemble_tiles,
    _auto_zoom,
    _bbox_4326_from_crs,
    _resolve_url,
    _warp_mosaic_to_viewport,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def metro_gdf():
    gdf = load_france_departments()
    return gdf[gdf.geometry.centroid.x > -600_000].copy()


BBOX_METRO_3857 = [-554_000, 5_066_000, 1_063_000, 6_637_000]


def _make_tile_png_bytes() -> bytes:
    """Return a minimal valid 256×256 PNG as bytes (solid grey)."""
    from PIL import Image
    img = Image.new("RGBA", (256, 256), (180, 180, 180, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _dummy_download(url, cache_path, timeout):
    """Mock tile downloader that returns a grey 256×256 PNG."""
    return _make_tile_png_bytes()


# ---------------------------------------------------------------------------
# 1. list_providers / TileConfig
# ---------------------------------------------------------------------------

def test_list_providers_returns_dict():
    providers = list_tile_providers()
    assert isinstance(providers, dict)
    assert "cartodb_positron" in providers
    assert "openstreetmap" in providers
    assert "satellite" in providers


def test_tile_config_defaults():
    cfg = TileConfig()
    assert cfg.source == "cartodb_positron"
    assert cfg.zoom == "auto"
    assert cfg.opacity == 1.0
    assert cfg.on_cartouches is True
    assert cfg.cache is True


def test_tile_config_custom():
    cfg = TileConfig(source="osm", zoom=8, opacity=0.7, zoom_offset=-1)
    assert cfg.source == "osm"
    assert cfg.zoom == 8
    assert cfg.opacity == 0.7
    assert cfg.zoom_offset == -1


# ---------------------------------------------------------------------------
# 2. _resolve_url
# ---------------------------------------------------------------------------

def test_resolve_url_known_alias():
    url = _resolve_url("cartodb_positron")
    assert "{x}" in url and "{y}" in url and "{z}" in url


def test_resolve_url_case_insensitive():
    url = _resolve_url("CartoDB_Positron")
    assert "cartocdn" in url.lower()


def test_resolve_url_raw_template():
    custom = "https://example.com/tiles/{z}/{x}/{y}.png"
    assert _resolve_url(custom) == custom


def test_resolve_url_unknown_raises():
    with pytest.raises(ValueError, match="Unknown tile provider"):
        _resolve_url("does_not_exist_xyz")


def test_resolve_url_all_providers_valid():
    for alias in TILE_PROVIDERS:
        url = _resolve_url(alias)
        assert "{z}" in url


# ---------------------------------------------------------------------------
# 3. _auto_zoom
# ---------------------------------------------------------------------------

def test_auto_zoom_wide_bbox():
    # France en WGS84: west=-5, east=9 to ~14° de large
    z = _auto_zoom(-5, 9, 900)
    assert 5 <= z <= 12


def test_auto_zoom_small_bbox():
    z = _auto_zoom(2.2, 2.4, 800)
    assert z >= 10


def test_auto_zoom_offset():
    z0 = _auto_zoom(-5, 9, 900, zoom_offset=0)
    z1 = _auto_zoom(-5, 9, 900, zoom_offset=-1)
    assert z1 == z0 - 1


def test_auto_zoom_clamped():
    z = _auto_zoom(0, 0.00001, 800, zoom_offset=10)
    assert z <= 18


# ---------------------------------------------------------------------------
# 4. _bbox_4326_from_crs
# ---------------------------------------------------------------------------

def test_bbox_4326_from_3857():
    # EPSG:3857 bbox for metropolitan France
    west, south, east, north = _bbox_4326_from_crs(BBOX_METRO_3857, "EPSG:3857")
    # Rough sanity checks for France
    assert -10 < west < 0
    assert 41 < south < 46
    assert 7 < east < 12
    assert 49 < north < 52


def test_bbox_4326_clamped():
    # Very large 3857 coords should stay within WGS84 bounds
    w, s, e, n = _bbox_4326_from_crs([-20_000_000, -20_000_000, 20_000_000, 20_000_000], "EPSG:3857")
    assert w >= -180
    assert s >= -85.051129
    assert e <= 180
    assert n <= 85.051129


# ---------------------------------------------------------------------------
# 5. _warp_mosaic_to_viewport
# ---------------------------------------------------------------------------

def test_warp_identity_3857(metro_gdf):
    """Warping a 3857 mosaic into a 3857 viewport should preserve colours."""
    from PIL import Image

    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=200, height=200)
    mosaic = Image.new("RGBA", (256, 256), (100, 150, 200, 255))
    bounds_3857 = (BBOX_METRO_3857[0], BBOX_METRO_3857[1],
                   BBOX_METRO_3857[2], BBOX_METRO_3857[3])
    png_bytes, geo_bounds = _warp_mosaic_to_viewport(
        mosaic, bounds_3857, m.main, m.gdf.crs, warp_scale=1.0
    )
    # Output bounds should equal the viewport geo_bounds
    vb_bounds = m.main.viewbox.geo_bounds
    for a, b in zip(geo_bounds, vb_bounds):
        assert abs(a - b) < 1.0

    # Output should be a valid PNG
    assert png_bytes.startswith(b"\x89PNG")

    # Output image should have correct size
    out = Image.open(io.BytesIO(png_bytes))
    assert out.size[0] == int(m.main.viewbox.content_width)
    assert out.size[1] == int(m.main.viewbox.content_height)


def test_warp_2154_produces_valid_png(metro_gdf):
    """Warping into EPSG:2154 should produce a valid PNG without errors."""
    from PIL import Image

    gdf_2154 = metro_gdf.to_crs(2154)
    bbox_2154 = [90_000, 6_040_000, 1_280_000, 7_150_000]
    m = Map(gdf_2154, bbox=bbox_2154, width=300, height=400)

    mosaic = Image.new("RGBA", (512, 512), (200, 180, 160, 255))
    # A tile mosaic that covers France in EPSG:3857
    bounds_3857 = (-700_000.0, 5_000_000.0, 1_200_000.0, 7_000_000.0)

    png_bytes, geo_bounds = _warp_mosaic_to_viewport(
        mosaic, bounds_3857, m.main, gdf_2154.crs, warp_scale=1.0
    )
    assert png_bytes.startswith(b"\x89PNG")
    assert geo_bounds[0] < geo_bounds[2]   # west < east
    assert geo_bounds[1] < geo_bounds[3]   # south < north


# ---------------------------------------------------------------------------
# 6. _assemble_tiles
# ---------------------------------------------------------------------------

def test_assemble_tiles_single():
    import mercantile
    tile = mercantile.Tile(x=32, y=22, z=6)
    tiles_data = {(tile.x, tile.y): _make_tile_png_bytes()}
    mosaic, bounds_3857 = _assemble_tiles(tiles_data, [tile], zoom=6)
    west, south, east, north = bounds_3857
    assert west < east
    assert south < north
    assert mosaic.size == (256, 256)


def test_assemble_tiles_2x2():
    import mercantile
    tiles = [
        mercantile.Tile(x=32, y=22, z=6),
        mercantile.Tile(x=33, y=22, z=6),
        mercantile.Tile(x=32, y=23, z=6),
        mercantile.Tile(x=33, y=23, z=6),
    ]
    tiles_data = {(t.x, t.y): _make_tile_png_bytes() for t in tiles}
    mosaic, bounds_3857 = _assemble_tiles(tiles_data, tiles, zoom=6)
    assert mosaic.size == (512, 512)


def test_assemble_tiles_missing_tile():
    import mercantile
    tiles = [mercantile.Tile(x=32, y=22, z=6), mercantile.Tile(x=33, y=22, z=6)]
    tiles_data = {(32, 22): _make_tile_png_bytes(), (33, 22): None}
    mosaic, _ = _assemble_tiles(tiles_data, tiles, zoom=6)
    assert mosaic.size == (512, 256)


# ---------------------------------------------------------------------------
# 7. Map.add_tile(), integration (mocked network)
# ---------------------------------------------------------------------------

@patch("mappyng.tile._download_tile", side_effect=lambda url, cache, timeout: _make_tile_png_bytes())
def test_add_tile_produces_image_in_svg(mock_dl, metro_gdf):
    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    m.add(Tile(source="cartodb_positron", zoom=6, cache=False))
    svg = m.to_string()
    assert "<image" in svg
    assert "data:image/png;base64" in svg


@patch("mappyng.tile._download_tile", side_effect=lambda url, cache, timeout: _make_tile_png_bytes())
def test_add_tile_alpha(mock_dl, metro_gdf):
    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    m.add(Tile(source="positron", zoom=6, opacity=0.4, cache=False))
    svg = m.to_string()
    assert "opacity" in svg


@patch("mappyng.tile._download_tile", side_effect=lambda url, cache, timeout: _make_tile_png_bytes())
def test_add_tile_all_providers_resolve(mock_dl, metro_gdf):
    """_resolve_url should not raise for any registered alias."""
    for alias in list(TILE_PROVIDERS.keys())[:6]:
        m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
        m.add(Tile(source=alias, zoom=6, cache=False))


@patch("mappyng.tile._download_tile", side_effect=lambda url, cache, timeout: None)
def test_add_tile_all_downloads_fail_warns(mock_dl, metro_gdf):
    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    with pytest.warns(UserWarning, match="all tile downloads failed"):
        m.add(Tile(source="osm", zoom=6, cache=False))
        m._build()
    svg = m.to_string()
    # No tile image should be in SVG
    assert svg.count("<image") == 0


@patch("mappyng.tile._download_tile", side_effect=lambda url, cache, timeout: _make_tile_png_bytes())
def test_add_tile_max_tiles_warns(mock_dl, metro_gdf):
    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    with pytest.warns(UserWarning, match="max_tiles"):
        m.add(Tile(source="osm", zoom=12, max_tiles=2, cache=False))
        m._build()


@patch("mappyng.tile._download_tile", side_effect=lambda url, cache, timeout: _make_tile_png_bytes())
def test_add_tile_custom_url(mock_dl, metro_gdf):
    custom = "https://example.com/{z}/{x}/{y}.png"
    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    m.add(Tile(source=custom, zoom=6, cache=False))
    svg = m.to_string()
    assert "<image" in svg


@patch("mappyng.tile._download_tile", side_effect=lambda url, cache, timeout: _make_tile_png_bytes())
def test_add_tile_auto_zoom(mock_dl, metro_gdf):
    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    m.add(Tile(source="positron", zoom="auto", cache=False))
    svg = m.to_string()
    assert "<image" in svg


# ---------------------------------------------------------------------------
# 8. extra_zoom_levels
# ---------------------------------------------------------------------------

@patch("mappyng.tile._download_tile", side_effect=lambda url, cache, timeout: _make_tile_png_bytes())
def test_extra_zoom_levels_produces_image(mock_dl, metro_gdf):
    """extra_zoom_levels=2 should still produce one composited <image>."""
    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    m.add(Tile(source="positron", zoom=6, extra_zoom_levels=2, cache=False))
    svg = m.to_string()
    assert "<image" in svg
    # Still exactly one tile image (composited)
    assert svg.count("<image") == 1


@patch("mappyng.tile._download_tile", side_effect=lambda url, cache, timeout: _make_tile_png_bytes())
def test_extra_zoom_levels_calls_download_more(mock_dl, metro_gdf):
    """With extra_zoom_levels=2 we should download tiles for 3 zoom levels."""
    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    m.add(Tile(source="positron", zoom=6, extra_zoom_levels=2, cache=False))
    m._build()
    # At zoom 4,5,6 over France: at least 3 download calls
    assert mock_dl.call_count >= 3


@patch("mappyng.tile._download_tile", side_effect=lambda url, cache, timeout: _make_tile_png_bytes())
def test_extra_zoom_levels_zero_unchanged(mock_dl, metro_gdf):
    """extra_zoom_levels=0 (default) behaves like before."""
    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    m.add(Tile(source="positron", zoom=6, extra_zoom_levels=0, cache=False))
    calls_without_extra = mock_dl.call_count
    mock_dl.reset_mock()

    m2 = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    m2.add(Tile(source="positron", zoom=6, cache=False))
    assert mock_dl.call_count == calls_without_extra


def _dl_fine_only(url, cache, timeout):
    """Simulate: coarser zoom tiles fail, only finest zoom succeeds."""
    # url contains /{z}/, extract z
    m = re.search(r'/(\d+)/\d+/\d+', url)
    z = int(m.group(1)) if m else 99
    if z < 6:
        return None   # coarse levels fail
    return _make_tile_png_bytes()


@patch("mappyng.tile._download_tile", side_effect=_dl_fine_only)
def test_extra_zoom_fallback_coarse_missing(mock_dl, metro_gdf):
    """When coarser tiles all fail, finer tiles still produce an image."""
    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    m.add(Tile(source="positron", zoom=6, extra_zoom_levels=2, cache=False))
    assert "<image" in m.to_string()


def _dl_coarse_only(url, cache, timeout):
    """Simulate: only coarsest zoom tiles succeed."""
    m = re.search(r'/(\d+)/\d+/\d+', url)
    z = int(m.group(1)) if m else 99
    return _make_tile_png_bytes() if z <= 4 else None


@patch("mappyng.tile._download_tile", side_effect=_dl_coarse_only)
def test_extra_zoom_fallback_fine_missing(mock_dl, metro_gdf):
    """When finer tiles fail, coarser tiles still fill in the image."""
    m = Map(metro_gdf, bbox=BBOX_METRO_3857, width=800, height=600)
    m.add(Tile(source="positron", zoom=6, extra_zoom_levels=2, cache=False))
    assert "<image" in m.to_string()


def test_assemble_tiles_warns_on_undecodable_tile():
    mercantile = pytest.importorskip("mercantile")
    from mappyng.tile import _assemble_tiles

    tile = mercantile.Tile(1, 1, 2)
    with pytest.warns(UserWarning, match="could not be decoded"):
        _assemble_tiles({(1, 1): b"not an image"}, [tile], 2)
