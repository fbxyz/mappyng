"""Build the small Natural Earth rasters used by the gallery.

Natural Earth I with shaded relief and water (public domain) is downloaded
once, then warped to the CRS of each example and written as a compact
GeoTIFF in ``docs/examples/data``:

* ``relief_france_2154.tif``: mainland France, Lambert-93;
* ``relief_globe_ortho.tif``: the orthographic globe of ``plot_13_globe.py``.

Run from the repository root: ``python docs/make_rasters.py [NE1_LR_LC_SR_W_DR.tif]``.
Without an argument, the 193 MB archive is fetched from naturalearthdata.com.
"""

import io
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject

URL = "https://naturalearth.s3.amazonaws.com/10m_raster/NE1_LR_LC_SR_W_DR.zip"
OUT = Path(__file__).resolve().parent / "examples" / "data"

R = 6378137.0
LON0, LAT0 = 0, 12      # centre of the globe, as in plot_13_globe.py
ORTHO = f"+proj=ortho +lat_0={LAT0} +lon_0={LON0} +ellps=WGS84 +units=m +no_defs"


def source(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    tif = Path("NE1_LR_LC_SR_W_DR.tif")
    if not tif.exists():
        with urllib.request.urlopen(URL) as resp:
            data = resp.read()
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            zf.extract("NE1_LR_LC_SR_W_DR.tif", ".")
    return tif


def warp(src_path: Path, crs, bounds, width, height, dst_path: Path) -> None:
    """Warp the RGB source to *crs* over *bounds*, with an alpha band."""
    transform = from_bounds(*bounds, width, height)
    dst = np.zeros((4, height, width), dtype="uint8")
    with rasterio.open(src_path) as src:
        rgb = src.read([1, 2, 3])
        alpha = np.full((1, src.height, src.width), 255, dtype="uint8")
        data = np.concatenate([rgb, alpha])
        reproject(
            data, dst,
            src_transform=src.transform, src_crs=src.crs,
            dst_transform=transform, dst_crs=crs,
            resampling=Resampling.bilinear,
        )
    with rasterio.open(
        dst_path, "w", driver="GTiff", width=width, height=height, count=4,
        dtype="uint8", crs=crs, transform=transform,
        compress="deflate", predictor=2, photometric="RGB",
        alpha="YES",
    ) as out:
        out.write(dst)
    print("wrote", dst_path, round(dst_path.stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    tif = source(sys.argv[1] if len(sys.argv) > 1 else None)
    OUT.mkdir(parents=True, exist_ok=True)
    # Mainland France frame (BBOX of the gallery) with a small margin.
    warp(tif, CRS.from_epsg(2154), (60000, 6010000, 1310000, 7180000),
         1000, 936, OUT / "relief_france_2154.tif")
    warp(tif, CRS.from_string(ORTHO), (-R, -R, R, R),
         1100, 1100, OUT / "relief_globe_ortho.tif")
