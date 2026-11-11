"""
Web tile module for mappyng.

Downloads XYZ raster tiles (OpenStreetMap, CartoDB, ESRI, Stadia, ...) and
embeds them as base64 PNG ``<image>`` elements inside SVG viewports.

No contextily / matplotlib / rasterio dependency, uses:
  - mercantile, calcul des tuiles XYZ
  - urllib, téléchargement HTTP (stdlib)
  - Pillow, assemblage du mosaïque PNG
  - numpy+pyproj, reprojection pixel à pixel (mapping inverse)

Coordinate handling
-------------------
Tiles are served in EPSG:3857 (Web Mercator).  After assembling the mosaic,
each output pixel is reprojected from the map CRS back to EPSG:3857 via an
**inverse mapping** (no rasterio required): for every pixel of the output
image (which is defined in the map CRS grid), we compute the corresponding
EPSG:3857 coordinate and sample the tile mosaic there.  The result is a
correctly warped raster, placed exactly over the viewport's geographic bbox.

Example
-------
>>> from mappyng import Tile
>>> m.add(Tile(source="cartodb_positron", zoom="auto", opacity=0.9))
>>> m.add(Tile(source="satellite", zoom=10))
>>> m.add(Tile(source="https://tile.openstreetmap.org/{z}/{x}/{y}.png"))
"""

from __future__ import annotations

import base64
import hashlib
import io
import math
import pathlib
import urllib.request
import warnings
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # annotations only; Pillow is an optional dependency
    import PIL.Image

from . import defaults as D
from .errors import GEO_ERRORS

# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

#: Tile provider aliases accepted by ``Tile(source=...)``, mapped to their
#: ``{z}/{x}/{y}`` URL templates.
TILE_PROVIDERS: dict[str, str] = {
    # OpenStreetMap
    "openstreetmap": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "osm": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "osm_hot": "https://a.tile.openstreetmap.fr/hot/{z}/{x}/{y}.png",
    # CartoDB
    "cartodb_positron": "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    "positron": "https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png",
    "cartodb_darkmatter": "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    "darkmatter": "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
    "cartodb_voyager": "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
    "voyager": "https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png",
    # Stadia / Stamen
    "stadia_terrain": "https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}.png",
    "terrain": "https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}.png",
    "stadia_toner": "https://tiles.stadiamaps.com/tiles/stamen_toner/{z}/{x}/{y}.png",
    "toner": "https://tiles.stadiamaps.com/tiles/stamen_toner/{z}/{x}/{y}.png",
    "stadia_toner_lite": "https://tiles.stadiamaps.com/tiles/stamen_toner_lite/{z}/{x}/{y}.png",
    "stadia_watercolor": "https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg",
    "watercolor": "https://tiles.stadiamaps.com/tiles/stamen_watercolor/{z}/{x}/{y}.jpg",
    # ESRI, URL order is {z}/{y}/{x} (row/col), not {z}/{x}/{y}
    "esri_worldimagery": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "satellite": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "esri_worldterrain": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}",
    "esri_worldstreet": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    "esri_natgeo": "https://server.arcgisonline.com/ArcGIS/rest/services/NatGeo_World_Map/MapServer/tile/{z}/{y}/{x}",
    "esri_ocean": "https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}",
    # OpenTopoMap
    "opentopomap": "https://tile.opentopomap.org/{z}/{x}/{y}.png",
    "topo": "https://tile.opentopomap.org/{z}/{x}/{y}.png",
}

USER_AGENT = "mappyng/1 (https://github.com/fbxyz/mappyng)"
TILE_SIZE = 256


# ---------------------------------------------------------------------------
# TileConfig
# ---------------------------------------------------------------------------

@dataclass
class TileConfig:
    """Configuration for a tile layer.

    Parameters
    ----------
    source : str
        Provider alias (e.g. ``"cartodb_positron"``) or a URL template
        with ``{x}``, ``{y}``, ``{z}`` placeholders.
    zoom : int or ``"auto"``
        Zoom level or ``"auto"`` (calculated from bbox + map width).
    zoom_offset : int
        Added to the auto-calculated zoom (e.g. ``-1`` for lighter tiles).
    opacity : float
        Tile layer opacity (0-1).
    z_order : int
        SVG z-order of the tile layer (default below basemap).
    timeout : float
        HTTP request timeout in seconds.
    cache : bool
        Whether to use disk cache (default True).
    cache_dir : str or None
        Cache directory. Defaults to ``~/.cache/mappyng/tiles``.
    on_cartouches : bool
        Render on cartouche viewports (default True).
    on_zoom : bool
        Render on zoom viewport (default True).
    max_tiles : int
        Safety limit on the number of tiles downloaded per viewport.
    warp_scale : float
        Resolution of the warped output image relative to the SVG content
        area (default 1.5, 50 % denser than screen pixels for crispness).
    """
    source: str = "cartodb_positron"
    zoom: object = "auto"
    zoom_offset: int = 0
    opacity: float = 1.0
    z_order: int = D.Z_RASTER
    timeout: float = 10.0
    cache: bool = True
    cache_dir: str | None = None
    on_cartouches: bool = True
    on_zoom: bool = True
    max_tiles: int = 64
    warp_scale: float = 1.5
    extra_zoom_levels: int = 0
    """Number of coarser zoom levels to also fetch (0 = target zoom only).
    Levels are composited from coarsest to finest: finer tiles overwrite
    coarser ones where they exist, coarser ones fill gaps where finer tiles
    failed to download.  E.g. ``extra_zoom_levels=3`` fetches at zoom,
    zoom-1, zoom-2, zoom-3 and composites them."""


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------

def _check_mercantile():
    try:
        import mercantile
        return mercantile
    except ImportError as e:
        raise ImportError(
            "mercantile is required for tile functionality. "
            "Install it with: pip install mercantile"
        ) from e


def _check_pillow():
    try:
        from PIL import Image
        return Image
    except ImportError as e:
        raise ImportError(
            "Pillow is required for tile functionality. "
            "Install it with: pip install Pillow"
        ) from e


# ---------------------------------------------------------------------------
# Provider resolution
# ---------------------------------------------------------------------------

def _resolve_url(source: str) -> str:
    """Return the URL template for a provider alias or a raw URL template."""
    low = source.lower()
    if low in TILE_PROVIDERS:
        return TILE_PROVIDERS[low]
    if "{z}" in source and ("{x}" in source or "{y}" in source):
        return source
    raise ValueError(
        f"Unknown tile provider: '{source}'. "
        f"Available providers: {sorted(TILE_PROVIDERS.keys())} "
        f"or pass a URL template with {{x}}, {{y}}, {{z}} placeholders."
    )


# ---------------------------------------------------------------------------
# Zoom
# ---------------------------------------------------------------------------

def _auto_zoom(west: float, east: float, map_width_px: float,
               zoom_offset: int = 0) -> int:
    """Estimate zoom so one tile mosaic covers the map at screen resolution."""
    if east <= west:
        return max(1, 5 + zoom_offset)
    lon_span = east - west
    z_float = math.log2(map_width_px * 360.0 / (TILE_SIZE * lon_span))
    return max(1, min(18, math.floor(z_float) + zoom_offset))


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_path_for(cache_dir: pathlib.Path, provider_key: str,
                    z: int, x: int, y: int) -> pathlib.Path:
    safe = provider_key.replace("://", "_").replace("/", "_")[:40]
    if provider_key not in TILE_PROVIDERS:
        # A URL template: the readable prefix alone is ambiguous (two
        # templates of one server share it), a digest tells them apart.
        digest = hashlib.sha1(provider_key.encode("utf-8")).hexdigest()[:10]
        safe = f"{safe}-{digest}"
    return cache_dir / safe / str(z) / str(x) / f"{y}.png"


def _download_tile(url: str, cache_path: pathlib.Path | None,
                   timeout: float) -> bytes | None:
    if cache_path is not None and cache_path.exists():
        return cache_path.read_bytes()
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(data)
        return data
    except Exception as exc:
        warnings.warn(f"tile download failed ({url}): {exc}")
        return None


# ---------------------------------------------------------------------------
# bbox helpers
# ---------------------------------------------------------------------------

def _bbox_4326_from_crs(bbox_map_crs, crs) -> tuple[float, float, float, float]:
    """Convert a bounding box from *crs* to EPSG:4326."""
    import geopandas as gpd
    from shapely.geometry import box as shapely_box

    gdf = gpd.GeoDataFrame(geometry=[shapely_box(*bbox_map_crs)], crs=crs)
    b = gdf.to_crs("EPSG:4326").total_bounds
    west  = max(-180.0,     float(b[0]))
    south = max(-85.051129, float(b[1]))
    east  = min( 180.0,     float(b[2]))
    north = min( 85.051129, float(b[3]))
    return west, south, east, north


# ---------------------------------------------------------------------------
# Tile download + mosaic assembly
# ---------------------------------------------------------------------------

def _assemble_tiles(
    tiles_data: dict,
    tile_list,
    zoom: int,
) -> tuple[PIL.Image.Image, tuple[float, float, float, float]]:
    """Assemble downloaded tile images into a PIL mosaic.

    Returns (mosaic_image, (west_3857, south_3857, east_3857, north_3857)).
    """
    import mercantile
    from PIL import Image

    image_errors = (OSError, ValueError, SyntaxError,
                    Image.DecompressionBombError)

    xs = [t.x for t in tile_list]
    ys = [t.y for t in tile_list]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    cols = max_x - min_x + 1
    rows = max_y - min_y + 1

    mosaic = Image.new("RGBA", (cols * TILE_SIZE, rows * TILE_SIZE),
                       (255, 255, 255, 0))
    n_corrupt = 0

    for tile in tile_list:
        data = tiles_data.get((tile.x, tile.y))
        if not data:
            continue
        try:
            img = Image.open(io.BytesIO(data)).convert("RGBA")
        except image_errors:
            n_corrupt += 1
            continue
        px = (tile.x - min_x) * TILE_SIZE
        py = (tile.y - min_y) * TILE_SIZE
        mosaic.paste(img, (px, py))

    if n_corrupt:
        warnings.warn(
            f"Tile: {n_corrupt} tile(s) could not be decoded and were left "
            f"blank. Delete the tile cache to download them again."
        )

    ul = mercantile.xy_bounds(mercantile.Tile(min_x, min_y, zoom))
    lr = mercantile.xy_bounds(mercantile.Tile(max_x, max_y, zoom))
    bounds_3857 = (ul.left, lr.bottom, lr.right, ul.top)

    return mosaic, bounds_3857


# ---------------------------------------------------------------------------
# Inverse-mapping warp: EPSG:3857 mosaic to map CRS output image
# ---------------------------------------------------------------------------

def _warp_mosaic_to_viewport(
    mosaic: PIL.Image.Image,
    bounds_3857: tuple[float, float, float, float],
    viewport,
    dst_crs,
    warp_scale: float = 1.5,
) -> tuple[bytes, tuple[float, float, float, float]]:
    """Warp a Web Mercator tile mosaic into the viewport's CRS.

    For each pixel of the output image (defined on a regular grid in *dst_crs*
    covering the viewport's geographic bbox), find the corresponding position
    in the EPSG:3857 mosaic by inverse transformation and sample the colour
    there (nearest-neighbour).  No rasterio needed.

    Returns
    -------
    (png_bytes, geo_bounds)
        *geo_bounds* is (minx, miny, maxx, maxy) in *dst_crs*, equal to
        the viewport's ``geo_bounds``, so the image fits the viewport exactly.
    """
    import numpy as np
    from PIL import Image
    from pyproj import Transformer

    vb = viewport.viewbox
    geo_minx, geo_miny, geo_maxx, geo_maxy = vb.geo_bounds

    out_w = max(1, int(vb.content_width  * warp_scale))
    out_h = max(1, int(vb.content_height * warp_scale))

    # Regular grid in map CRS covering geo_bounds (pixel centres)
    col_arr = (np.arange(out_w) + 0.5) / out_w  # 0..1
    row_arr = (np.arange(out_h) + 0.5) / out_h  # 0..1
    col_frac, row_frac = np.meshgrid(col_arr, row_arr)   # (out_h, out_w)

    geo_x = geo_minx + col_frac * (geo_maxx - geo_minx)   # map CRS x
    geo_y = geo_maxy - row_frac * (geo_maxy - geo_miny)   # map CRS y (top to bottom)

    # Inverse transform: map CRS to EPSG:3857
    transformer = Transformer.from_crs(dst_crs, "EPSG:3857", always_xy=True)
    src_x, src_y = transformer.transform(geo_x.ravel(), geo_y.ravel())
    src_x = src_x.reshape(out_h, out_w)
    src_y = src_y.reshape(out_h, out_w)

    # Map EPSG:3857 coords to pixel in mosaic
    west_3857, south_3857, east_3857, north_3857 = bounds_3857
    mos_w, mos_h = mosaic.size

    src_col = (src_x - west_3857)  / (east_3857  - west_3857)  * mos_w
    src_row = (north_3857 - src_y) / (north_3857 - south_3857) * mos_h

    # Valid mask: pixel falls inside the mosaic
    valid = (
        (src_col >= 0) & (src_col < mos_w) &
        (src_row >= 0) & (src_row < mos_h)
    )

    src_col_i = np.clip(src_col.astype(np.int32), 0, mos_w - 1)
    src_row_i = np.clip(src_row.astype(np.int32), 0, mos_h - 1)

    # Sample mosaic (nearest-neighbour)
    mos_arr = np.asarray(mosaic)                           # (mos_h, mos_w, 4)
    out_arr = mos_arr[src_row_i, src_col_i]                # (out_h, out_w, 4)
    out_arr[~valid] = 0                                    # transparent outside

    out_img = Image.fromarray(out_arr.astype(np.uint8), mode="RGBA")
    buf = io.BytesIO()
    out_img.save(buf, format="PNG")

    return buf.getvalue(), (geo_minx, geo_miny, geo_maxx, geo_maxy)


# ---------------------------------------------------------------------------
# Place warped PNG in SVG viewport
# ---------------------------------------------------------------------------

def _place_tile_png(
    viewport,
    png_bytes: bytes,
    geo_bounds: tuple[float, float, float, float],
    alpha: float,
    z_order: int,
) -> None:
    """Embed a PNG into a viewport, clipped to geo_bounds."""
    vb = viewport.viewbox
    minx, miny, maxx, maxy = geo_bounds

    sx0, sy0 = vb.geo_to_svg(minx, maxy)   # top-left
    sx1, sy1 = vb.geo_to_svg(maxx, miny)   # bottom-right
    sw = sx1 - sx0
    sh = sy1 - sy0
    if sw <= 0 or sh <= 0:
        return

    href = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
    attrs = {"preserveAspectRatio": "none"}
    if alpha < 1.0:
        attrs["opacity"] = f"{alpha:.3f}"

    viewport.add_image("tile", sx0, sy0, sw, sh, href, z_order=z_order, **attrs)


# ---------------------------------------------------------------------------
# Core: fetch + warp + place on a single viewport
# ---------------------------------------------------------------------------

def _fetch_one_zoom(
    zoom: int,
    bbox_4326: tuple[float, float, float, float],
    url_template: str,
    provider_key: str,
    cfg: TileConfig,
    cache_dir: pathlib.Path | None,
) -> tuple[PIL.Image.Image, tuple[float, float, float, float]] | None:
    """Download all tiles at *zoom* for *bbox_4326* and return assembled mosaic.

    Returns ``(mosaic_image, bounds_3857)`` or ``None`` if all downloads failed
    or the tile count exceeds ``cfg.max_tiles``.
    """
    import mercantile

    tile_list = list(mercantile.tiles(*bbox_4326, zooms=zoom))
    if not tile_list:
        return None
    if len(tile_list) > cfg.max_tiles:
        warnings.warn(
            f"Tile: zoom {zoom} needs {len(tile_list)} tiles "
            f"(max_tiles={cfg.max_tiles}), so this level was skipped. "
            f"Lower the zoom or raise max_tiles to fetch it."
        )
        return None

    tiles_data = {}
    for tile in tile_list:
        url = url_template.format(x=tile.x, y=tile.y, z=tile.z)
        cp = (
            _cache_path_for(cache_dir, provider_key, tile.z, tile.x, tile.y)
            if cfg.cache and cache_dir is not None else None
        )
        tiles_data[(tile.x, tile.y)] = _download_tile(url, cp, cfg.timeout)

    if all(v is None for v in tiles_data.values()):
        return None

    return _assemble_tiles(tiles_data, tile_list, zoom)


def _composite_warped(
    base: PIL.Image.Image | None,
    overlay: PIL.Image.Image,
) -> PIL.Image.Image:
    """Alpha-composite *overlay* on top of *base* (both RGBA, same size).

    *base* is None for the first zoom level, in which case *overlay* is
    returned as is.
    """
    if base is None:
        return overlay
    # PIL alpha_composite requires same size and RGBA mode
    result = base.copy()
    result.alpha_composite(overlay)
    return result


def _render_tiles_on_viewport(
    viewport,
    bbox_map_crs,
    crs,
    url_template: str,
    provider_key: str,
    zoom: int,
    alpha: float,
    z_order: int,
    cfg: TileConfig,
    cache_dir: pathlib.Path | None,
) -> None:
    # 1. Convert viewport bbox to EPSG:4326
    try:
        bbox_4326 = _bbox_4326_from_crs(bbox_map_crs, crs)
    except Exception as exc:
        warnings.warn(
            f"Tile: converting the viewport bbox to EPSG:4326 failed "
            f"({exc}); this viewport was skipped. Check that the map data "
            f"has a CRS set."
        )
        return

    # 2. Build list of zoom levels: from coarsest to finest
    n_extra = max(0, int(cfg.extra_zoom_levels))
    zoom_levels = [max(1, zoom - n_extra + i) for i in range(n_extra + 1)]
    # Remove duplicates (e.g. if zoom-n+i < 1 clamps to 1 several times)
    zoom_levels = list(dict.fromkeys(zoom_levels))

    # 3. For each zoom level fetch, warp, and composite (coarse to fine)
    composite: PIL.Image.Image | None = None
    geo_bounds = None
    any_success = False

    for z in zoom_levels:
        result = _fetch_one_zoom(z, bbox_4326, url_template, provider_key, cfg, cache_dir)
        if result is None:
            continue

        mosaic, bounds_3857 = result

        try:
            warped, geo_bounds = _warp_mosaic_to_viewport(
                mosaic, bounds_3857, viewport, crs, cfg.warp_scale
            )
        except Exception as exc:
            warnings.warn(
                f"Tile: warping tiles at zoom {z} failed ({exc}); this "
                f"zoom level was skipped."
            )
            continue

        from PIL import Image
        warped_img = Image.open(io.BytesIO(warped)).convert("RGBA")
        composite = _composite_warped(composite, warped_img)
        any_success = True

    if not any_success or composite is None:
        warnings.warn(
            "Tile: all tile downloads failed, so no basemap tiles were "
            "drawn. Check the network connection or the provider URL."
        )
        return

    # 4. Encode composited image to PNG and embed in SVG
    if geo_bounds is None:  # unreachable: set whenever `composite` is
        return
    buf = io.BytesIO()
    composite.save(buf, format="PNG")
    _place_tile_png(viewport, buf.getvalue(), geo_bounds, alpha, z_order)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_tile(map_obj, cfg: TileConfig) -> None:
    """Add a web tile basemap to all viewports of *map_obj*."""
    _check_mercantile()
    _check_pillow()

    url_template = _resolve_url(cfg.source)
    provider_key  = cfg.source.lower()

    cache_dir: pathlib.Path | None = None
    if cfg.cache:
        base = pathlib.Path(cfg.cache_dir) if cfg.cache_dir else (
            pathlib.Path.home() / ".cache" / "mappyng" / "tiles"
        )
        cache_dir = base

    # Resolve zoom from main viewport bbox
    if cfg.zoom == "auto":
        try:
            w4, s4, e4, n4 = _bbox_4326_from_crs(map_obj.bbox, map_obj.gdf.crs)
            zoom = _auto_zoom(w4, e4, map_obj.width, cfg.zoom_offset)
        except GEO_ERRORS as e:
            zoom = 7 + cfg.zoom_offset
            warnings.warn(
                f"Tile: could not compute the automatic zoom ({e}); "
                f"using zoom {zoom}."
            )
    else:
        zoom = int(cfg.zoom) + cfg.zoom_offset  # type: ignore[call-overload]
    zoom = max(1, min(18, zoom))

    crs = map_obj.gdf.crs

    # Main viewport
    _render_tiles_on_viewport(
        map_obj.main, map_obj.bbox, crs,
        url_template, provider_key, zoom, cfg.opacity, cfg.z_order, cfg, cache_dir,
    )

    # Cartouches
    if cfg.on_cartouches:
        for index, vp in map_obj._cartouche_viewports.items():
            params = map_obj.cartouche_params[index]
            cart_bbox = params["bbox"]
            cart_crs  = params.get("crs", crs)
            _render_tiles_on_viewport(
                vp, cart_bbox, cart_crs,
                url_template, provider_key, zoom, cfg.opacity, cfg.z_order, cfg, cache_dir,
            )

    # Zoom
    if cfg.on_zoom and map_obj._zoom_viewport and map_obj._zoom_bbox:
        _render_tiles_on_viewport(
            map_obj._zoom_viewport, map_obj._zoom_bbox, crs,
            url_template, provider_key, zoom, cfg.opacity, cfg.z_order, cfg, cache_dir,
        )


def list_providers() -> dict[str, str]:
    """Return the registered tile providers."""
    return dict(TILE_PROVIDERS)
