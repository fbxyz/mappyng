"""
Raster background module for mappyng.

Embeds GeoTIFF files (MNT, relief, satellite imagery...) as base64 PNG
``<image>`` elements inside SVG viewports.

The raster must share the same CRS as the viewport it is rendered in.
No reprojection is performed, the GeoTIFF is windowed (cropped) to
the viewport's geographic bounds and placed at the correct SVG
coordinates. A raster in another CRS is skipped with a warning.

The image is resampled down to the resolution the viewport can show,
pixels without data are transparent, and rasters that are not 8-bit
(elevation models, 16-bit images) are stretched to the 0-255 range.

Multiple raster files can be supplied so that each viewport (main map,
cartouches, zoom) picks the one whose footprint overlaps its bbox.

All default values are imported from :mod:`mappyng.defaults`.

Example
-------
>>> from mappyng import Raster
>>> m.add(Raster(
...     paths={
...         "metropole": "data/MNT/BDTOPO2018_gen3_NC.tif",
...         "antilles":  "data/MNT/antilles.tif",
...         "guyane":    "data/MNT/guyane.tif",
...         "reunion":   "data/MNT/reunion.tif",
...     },
...     opacity=0.6,
... ))
"""

from __future__ import annotations

import base64
import os
import struct
import warnings
import zlib

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import from_bounds as window_from_bounds

from . import defaults as D
from .renderer import SvgViewport


def _raster_overlaps_bbox(
    ds: rasterio.DatasetReader,
    bbox: list[float],
) -> bool:
    """Check if a rasterio dataset overlaps the given bbox."""
    rb = ds.bounds
    bx0, by0, bx1, by1 = bbox
    return not (rb.right < bx0 or rb.left > bx1 or
                rb.top < by0 or rb.bottom > by1)


def _read_window_png(
    ds: rasterio.DatasetReader,
    bbox: list[float],
    max_size: tuple[int, int] | None = None,
) -> tuple[bytes | None, tuple[float, float, float, float]]:
    """Read the portion of *ds* that intersects *bbox* and return PNG bytes.

    Parameters
    ----------
    ds : rasterio dataset
        The opened raster.
    bbox : list of float
        Geographic window to read, in the raster CRS.
    max_size : (width, height), optional
        Largest useful image size in pixels. A window with more pixels is
        resampled down to it while reading, so a large raster does not bloat
        the SVG.

    Returns (png_bytes, actual_bounds) or (None, ...) if no overlap.
    *actual_bounds* is (minx, miny, maxx, maxy) of the actual window read.
    Pixels without data (nodata value, mask or alpha band) are transparent.
    """
    rb = ds.bounds

    # Clamp bbox to raster extent
    win_minx = max(bbox[0], rb.left)
    win_miny = max(bbox[1], rb.bottom)
    win_maxx = min(bbox[2], rb.right)
    win_maxy = min(bbox[3], rb.top)

    if win_minx >= win_maxx or win_miny >= win_maxy:
        return None, (0, 0, 0, 0)

    # Compute rasterio window
    window = window_from_bounds(
        win_minx, win_miny, win_maxx, win_maxy, ds.transform,
    )

    # Round to integer pixel boundaries
    row_off = max(0, int(window.row_off))
    col_off = max(0, int(window.col_off))
    row_end = min(ds.height, int(window.row_off + window.height) + 1)
    col_end = min(ds.width, int(window.col_off + window.width) + 1)
    win_h = row_end - row_off
    win_w = col_end - col_off

    if win_h <= 0 or win_w <= 0:
        return None, (0, 0, 0, 0)

    int_window = rasterio.windows.Window(col_off, row_off, win_w, win_h)

    # Recompute actual geographic bounds from integer window
    actual_bounds = rasterio.windows.bounds(int_window, ds.transform)
    # bounds returns (left, bottom, right, top)
    act_minx, act_miny, act_maxx, act_maxy = actual_bounds

    # Resample down while reading when the window holds more pixels than
    # the viewport can show.
    out_h, out_w = win_h, win_w
    if max_size is not None:
        ratio = max(win_w / max(max_size[0], 1), win_h / max(max_size[1], 1))
        if ratio > 1:
            out_w = max(1, round(win_w / ratio))
            out_h = max(1, round(win_h / ratio))
    resampled = (out_h, out_w) != (win_h, win_w)
    bands = ds.read(
        window=int_window, out_shape=(ds.count, out_h, out_w),
        resampling=Resampling.average if resampled else Resampling.nearest,
    )  # shape: (bands, h, w)
    mask = ds.dataset_mask(window=int_window, out_shape=(out_h, out_w))

    png_bytes = _array_to_png(_to_uint8(bands, mask), mask)
    return png_bytes, (act_minx, act_miny, act_maxx, act_maxy)


def _to_uint8(bands: np.ndarray, mask: np.ndarray | None = None) -> np.ndarray:
    """Return *bands* as uint8, stretching other data types to 0-255.

    Rasters that are not 8-bit (an elevation model in metres, a 16-bit
    image...) are stretched linearly from the lowest to the highest valid
    value, all bands together so the colours keep their balance. Pixels
    masked out by *mask* (0 = no data) and non-finite values are ignored
    when looking for the range.
    """
    if bands.dtype == np.uint8:
        return bands
    data = bands.astype(np.float64)
    valid = np.isfinite(data)
    if mask is not None:
        valid &= (mask > 0)[None, :, :]
    if not valid.any():
        return np.zeros(bands.shape, dtype=np.uint8)
    lo, hi = float(data[valid].min()), float(data[valid].max())
    if hi <= lo:
        return np.where(valid, 255, 0).astype(np.uint8)
    scaled = np.clip((data - lo) / (hi - lo), 0.0, 1.0) * 255.0
    return np.where(valid, np.round(scaled), 0).astype(np.uint8)


def _array_to_png(bands: np.ndarray, mask: np.ndarray | None = None) -> bytes:
    """Convert a (bands, h, w) uint8 array to PNG bytes.

    Supports 1-band (grayscale), 2-band (grayscale + alpha), 3-band (RGB)
    and 4-band (RGBA) input; any other band count keeps the first three
    bands. *mask* is an optional (h, w) array where 0 marks pixels without
    data: they become transparent. The PNG is encoded with :mod:`zlib`
    only, so no imaging library is needed.
    """
    bands = bands.astype(np.uint8)
    count = bands.shape[0]
    alpha = None
    if count in (1, 2):
        rgb = np.repeat(bands[:1], 3, axis=0)
        if count == 2:
            alpha = bands[1]
    else:
        rgb = bands[:3]
        if count == 4:
            alpha = bands[3]
    if mask is not None and (mask == 0).any():
        opaque = np.where(mask > 0, 255, 0).astype(np.uint8)
        alpha = opaque if alpha is None else np.minimum(alpha, opaque)
    if alpha is not None:
        rgb = np.concatenate([rgb, alpha[None]], axis=0)
    img = np.ascontiguousarray(np.transpose(rgb, (1, 2, 0)))
    height, width, channels = img.shape
    color_type = 6 if channels == 4 else 2

    # One filter byte (0 = none) in front of every scanline.
    raw = np.concatenate(
        [np.zeros((height, 1), dtype=np.uint8), img.reshape(height, -1)],
        axis=1,
    ).tobytes()

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return (struct.pack(">I", len(data)) + body
                + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _place_raster(
    viewport: SvgViewport,
    png_bytes: bytes,
    bounds: tuple[float, float, float, float],
    alpha: float,
    z_order: int,
) -> None:
    """Place a raster PNG into a viewport at the correct geographic position."""
    vb = viewport.viewbox
    minx, miny, maxx, maxy = bounds

    # Convert geographic bounds to SVG coordinates
    sx0, sy0 = vb.geo_to_svg(minx, maxy)  # top-left (geo max-y to svg min-y)
    sx1, sy1 = vb.geo_to_svg(maxx, miny)  # bottom-right

    sw = sx1 - sx0
    sh = sy1 - sy0
    if sw <= 0 or sh <= 0:
        return

    href = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")

    attrs = {"preserveAspectRatio": "none"}
    if alpha < 1.0:
        attrs["opacity"] = f"{alpha:.2f}"

    viewport.add_image(
        "raster", sx0, sy0, sw, sh, href,
        z_order=z_order, **attrs,
    )


def _same_crs(a, b) -> bool:
    """Whether two CRS objects (rasterio, pyproj...) describe the same CRS."""
    from pyproj import CRS
    try:
        return CRS.from_user_input(a) == CRS.from_user_input(b)
    except Exception:  # noqa: BLE001 - unreadable CRS: do not block drawing
        return True


def _crs_name(crs) -> str:
    """Short readable name of a CRS (``EPSG:2154`` when it has a code)."""
    from pyproj import CRS
    try:
        parsed = CRS.from_user_input(crs)
        code = parsed.to_epsg()
        return f"EPSG:{code}" if code else parsed.name
    except Exception:  # noqa: BLE001
        return str(crs)


def _find_matching_raster(
    raster_datasets: dict[str, rasterio.DatasetReader],
    bbox: list[float],
) -> str | None:
    """Find the raster key whose footprint overlaps *bbox*, or None."""
    for key, ds in raster_datasets.items():
        if _raster_overlaps_bbox(ds, bbox):
            return key
    return None


# ============================================================================
# Public API, integrated into Map
# ============================================================================

def add_raster(
    map_obj,
    paths: dict[str, str] | str,
    opacity: float = 1.0,
    on_zoom: bool = True,
    on_cartouches: bool = True,
    z: int | None = None,
) -> None:
    """Add raster backgrounds to a Map.

    Parameters
    ----------
    map_obj : mappyng.Map
        The map instance.
    paths : dict or str
        Mapping of region names to GeoTIFF file paths, or a single path.
        Each viewport (main, cartouche, zoom) picks the raster whose
        geographic footprint overlaps its bbox.  Example::

            {
                "metropole": "/path/to/BDTOPO2018_gen3_NC.tif",
                "antilles":  "/path/to/antilles.tif",
                "reunion":   "/path/to/reunion.tif",
                "guyane":    "/path/to/guyane.tif",
            }
    opacity : float
        Raster opacity (0-1, default 1.0).
    on_zoom : bool
        Render on zoom viewport (default True).
    on_cartouches : bool
        Render on cartouche viewports (default True).
    z : int, optional
        Stacking depth. By default the raster is drawn behind every other
        layer; a larger value lifts it above lower layers.
    """
    z_order = D.Z_RASTER if z is None else z
    if isinstance(paths, (str, os.PathLike)):
        paths = {"raster": paths}
    if not isinstance(paths, dict) or not paths:
        raise ValueError(
            f"Raster: paths must be a GeoTIFF path or a dict mapping a name "
            f"to a GeoTIFF path, got {paths!r}."
        )
    for key, path in paths.items():
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Raster: the file for {key!r} does not exist: {path}"
            )

    # Open all raster files
    datasets: dict[str, rasterio.DatasetReader] = {}
    try:
        map_crs = map_obj.gdf.crs
        for key, path in paths.items():
            ds = rasterio.open(path)
            if (ds.crs is not None and map_crs is not None
                    and not _same_crs(ds.crs, map_crs)):
                ds.close()
                warnings.warn(
                    f"Raster {key!r} is in {_crs_name(ds.crs)} but the map "
                    f"is in {_crs_name(map_crs)}. Rasters are not "
                    f"reprojected, so it is not drawn. Reproject the file to "
                    f"the map CRS first (for example with gdalwarp).",
                    UserWarning, stacklevel=2,
                )
                continue
            datasets[key] = ds

        # --- Main viewport ---
        _render_raster_on_viewport(
            map_obj.main, map_obj.bbox, datasets, opacity, z_order,
        )

        # --- Cartouches ---
        if on_cartouches:
            for index, vp in map_obj._cartouche_viewports.items():
                params = map_obj.cartouche_params[index]
                cart_bbox = params["bbox"]
                _render_raster_on_viewport(
                    vp, cart_bbox, datasets, opacity, z_order,
                )

        # --- Zoom ---
        if on_zoom and map_obj._zoom_viewport and map_obj._zoom_bbox:
            _render_raster_on_viewport(
                map_obj._zoom_viewport, map_obj._zoom_bbox,
                datasets, opacity, z_order,
            )
    finally:
        for ds in datasets.values():
            ds.close()


def _render_raster_on_viewport(
    viewport: SvgViewport,
    bbox: list[float],
    datasets: dict[str, rasterio.DatasetReader],
    alpha: float,
    z_order: int,
) -> None:
    """Render the matching raster on a single viewport."""
    key = _find_matching_raster(datasets, bbox)
    if key is None:
        return

    ds = datasets[key]
    vb = viewport.viewbox
    max_size = (
        max(1, round(vb.content_width * D.RASTER_PIXEL_RATIO)),
        max(1, round(vb.content_height * D.RASTER_PIXEL_RATIO)),
    )
    png_bytes, actual_bounds = _read_window_png(ds, bbox, max_size)
    if png_bytes is None:
        return

    _place_raster(viewport, png_bytes, actual_bounds, alpha, z_order)
