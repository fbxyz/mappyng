"""
Raster background module for mappyng.

Embeds GeoTIFF files (MNT, relief, satellite imagery...) as base64 PNG
``<image>`` elements inside SVG viewports.

The raster must share the same CRS as the viewport it is rendered in.
No reprojection is performed, the GeoTIFF is windowed (cropped) to
the viewport's geographic bounds and placed at the correct SVG
coordinates.

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
import io

import numpy as np
import rasterio
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
) -> tuple[bytes | None, tuple[float, float, float, float]]:
    """Read the portion of *ds* that intersects *bbox* and return PNG bytes.

    Returns (png_bytes, actual_bounds) or (None, ...) if no overlap.
    *actual_bounds* is (minx, miny, maxx, maxy) of the actual window read.
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

    # Read bands
    bands = ds.read(window=int_window)  # shape: (bands, h, w)

    # Build RGBA or RGB PNG via PIL-free approach (raw PNG with numpy)
    png_bytes = _array_to_png(bands)
    return png_bytes, (act_minx, act_miny, act_maxx, act_maxy)


def _array_to_png(bands: np.ndarray) -> bytes:
    """Convert a (bands, h, w) uint8 array to PNG bytes.

    Supports 3-band (RGB) and 4-band (RGBA) input.
    Uses matplotlib's imsave for simplicity.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if bands.shape[0] == 4:
        img = np.transpose(bands, (1, 2, 0))  # (h, w, 4)
    elif bands.shape[0] == 3:
        img = np.transpose(bands, (1, 2, 0))  # (h, w, 3)
    elif bands.shape[0] == 1:
        # Grayscale to RGB
        gray = bands[0]
        img = np.stack([gray, gray, gray], axis=-1)
    else:
        img = np.transpose(bands[:3], (1, 2, 0))

    buf = io.BytesIO()
    plt.imsave(buf, img, format="png")
    buf.seek(0)
    return buf.read()


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
    paths: dict[str, str],
    opacity: float = 1.0,
    on_zoom: bool = True,
    on_cartouches: bool = True,
) -> None:
    """Add raster backgrounds to a Map.

    Parameters
    ----------
    map_obj : mappyng.Map
        The map instance.
    paths : dict
        Mapping of region names to GeoTIFF file paths.
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
    """
    z_order = D.Z_RASTER

    # Open all raster files
    datasets: dict[str, rasterio.DatasetReader] = {}
    try:
        for key, path in paths.items():
            datasets[key] = rasterio.open(path)

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
    png_bytes, actual_bounds = _read_window_png(ds, bbox)
    if png_bytes is None:
        return

    _place_raster(viewport, png_bytes, actual_bounds, alpha, z_order)
