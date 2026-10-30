"""
Categorical (qualitative) choropleth for mappyng.

Colours each polygon by a nominal category (an id, a type, a cluster
label...) rather than by classifying a continuous value. Opacity can
separately encode a probability/confidence column, reusing the same
mechanism as :func:`mappyng.choropleth.add_choropleth`.

Example
-------
>>> from mappyng import Map, Category
>>> m = Map(gdf)
>>> m.add(Category(
...     gdf, column="cluster",
...     fill_map={"A": "#1f78b4", "B": "#33a02c", "C": "#e31a1c"},
...     opacity_column="confidence",
... ))
>>> m.render("category.svg")
"""

from __future__ import annotations

import copy
import warnings
from typing import Any

import geopandas as gpd
import numpy as np
from shapely.geometry import box

from . import defaults as D
from .border_contrast import parse_border_contrast, report_weak_borders
from .choropleth import (
    ChoroplethLegendConfig,
    _draw_classified_gdf,
    _draw_legend,
    _draw_nodata_gdf,
    _resolve_opacity_bins,
)
from .choropleth_classify import CategoryReport
from .detail import ZOOM, detail_for, join_detail, normalize_detail
from .renderer import SvgViewport


def add_category(
    map_obj,
    gdf: gpd.GeoDataFrame,
    column: str,
    fill_map: dict[Any, str],
    default_fill: str | None = None,
    default_label: str = "Autre",
    stroke: str | None = None,
    stroke_width: float | None = None,
    legend_params: dict[str, Any] | None = None,
    dissolve: bool = False,
    simplify=None,
    on_zoom: bool = True,
    on_cartouches: bool = True,
    opacity_column: str | None = None,
    min_opacity: float = D.CHOROPLETH_DEFAULT_MIN_OPACITY,
    max_opacity: float = D.CHOROPLETH_DEFAULT_MAX_OPACITY,
    blend_background: str | None = None,
    opacity_bins=None,
    detail: Any = None,
    detail_join: Any = None,
    border_contrast: Any = None,
) -> int:
    """Add a categorical (qualitative) choropleth layer to a Map.

    Parameters
    ----------
    map_obj : mappyng.Map
        The map instance.
    gdf : GeoDataFrame
        Data with geometries and a category column.
    column : str
        Column holding the category (id, type, label...) per feature.
    fill_map : dict
        Mapping ``category -> "#RRGGBB"``. Categories not present in the
        data are simply not drawn in the legend.
    default_fill : str, optional
        Colour for categories present in *column* but absent from
        *fill_map*. Without it, an unmapped category raises ``ValueError``
        (silently falling back would hide a mismatch between data and
        legend).
    default_label : str
        Legend label for the *default_fill* bucket (default ``"Autre"``).
    stroke, stroke_width : optional
        Polygon outline colour/width (defaults from style).
    legend_params : dict or False, optional
        :class:`~mappyng.choropleth.ChoroplethLegendConfig` fields.
        Defaults to a vertical legend with one swatch per category.
    dissolve : bool
        Merge adjacent areas that share a category before drawing.
    simplify : None, "auto" or float
        Geometry simplification, see :func:`mappyng.choropleth.add_choropleth`.
    on_zoom, on_cartouches : bool
        Which viewports to draw on.
    opacity_column : str, optional
        Column holding a probability/confidence in ``[0, 1]``. When set,
        each feature's opacity is driven by this value (linearly mapped
        onto ``[min_opacity, max_opacity]``), so colour encodes the
        category while opacity encodes certainty.
    min_opacity, max_opacity : float
        Opacity bounds for *opacity_column*. Ignored without it.
    blend_background : str, optional
        With *opacity_column*, pre-composite the category colour over this
        ``#RRGGBB`` background and draw an opaque solid fill instead of
        SVG ``fill-opacity``. See :func:`mappyng.choropleth.add_choropleth`.
    opacity_bins : int or list of float, optional
        Discretize *opacity_column* into this many equal-width bins over
        ``[0, 1]`` (or explicit bin edges). With *dissolve*, features
        sharing both category and opacity bin merge into one path instead
        of having their opacity averaged.
    detail : GeoDataFrame or dict, optional
        Finer geometry for the zoom window and the cartouches. Categories and
        colours come from *gdf* and are carried to the finer geometries
        through *detail_join*. See
        :func:`mappyng.choropleth.add_choropleth` and :mod:`mappyng.detail`.
    detail_join : str, tuple or None
        Key shared by *gdf* and the finer geometries (column name, a
        ``(gdf_column, detail_column)`` pair, or None for the index).
    border_contrast : bool, str, dict or BorderContrast, optional
        Make the borders between touching areas of similar colour visible.
        Where two neighbours are both light (or both dark) and the outline is
        too close in tone, the border between them disappears. With
        ``True`` (or ``"fix"``) **only those shared borders** are redrawn on top
        in a contrasting colour; the polygons keep their own outline. Use it
        when two neighbouring categories have close colours.
        ``"check"`` reveals them instead, thick in magenta, and warns with a
        count and examples. A dict or a :class:`~mappyng.BorderContrast` sets
        the thresholds and colours. Default ``None`` (off). See
        :mod:`mappyng.border_contrast`.

    Returns
    -------
    int
        The layer id.
    """
    layer_id = map_obj._next_layer_id("category")

    style = map_obj.style
    stroke = stroke or style["edge_color"]
    sw = stroke_width or style["edge_width"]
    z = style.config.z_order.CHOROPLETH
    border_cfg = parse_border_contrast(border_contrast)

    gdf = gdf.copy()
    nodata = gdf[gdf[column].isna()]
    data = gdf.dropna(subset=[column])

    categories: list[Any] = list(fill_map.keys())
    colors: list[str] = [fill_map[c] for c in categories]

    unmapped = sorted(set(data[column].unique()) - set(categories), key=str)
    if unmapped:
        if default_fill is None:
            raise ValueError(
                f"Category: {len(unmapped)} value(s) in column "
                f"{column!r} have no entry in fill_map: {unmapped}. Add "
                f"them to fill_map, or pass default_fill for a fallback "
                f"colour."
            )
        categories = categories + ["__default__"]
        colors = colors + [default_fill]

    cat_index = {c: i for i, c in enumerate(categories)}
    default_idx = cat_index.get("__default__")
    data = data.copy()
    data["_class"] = data[column].map(lambda v: cat_index.get(v, default_idx))

    counts = np.bincount(data["_class"].to_numpy(dtype=int),
                         minlength=len(categories))
    map_obj._state.classification_reports[layer_id] = CategoryReport(
        column=column, categories=categories,
        counts=[int(c) for c in counts], n_valid=len(data),
        n_excluded=len(nodata), unmapped=unmapped,
    )

    data, opacity_levels = _resolve_opacity_bins(data, opacity_column, opacity_bins)

    full_data = data

    def _finish(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Merge adjacent features of the same class when *dissolve* is set."""
        if not dissolve:
            return frame
        group_keys = ["_class", "_opacity_class"] if opacity_levels else "_class"
        key_cols = group_keys if isinstance(group_keys, list) else [group_keys]
        aggfunc = {
            c: ("mean" if c == opacity_column else "first")
            for c in frame.columns if c not in ("geometry", *key_cols)
        }
        return frame.dissolve(by=group_keys, aggfunc=aggfunc).reset_index()

    data = _finish(full_data)

    # Finer geometry for the zoom and cartouches: same symbology, joined by key.
    details = normalize_detail(detail)
    _detail_cache: dict[int, Any] = {}

    def _data_for(target: Any) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """(data, nodata) frames to draw on *target*."""
        finer = detail_for(details, target)
        if finer is None:
            return data, nodata
        if id(finer) not in _detail_cache:
            _detail_cache[id(finer)] = (
                _finish(join_detail(full_data, finer, detail_join,
                                    what="category")),
                join_detail(nodata, finer, detail_join, what="category"),
            )
        return _detail_cache[id(finer)]

    labels = [str(c) for c in categories]
    if unmapped:
        labels[-1] = default_label

    show_legend = legend_params is not False
    if not show_legend:
        legend_params = None
    if isinstance(legend_params, ChoroplethLegendConfig):
        legend_cfg = copy.copy(legend_params)
    else:
        merged: dict[str, Any] = {"orientation": "vertical",
                                  "label_position": "center",
                                  "labels": labels}
        merged.update(legend_params or {})
        legend_cfg = ChoroplethLegendConfig(**merged)
    legend_cfg.resolve_defaults(style, font_scale=getattr(map_obj, "font_scale", 1.0))
    bins = np.arange(len(colors) + 1, dtype=float)

    border_report: list = []

    def _render_on(viewport: SvgViewport, d: gpd.GeoDataFrame,
                   nd: gpd.GeoDataFrame, clip_bbox: list,
                   report: list | None = None) -> None:
        clip_geom = box(*clip_bbox)
        clipped = d.clip(mask=clip_geom)
        clipped = clipped[~clipped.is_empty] if not clipped.empty else clipped
        if not clipped.empty:
            _draw_classified_gdf(
                viewport, clipped, colors, column, stroke, sw, z, layer_id,
                simplify=simplify, opacity_column=opacity_column,
                min_opacity=min_opacity, max_opacity=max_opacity,
                blend_background=blend_background,
                border_cfg=border_cfg, border_report=report,
            )
        nd_clipped = nd.clip(mask=clip_geom) if not nd.empty else nd
        nd_clipped = nd_clipped[~nd_clipped.is_empty] if not nd_clipped.empty else nd_clipped
        if not nd_clipped.empty:
            _draw_nodata_gdf(viewport, nd_clipped, legend_cfg.hatch_color, sw, z,
                             layer_id, map_obj.svg._defs,
                             hatch_style=legend_cfg.hatch_style, simplify=simplify)

    _render_on(map_obj.main, data, nodata, map_obj.bbox, report=border_report)
    if border_report and border_cfg is not None and border_cfg.mode == "check":
        borders, labels = border_report[0]
        warnings.warn(report_weak_borders(borders, labels, "Category"),
                      UserWarning, stacklevel=2)

    if on_zoom and map_obj._zoom_viewport and map_obj._zoom_bbox:
        zoom_data, zoom_nodata = _data_for(ZOOM)
        _render_on(map_obj._zoom_viewport, zoom_data, zoom_nodata,
                   map_obj._zoom_bbox)

    if on_cartouches:
        for index, vp in map_obj._cartouche_viewports.items():
            params = map_obj.cartouche_params[index]
            cart_frame, cart_nodata = _data_for(index)
            cart_data = map_obj._prepare_cartouche_data(cart_frame, params)
            cart_nd = map_obj._prepare_cartouche_data(cart_nodata, params)
            if not cart_data.empty:
                _draw_classified_gdf(
                    vp, cart_data, colors, column, stroke, sw, z, layer_id,
                    simplify=simplify, opacity_column=opacity_column,
                    min_opacity=min_opacity, max_opacity=max_opacity,
                    blend_background=blend_background,
                    border_cfg=border_cfg,
                )
            if not cart_nd.empty:
                _draw_nodata_gdf(vp, cart_nd, legend_cfg.hatch_color, sw, z, layer_id,
                                 map_obj.svg._defs, hatch_style=legend_cfg.hatch_style,
                                 simplify=simplify)

    if show_legend:
        _draw_legend(map_obj.svg, colors, bins, legend_cfg, not nodata.empty,
                     map_obj.main, map_obj, values=None)

    return layer_id
