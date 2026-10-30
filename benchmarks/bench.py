"""Render-time and SVG-size benchmarks on representative workloads.

Run ``python benchmarks/bench.py`` (add ``--md`` for a Markdown table).
Every case is rendered ``REPEAT`` times; the median is reported. "Communes"
is a synthetic grid of jittered polygons (no external data), sized like
metropolitan France's ~35 000 communes; "detailed" is the same grid with
densified boundaries.
"""

from __future__ import annotations

import argparse
import os
import platform
import statistics
import tempfile
import time
import warnings

import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon

import mappyng as mp
from mappyng.data import load_europe, load_france_departments

REPEAT = 3
warnings.simplefilter("ignore")


def grid(n_side: int, vertices_per_edge: int = 1, seed: int = 0) -> gpd.GeoDataFrame:
    """n_side x n_side jittered quadrilaterals sharing vertices (EPSG:3857)."""
    rng = np.random.default_rng(seed)
    xs = np.linspace(-500_000, 1_000_000, n_side + 1)
    ys = np.linspace(5_100_000, 6_600_000, n_side + 1)
    jx = rng.normal(0, 1_500_000 / n_side / 6, (n_side + 1, n_side + 1))
    jy = rng.normal(0, 1_500_000 / n_side / 6, (n_side + 1, n_side + 1))
    X = xs[None, :] + jx
    Y = ys[:, None] + jy
    polys = []
    t = np.linspace(0, 1, vertices_per_edge + 1)[:-1]
    for i in range(n_side):
        for j in range(n_side):
            c = [(X[i, j], Y[i, j]), (X[i, j + 1], Y[i, j + 1]),
                 (X[i + 1, j + 1], Y[i + 1, j + 1]), (X[i + 1, j], Y[i + 1, j])]
            ring = []
            for a, b in zip(c, c[1:] + c[:1]):
                for s in t:
                    ring.append((a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s))
            polys.append(Polygon(ring))
    gdf = gpd.GeoDataFrame({"v": rng.random(len(polys))}, geometry=polys, crs=3857)
    gdf["name"] = [f"C{i}" for i in range(len(gdf))]
    return gdf


def choropleth_map(gdf, **kw):
    return (mp.Map(gdf, width=900, height="auto")
            + mp.Basemap() + mp.Choropleth(gdf, column="v", **kw))


def labelled_map(gdf, n):
    pts = gdf.iloc[:n]
    return (mp.Map(gdf, width=900, height="auto") + mp.Basemap()
            + mp.Label(pts, column="name"))


def cases():
    deps = load_france_departments()
    deps = deps[deps["COD_GEO"].str.len() == 2].copy()
    deps["v"] = np.random.default_rng(1).random(len(deps))
    deps["name"] = deps["LIB_GEO"]
    eur = load_europe()
    eur["v"] = np.random.default_rng(2).random(len(eur))
    communes = grid(190)                      # ~36 000 polygons
    detailed = grid(60, vertices_per_edge=25)  # 3 600 polygons, 100 vertices each
    yield "Basemap, departments", deps, lambda: mp.Map(deps, width=900, height="auto") + mp.Basemap()
    yield "Choropleth, departments", deps, lambda: choropleth_map(deps)
    yield "Choropleth, Europe (94)", eur, lambda: choropleth_map(eur)
    yield "Choropleth, 36 000 synthetic communes", communes, lambda: choropleth_map(communes)
    yield "Choropleth, 3 600 polygons x 100 vertices", detailed, lambda: choropleth_map(detailed)
    yield 'Choropleth, communes, simplify="auto"', communes, lambda: choropleth_map(communes, simplify="auto")
    yield "96 labels on departments", deps, lambda: labelled_map(deps, 96)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", action="store_true", help="Markdown table")
    args = ap.parse_args()
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for name, gdf, build in cases():
            times, size = [], 0
            for _ in range(REPEAT):
                path = os.path.join(tmp, "b.svg")
                t0 = time.perf_counter()
                build().render(path)
                times.append(time.perf_counter() - t0)
                size = os.path.getsize(path)
            n_vert = int(gdf.geometry.get_coordinates().shape[0])
            rows.append((name, len(gdf), n_vert, statistics.median(times), size / 1024))
    head = f"mappyng {mp.__version__}, Python {platform.python_version()}, {platform.machine()}, median of {REPEAT}"
    if args.md:
        print(head + "\n")
        print("| Case | Features | Vertices | Render (s) | SVG (KiB) |\n|---|---:|---:|---:|---:|")
        for r in rows:
            print(f"| {r[0]} | {r[1]:,} | {r[2]:,} | {r[3]:.2f} | {r[4]:,.0f} |")
    else:
        print(head)
        for r in rows:
            print(f"{r[0]:<48} {r[1]:>7,} feat {r[2]:>9,} vtx {r[3]:>7.2f} s {r[4]:>9,.0f} KiB")


if __name__ == "__main__":
    main()
