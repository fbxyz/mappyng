"""Snapshot tests for legend SVG output.

Each case renders a map and compares the legend markup (the ``*-legend``
groups and their hatch patterns) with the stored snapshot in
``tests/snapshots/legends.json``. They guard the legend layout code against
unintended changes.

After an intentional change, review the diff and regenerate the snapshots::

    UPDATE_SNAPSHOTS=1 pytest tests/test_legend_snapshots.py
"""

import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest

from mappyng import FactorLegend, Map
from mappyng.layers import Category, Choropleth, Proportional

SNAPSHOT_FILE = Path(__file__).parent / "snapshots" / "legends.json"
UPDATE = bool(os.environ.get("UPDATE_SNAPSHOTS"))

FRAME = {"padding": 8, "stroke": "#f00"}
FILL_MAP = {"A": "#e41a1c", "B": "#377eb8", "C": "#4daf4a", "D": "#984ea3"}

CHOROPLETH_CASES = {
    "horizontal_default": {},
    "horizontal_title_subtitle_frame": {
        "title": "Titre de légende", "subtitle": "sous-titre", "frame": True},
    "horizontal_center_range": {
        "label_position": "center", "label_format": "range", "decimals": 1},
    "horizontal_center_value": {"label_position": "center"},
    "horizontal_custom_labels": {
        "label_position": "center", "labels": ["a", "b", "c", "d", "e"]},
    "horizontal_rotated_border": {"label_rotation": 30, "label_anchor": "end"},
    "horizontal_rotated_center": {
        "label_position": "center", "label_rotation": -45},
    "horizontal_rounded_swatches": {
        "swatch_shape": "rounded", "swatch_width": 40, "swatch_height": 12},
    "horizontal_circle_swatches": {"swatch_shape": "circle"},
    "horizontal_histogram": {"histogram": True, "frame": FRAME},
    "horizontal_separators": {
        "thousands_sep": ",", "decimal_sep": ",", "decimals": 2},
    "horizontal_manual_position": {"position": {"x": 0.7, "y": 0.2}},
    "horizontal_fonts": {
        "fontsize": 13, "fontcolor": "#123", "fontfamily": "serif"},
    "vertical_default": {"orientation": "vertical"},
    "vertical_title_frame": {
        "orientation": "vertical", "title": "Titre", "frame": FRAME},
    "vertical_frame_padding_dict": {
        "orientation": "vertical",
        "frame": {"padding": {"top": 3, "left": 20}, "fill": "#eee"}},
    "vertical_center_range": {
        "orientation": "vertical", "label_position": "center",
        "label_format": "range", "decimals": 1},
    "vertical_center_value": {
        "orientation": "vertical", "label_position": "center"},
    "vertical_custom_labels": {
        "orientation": "vertical", "labels": ["a", "b", "c", "d", "e"]},
    "vertical_histogram": {"orientation": "vertical", "histogram": True},
    "vertical_circle_swatches": {
        "orientation": "vertical", "swatch_shape": "circle",
        "vertical_swatch_width": 30, "vertical_label_gap": 11},
}
NODATA_OPTIONS = {"nodata_label": "Pas de données"}

FACTOR_CASES = {
    "factor_vertical_default": {},
    "factor_vertical_poles": {
        "title": "Facteur 1", "variance": 0.5,
        "pole_high": "Haut pôle assez long pour passer à la ligne",
        "pole_low": "Bas", "note": "une note"},
    "factor_horizontal": {"orientation": "horizontal"},
    "factor_horizontal_frame": {
        "orientation": "horizontal", "frame": True, "title": "x",
        "pole_fontsize": 9, "pole_high": "Haut", "pole_low": "Bas",
        "label_rotation": 30},
}

CATEGORY_CASES = {
    "category_default": None,
    "category_horizontal": {"orientation": "horizontal"},
    "category_frame": {"frame": True, "title": "Catégorie"},
}

PROPORTIONAL_CASES = {
    "proportional_nested": {},
    "proportional_nested_frame": {"frame": True, "title": "Pop."},
    "proportional_vertical": {"orientation": "vertical"},
    "proportional_vertical_frame": {
        "orientation": "vertical", "frame": {"padding": 6}, "subtitle": "hab."},
    "proportional_horizontal": {"orientation": "horizontal"},
    "proportional_horizontal_options": {
        "orientation": "horizontal", "number_format": "none", "decimals": 1,
        "circle_fill": "#abc", "circle_spacing": 7, "values": [1e4, 1e5, 5e5]},
    "proportional_manual_position": {
        "position": {"x": 0.1, "y": 0.5}, "num_values": 4},
}


@pytest.fixture(scope="module")
def gdf(gdf_departments_module):
    g = gdf_departments_module.copy()
    n = len(g)
    g["v"] = np.linspace(-3, 3, n) ** 3
    g["vn"] = g["v"]
    g.loc[g.index[:7], "vn"] = np.nan
    g["cat"] = [("A", "B", "C", "D")[i % 4] for i in range(n)]
    g["pop"] = np.linspace(1_000, 1_000_000, n)
    return g


@pytest.fixture(scope="module")
def gdf_departments_module():
    from mappyng.data import load_france_departments
    return load_france_departments().to_crs(2154)


def _dump(el, depth=0):
    """Canonical text form of an element, independent of namespace prefixes.

    ``ET.tostring`` output depends on process-wide namespace registration
    (``ET.register_namespace``), so serialise by hand instead.
    """
    tag = el.tag.rsplit("}", 1)[-1]
    attrs = "".join(f' {k}="{v}"' for k, v in el.attrib.items())
    text = (el.text or "").strip()
    pad = "  " * depth
    if len(el) == 0:
        return f"{pad}<{tag}{attrs}>{text}</{tag}>"
    inner = "\n".join(_dump(child, depth + 1) for child in el)
    return f"{pad}<{tag}{attrs}>{text}\n{inner}\n{pad}</{tag}>"


def _legend_markup(svg: str) -> str:
    """Serialise the legend groups and legend hatch patterns of an SVG."""
    root = ET.fromstring(svg)
    parts = []
    for el in root.iter():
        el_id = el.get("id") or ""
        if el_id.endswith("-legend") or el_id.startswith("hatch-legend"):
            parts.append(_dump(el))
    return "\n".join(parts)


def _render(build, gdf):
    m = Map(gdf, width=800, height=700)
    build(m)
    return _legend_markup(m.to_string())


def _all_cases(gdf):
    cases = {}
    for name, legend in CHOROPLETH_CASES.items():
        cases[name] = lambda m, lg=legend: m.add(Choropleth(
            gdf, column="v", method="Quantiles", num_classes=5, legend=lg))
        cases[name + "_nodata"] = lambda m, lg=legend: m.add(Choropleth(
            gdf, column="vn", method="Quantiles", num_classes=5,
            legend={**lg, **NODATA_OPTIONS}))
    for name, legend in FACTOR_CASES.items():
        cases[name] = lambda m, lg=legend: m.add(Choropleth(
            gdf, column="v", cmap="RdYlGn", method="Quantiles",
            num_classes=5, legend=FactorLegend(**lg)))
    cases["factor_vertical_nodata"] = lambda m: m.add(Choropleth(
        gdf, column="vn", cmap="RdYlGn", method="Quantiles", num_classes=5,
        legend=FactorLegend()))
    cases["factor_horizontal_nodata"] = lambda m: m.add(Choropleth(
        gdf, column="vn", cmap="RdYlGn", method="Quantiles", num_classes=5,
        legend=FactorLegend(orientation="horizontal")))
    for name, legend in CATEGORY_CASES.items():
        kw = {} if legend is None else {"legend": legend}
        cases[name] = lambda m, kw=kw: m.add(
            Category(gdf, column="cat", fill_map=FILL_MAP, **kw))
    for name, legend in PROPORTIONAL_CASES.items():
        cases[name] = lambda m, lg=legend: m.add(
            Proportional(_centroids(gdf), column="pop", legend=lg))
    return cases


def _centroids(gdf):
    pts = gdf.copy()
    pts["geometry"] = pts.geometry.centroid
    return pts


def _load_snapshots():
    if SNAPSHOT_FILE.exists():
        return json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    return {}


def test_legend_snapshots(gdf):
    cases = _all_cases(gdf)
    actual = {name: _render(build, gdf) for name, build in cases.items()}

    if UPDATE:
        SNAPSHOT_FILE.write_text(
            json.dumps(actual, indent=1, sort_keys=True, ensure_ascii=False)
            + "\n", encoding="utf-8")
        pytest.skip("snapshots updated")

    expected = _load_snapshots()
    assert set(actual) == set(expected), (
        "snapshot cases changed; regenerate with UPDATE_SNAPSHOTS=1")
    changed = [name for name in sorted(actual) if actual[name] != expected[name]]
    assert not changed, (
        f"legend markup changed for {len(changed)} case(s): {changed}. "
        f"If intentional, regenerate with UPDATE_SNAPSHOTS=1")
    for name, markup in actual.items():
        assert markup, f"{name}: no legend markup was rendered"
