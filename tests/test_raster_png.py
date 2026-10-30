"""The raster PNG encoder needs no imaging library."""

import io

import numpy as np
import pytest

pytest.importorskip("rasterio")
from mappyng.raster import _array_to_png  # noqa: E402


@pytest.mark.parametrize("n_bands, mode", [(1, "RGB"), (3, "RGB"), (4, "RGBA")])
def test_array_to_png_roundtrip(n_bands, mode):
    image = pytest.importorskip("PIL.Image")
    rng = np.random.default_rng(0)
    bands = rng.integers(0, 256, size=(n_bands, 7, 5), dtype=np.uint8)
    png = _array_to_png(bands)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    img = image.open(io.BytesIO(png))
    assert img.mode == mode and img.size == (5, 7)
    expected = np.transpose(np.repeat(bands, 3, axis=0) if n_bands == 1 else bands,
                            (1, 2, 0))
    assert np.array_equal(np.asarray(img), expected)


def test_raster_z_lifts_the_image(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    import geopandas as gpd
    from rasterio.transform import from_bounds
    from shapely.geometry import box

    import mappyng as mp

    tif = tmp_path / "r.tif"
    with rasterio.open(
        tif, "w", driver="GTiff", width=4, height=4, count=3, dtype="uint8",
        crs="EPSG:3857", transform=from_bounds(0, 0, 100, 100, 4, 4),
    ) as dst:
        dst.write(np.full((3, 4, 4), 200, dtype="uint8"))
    gdf = gpd.GeoDataFrame(geometry=[box(0, 0, 100, 100)], crs=3857)

    def svg(z):
        m = mp.Map(gdf, width=200, height=200)
        m += mp.Raster(paths={"r": str(tif)}, z=z)
        m += mp.Vector(gdf, fill="#ff0000")
        return m.to_string()

    below, above = svg(None), svg(10)
    assert below.index("<image") < below.index("#ff0000")
    assert above.index("<image") > above.index("#ff0000")
