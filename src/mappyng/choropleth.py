"""
Choropleth map visualization for mappyng.

Handles data classification (via mapclassify) and SVG rendering of
colored polygons on all viewports (main, cartouches, zoom).

Each polygon gets SVG attributes:
- id: based on GeoDataFrame index for later filtering/interactivity
- class: CSS class "choropleth choropleth-{class_index}"
- data-value: original data value for tooltips

All default values are imported from :mod:`mappyng.defaults`.

Example
-------
>>> from mappyng import Map, Basemap, Choropleth
>>> m = Map(gdf)
>>> m.add(Basemap())
>>> m.add(Choropleth(gdf, column="population", method="Quantiles", cmap="YlOrRd"))
>>> m.render("choropleth.svg")
"""

from __future__ import annotations

import copy
import warnings
from typing import Any

import geopandas as gpd
from shapely.geometry import box

from . import defaults as D
from .border_contrast import (
    BorderContrast,
    draw_weak_borders,
    find_weak_borders,
    parse_border_contrast,
    report_weak_borders,
)
from .choropleth_classify import (  # noqa: F401 - re-exported for compatibility
    METHODS,
    ClassificationReport,
    _looks_like_stock,
    _resolve_colors,
    _resolve_colors_with_fallback,
    _resolve_num_classes,
    _resolve_opacity_bins,
    _resolve_stdmean_k,
    build_report,
    classify,
    palette_adjustment,
)
from .choropleth_legend import (  # noqa: F401 - re-exported for compatibility
    ChoroplethLegendConfig,
    FactorLegend,
    _draw_factor_legend,
    _draw_legend,
    _draw_legend_histogram,
    _format_range_label,
)
from .config import alpha_blend_hex
from .detail import ZOOM, detail_for, join_detail, normalize_detail
from .legend import ensure_hatch_pattern
from .renderer import SvgViewport, geometry_to_paths

# ============================================================================
# SVG rendering helpers
# ============================================================================

def _resolve_tolerance(simplify, viewport: SvgViewport) -> float | None:
    """Resolve a simplification tolerance in CRS units for one viewport.

    Parameters
    ----------
    simplify : None, "auto" or float
        ``None`` disables simplification. ``"auto"`` targets half a pixel
        at the viewport scale. A number is used directly as a tolerance in
        the data CRS units.
    viewport : SvgViewport
        The viewport whose scale sets the pixel size for ``"auto"``.

    Returns
    -------
    float or None
        The tolerance, or ``None`` when simplification is off or the scale
        is unusable.
    """
    if simplify is None:
        return None
    if isinstance(simplify, str):
        if simplify != "auto":
            raise ValueError(
                f"simplify must be None, 'auto' or a number, got "
                f"{simplify!r}. Use 'auto' to target half a pixel at the "
                f"render scale, or pass a tolerance in the data CRS units."
            )
        scale = getattr(viewport.viewbox, "scale", 0.0)
        if not scale or scale <= 0:
            return None
        return D.SIMPLIFY_AUTO_PIXELS / scale
    return float(simplify)


def _simplify_gdf(gdf: gpd.GeoDataFrame, simplify,
                  viewport: SvgViewport) -> gpd.GeoDataFrame:
    """Return a copy of *gdf* with geometries simplified for *viewport*.

    Uses Douglas-Peucker with topology preserved within each geometry.
    Borders shared between separate features are simplified independently,
    so gaps can appear between neighbours when the data is not dissolved.
    If the tolerance would empty a geometry, the original is kept and a
    non-blocking warning is emitted.
    """
    tol = _resolve_tolerance(simplify, viewport)
    if not tol or gdf.empty:
        return gdf
    simplified = gdf.geometry.simplify(tol, preserve_topology=True)
    emptied = simplified.is_empty | simplified.isna()
    if emptied.any():
        warnings.warn(
            f"simplify: tolerance {tol:.4g} emptied "
            f"{int(emptied.sum())} geometry(ies); their originals are kept. "
            f"Lower the tolerance or pass simplify='auto' to scale it to "
            f"the render resolution.",
            UserWarning, stacklevel=2,
        )
        simplified = simplified.where(~emptied, gdf.geometry)
    out = gdf.copy()
    out.geometry = simplified
    return out


def _draw_classified_gdf(
    viewport: SvgViewport,
    gdf: gpd.GeoDataFrame,
    colors: list[str],
    column: str,
    stroke: str,
    stroke_width: float,
    z_order: int,
    layer_id: int,
    simplify=None,
    opacity_column: str | None = None,
    min_opacity: float = D.CHOROPLETH_DEFAULT_MIN_OPACITY,
    max_opacity: float = D.CHOROPLETH_DEFAULT_MAX_OPACITY,
    blend_background: str | None = None,
    border_cfg: BorderContrast | None = None,
    border_report: list | None = None,
) -> None:
    """Render classified polygons as SVG paths with semantic attributes.

    With *opacity_column*, each feature's probability (clipped to
    ``[0, 1]``) is mapped linearly onto ``[min_opacity, max_opacity]``. With
    *blend_background* set, that opacity is pre-composited into a solid
    colour (deterministic regardless of what renders underneath); otherwise
    it is emitted as native SVG ``fill-opacity`` (blends live with whatever
    is drawn beneath, e.g. the basemap or another layer).

    With *border_cfg*, the borders shared by touching polygons of similar
    colour are redrawn on top in a contrasting colour (see
    :mod:`mappyng.border_contrast`); *border_report* then collects the weak
    borders found, as ``(borders, labels)``.
    """
    layer_name = "choropleth"
    original = gdf
    gdf = _simplify_gdf(gdf, simplify, viewport)
    fills: list[str] = []

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        cls = int(row["_class"])
        fill = colors[cls]
        value = row.get(column, "")

        attrs = {
            "fill": fill,
            "stroke": stroke,
            "stroke_width": stroke_width,
            "id": f"choro-{layer_id}-{idx}",
            "class": f"choropleth choropleth-{cls}",
            "data_value": str(value),
        }

        if opacity_column is not None:
            p = min(max(float(row[opacity_column]), 0.0), 1.0)
            alpha = min_opacity + p * (max_opacity - min_opacity)
            if blend_background is not None:
                attrs["fill"] = alpha_blend_hex(fill, blend_background, alpha)
            else:
                attrs["fill_opacity"] = round(alpha, 3)

        fills.append(str(attrs["fill"]))
        for d in geometry_to_paths(geom, viewport.viewbox):
            viewport.add_path(layer_name, d, z_order=z_order, **attrs)

    if border_cfg is not None and len(fills) == len(original):
        # Borders come from the original geometries: simplified neighbours
        # no longer share exact vertices. The lines are simplified instead.
        borders = find_weak_borders(original.geometry, fills, stroke,
                                    border_cfg)
        if borders:
            draw_weak_borders(
                viewport, borders, stroke_width=stroke_width,
                z_order=z_order + 1, cfg=border_cfg,
                tolerance=_resolve_tolerance(simplify, viewport))
            if border_report is not None:
                border_report.append((borders, original.index.tolist()))


def _draw_nodata_gdf(
    viewport: SvgViewport,
    gdf: gpd.GeoDataFrame,
    hatch_color: str | None,
    stroke_width: float,
    z_order: int,
    layer_id: int,
    defs_element,
    hatch_style: str | None = None,
    simplify=None,
) -> None:
    """Render no-data polygons with a hatch pattern fill."""
    if gdf.empty:
        return

    from . import defaults as _D
    pattern_id = f"hatch-{layer_id}-{viewport.name}"
    ensure_hatch_pattern(defs_element, pattern_id,
                         hatch_color or _D.LEGEND_HATCH_COLOR,
                         style=hatch_style or _D.LEGEND_HATCH_STYLE)

    layer_name = "choropleth"
    gdf = _simplify_gdf(gdf, simplify, viewport)

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        attrs = {
            "fill": f"url(#{pattern_id})",
            "stroke": hatch_color,
            "stroke_width": stroke_width,
            "id": f"choro-nodata-{layer_id}-{idx}",
            "class": "choropleth choropleth-nodata",
        }

        for d in geometry_to_paths(geom, viewport.viewbox):
            viewport.add_path(layer_name, d, z_order=z_order, **attrs)



# ============================================================================
# Public API, integrated into Map
# ============================================================================


def add_choropleth(
    map_obj,
    gdf: gpd.GeoDataFrame,
    column: str,
    cmap: str | list[str] = D.CHOROPLETH_DEFAULT_CMAP,
    reverse: bool = False,
    method: str | list = D.CHOROPLETH_DEFAULT_METHOD,
    num_classes: int = D.CHOROPLETH_DEFAULT_NUM_CLASSES,
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
    opacity_bins: int | list[float] | None = None,
    detail: Any = None,
    detail_join: Any = None,
    border_contrast: Any = None,
) -> int:
    """Add a choropleth layer to a Map.

    Parameters
    ----------
    map_obj : mappyng.Map
        The map instance.
    gdf : GeoDataFrame
        Data with geometries and a numeric column.
    column : str
        Column name to classify.
    cmap : str or list
        Colormap name or list of hex colors. With ``"StdMean"`` a diverging
        ramp (``"RdBu"``, ``"BrBG"``, ``"RdYlGn"``) suits the classification.
    reverse : bool
        Reverse the colour order, so the lowest class takes the ramp's last
        colour (default False). Applies to named ramps and explicit lists.
    method : str or list
        Classification method or custom break values.
    num_classes : int
        Number of classes (4-7). ``"StdMean"`` supports 5 or 7 (a diverging
        *double gamme*); any other count snaps to the nearest valid one with a
        warning. ``"Q6"`` always yields 6.
    stroke : str, optional
        Polygon outline color.
    stroke_width : float, optional
        Polygon outline width.
    legend_params : dict or False, optional
        Legend configuration (see ChoroplethLegendConfig fields).
    dissolve : bool
        Whether to dissolve geometries by class.
    simplify : None, "auto" or float
        Geometry simplification before rendering. ``None`` (default) keeps
        every vertex. ``"auto"`` drops vertices that move less than half a
        pixel at each viewport scale, which removes detail invisible at the
        render size. A number is a tolerance in the data CRS units.
        Simplification runs per viewport, after the optional dissolve.
        Without dissolve it is applied per feature, so gaps can appear
        between neighbours.
    on_zoom : bool
        Render on zoom viewport.
    on_cartouches : bool
        Render on cartouche viewports.
    opacity_column : str, optional
        Column holding a probability/confidence in ``[0, 1]``. When set,
        each feature's opacity is driven by this value (linearly mapped
        onto ``[min_opacity, max_opacity]``) instead of being fully opaque,
        so colour still encodes *column*'s class while opacity encodes
        certainty.
    min_opacity, max_opacity : float
        Opacity bounds for *opacity_column*, e.g. a probability of 0 maps
        to *min_opacity* (kept above 0 so low-confidence areas stay
        visible) and a probability of 1 maps to *max_opacity*. Ignored
        without *opacity_column*.
    blend_background : str, optional
        With *opacity_column*, pre-composite the class colour over this
        ``#RRGGBB`` background and draw an opaque solid fill instead of
        using SVG ``fill-opacity``. Gives a deterministic colour regardless
        of what renders underneath (matters when stacking layers, or for a
        legend swatch); without it, opacity is native SVG transparency and
        blends live with the basemap or layers beneath.
    opacity_bins : int, list of float, optional
        Discretize *opacity_column* into this many equal-width bins over
        ``[0, 1]`` (or explicit bin edges, as a list). Every feature in a
        bin gets the exact same opacity, so with *dissolve* neighbouring
        features that share both class and opacity bin merge into one
        path instead of being averaged. ``None`` (default) keeps opacity
        continuous, one value per feature.
    detail : GeoDataFrame or dict, optional
        Finer geometry for the zoom window and the cartouches, so a magnified
        area is not drawn from the generalised layer. Classes and colours are
        still computed from *gdf*, then carried to the finer geometries
        through *detail_join*. A GeoDataFrame applies to the zoom and to every
        cartouche; a dict maps ``"zoom"``, ``"cartouches"`` or a cartouche
        index to a GeoDataFrame. See :mod:`mappyng.detail`.
    detail_join : str, tuple or None
        Key shared by *gdf* and the finer geometries: a column name present
        in both, a ``(gdf_column, detail_column)`` pair, or None (default) to
        join on the index.
    border_contrast : bool, str, dict or BorderContrast, optional
        Make the borders between touching areas of similar colour visible.
        Where two neighbours are both light (or both dark) and the outline is
        too close in tone, the border between them disappears. With
        ``True`` (or ``"fix"``) **only those shared borders** are redrawn on top
        in a contrasting colour; the polygons keep their own outline.
        ``"check"`` reveals them instead, thick in magenta, and warns with a
        count and examples. A dict or a :class:`~mappyng.BorderContrast` sets
        the thresholds and colours. Default ``None`` (off). See
        :mod:`mappyng.border_contrast`.

    Notes
    -----
    A choropleth is intended for *relative* data (rates, ratios,
    densities). If *column* looks like absolute count (stock) data,
    strictly positive integers spanning a wide range, a non-blocking
    ``UserWarning`` suggests :meth:`~mappyng.Map.add_proportional`
    instead. The rendering always proceeds.
    """
    layer_id = map_obj._next_layer_id("choropleth")

    # The stock-data semiology check lives in
    # Choropleth.validate(), emitted once at layer construction.

    style = map_obj.style
    stroke = stroke or style["edge_color"]
    sw = stroke_width or style["edge_width"]
    z = style.config.z_order.CHOROPLETH
    border_cfg = parse_border_contrast(border_contrast)

    # Classification
    k = _resolve_num_classes(method, num_classes)
    adjustments: list[str] = []
    if method != "Q6" and not isinstance(method, list) and k != num_classes:
        adjustments.append(
            f"num_classes snapped from {num_classes} to {k} ({method})")

    # legend_params=False hides the legend; the config is still built because
    # the no-data hatch reads its colours.
    show_legend = legend_params is not False
    if not show_legend:
        legend_params = None

    # legend_params may be a dict (built into ChoroplethLegendConfig) or an
    # already-built config instance (e.g. FactorLegend). The instance is
    # copied: resolve_defaults modifies it and several maps may share it.
    if isinstance(legend_params, ChoroplethLegendConfig):
        legend_cfg = copy.copy(legend_params)
    else:
        legend_cfg = ChoroplethLegendConfig(**(legend_params or {}))
    legend_cfg.resolve_defaults(style, font_scale=getattr(map_obj, "font_scale", 1.0))

    if method == "PrettyBreaks":
        # PrettyBreaks does not guarantee the requested k: classify first, then
        # derive the real class count from the bins actually produced.
        classified, nodata, scheme, bins = classify(
            gdf, column, method=method, num_classes=k, decimals=legend_cfg.decimals,
        )
        k_real = len(scheme.bins)
        if k_real != num_classes:
            adjustments.append(
                f"PrettyBreaks produced {k_real} classes instead of {num_classes}")
            warnings.warn(
                f"PrettyBreaks produced {k_real} classes (rounded breaks) despite "
                f"num_classes={num_classes}. This is expected: PrettyBreaks prioritises "
                f"round interval bounds over the exact class count.",
                UserWarning,
                stacklevel=2,
            )
        colors = _resolve_colors_with_fallback(cmap, k_real)
    else:
        colors = _resolve_colors(cmap, k)
        classified, nodata, scheme, bins = classify(
            gdf, column, method=method, num_classes=k, decimals=legend_cfg.decimals,
        )
        k_real = len(scheme.bins)
        if k_real != len(colors):
            # Repeated or rounded values can make class breaks coincide, so the
            # classifier returns fewer classes than requested. Size the palette
            # (and so the legend) on the classes that really exist.
            label = method if isinstance(method, str) else "Custom breaks"
            adjustments.append(
                f"{label}: {k_real} distinct classes instead of {len(colors)} "
                f"(coinciding breaks, decimals={legend_cfg.decimals})")
            warnings.warn(
                f"{label}: only {k_real} distinct classes could be formed "
                f"instead of the {len(colors)} requested (repeated or rounded "
                f"values make some class breaks coincide, here with "
                f"decimals={legend_cfg.decimals}). The map and its legend use "
                f"{k_real} classes.",
                UserWarning,
                stacklevel=2,
            )
            colors = (list(colors[:k_real]) if isinstance(cmap, list)
                      else _resolve_colors_with_fallback(cmap, k_real, label=label))

    palette_note = palette_adjustment(cmap, colors)  # before any reversal
    if palette_note:
        adjustments.append(palette_note)

    if reverse:
        colors = list(reversed(colors))

    if isinstance(cmap, list) and k_real != len(cmap):
        adjustments.append(
            f"custom colour list cut from {len(cmap)} to its first {k_real} colours")
    map_obj._state.classification_reports[layer_id] = build_report(
        column, method, num_classes, k, classified, nodata, bins, adjustments,
        cmap=cmap, colors=colors)

    # Capture raw values before dissolve for the legend histogram
    hist_values = classified[column].to_numpy(dtype=float, copy=True)

    classified, opacity_levels = _resolve_opacity_bins(
        classified, opacity_column, opacity_bins)

    full_classified = classified

    def _finish(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """Dissolve (if requested) and assign each feature its class colour."""
        if dissolve:
            group_keys = (["_class", "_opacity_class"]
                          if opacity_levels else "_class")
            if opacity_column is not None:
                # dict aggfunc drops columns it doesn't name, unlike the
                # default "first"; keep every other column as "first" and
                # only average the opacity column across the merged features
                # (a no-op when opacity_bins already made it uniform per
                # group).
                key_cols = (group_keys if isinstance(group_keys, list)
                            else [group_keys])
                aggfunc = {
                    c: ("mean" if c == opacity_column else "first")
                    for c in frame.columns if c not in ("geometry", *key_cols)
                }
                frame = frame.dissolve(
                    by=group_keys, aggfunc=aggfunc,
                ).reset_index()
            else:
                frame = frame.dissolve(by="_class").reset_index()

        # Assign colors
        frame["_color"] = frame["_class"].map(lambda c: colors[c])
        return frame

    classified = _finish(full_classified.copy())

    # Finer geometry for the zoom and cartouches: same symbology, joined by key.
    details = normalize_detail(detail)
    _detail_cache: dict[int, Any] = {}

    def _data_for(target: Any) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """(classified, nodata) frames to draw on *target*."""
        finer = detail_for(details, target)
        if finer is None:
            return classified, nodata
        if id(finer) not in _detail_cache:
            _detail_cache[id(finer)] = (
                _finish(join_detail(full_classified, finer, detail_join,
                                    what="choropleth")),
                join_detail(nodata, finer, detail_join, what="choropleth"),
            )
        return _detail_cache[id(finer)]

    # ---- Render on each viewport ----

    border_report: list = []

    def _render_on(viewport: SvgViewport, data: gpd.GeoDataFrame,
                   nd: gpd.GeoDataFrame, clip_bbox: list,
                   report: list | None = None) -> None:
        clip_geom = box(*clip_bbox)
        clipped = data.clip(mask=clip_geom)
        clipped = clipped[~clipped.is_empty] if not clipped.empty else clipped
        if not clipped.empty:
            _draw_classified_gdf(viewport, clipped, colors, column, stroke, sw, z, layer_id,
                                 simplify=simplify, opacity_column=opacity_column,
                                 min_opacity=min_opacity, max_opacity=max_opacity,
                                 blend_background=blend_background,
                                 border_cfg=border_cfg, border_report=report)
        nd_clipped = nd.clip(mask=clip_geom) if not nd.empty else nd
        nd_clipped = nd_clipped[~nd_clipped.is_empty] if not nd_clipped.empty else nd_clipped
        if not nd_clipped.empty:
            _draw_nodata_gdf(viewport, nd_clipped, legend_cfg.hatch_color, sw, z, layer_id,
                             map_obj.svg._defs, hatch_style=legend_cfg.hatch_style,
                             simplify=simplify)

    # Main viewport
    _render_on(map_obj.main, classified, nodata, map_obj.bbox,
               report=border_report)
    if border_report and border_cfg is not None and border_cfg.mode == "check":
        borders, labels = border_report[0]
        warnings.warn(report_weak_borders(borders, labels, "Choropleth"),
                      UserWarning, stacklevel=2)

    # Zoom
    if on_zoom and map_obj._zoom_viewport and map_obj._zoom_bbox:
        zoom_data, zoom_nodata = _data_for(ZOOM)
        _render_on(map_obj._zoom_viewport, zoom_data, zoom_nodata,
                   map_obj._zoom_bbox)

    # Cartouches
    if on_cartouches:
        for index, vp in map_obj._cartouche_viewports.items():
            params = map_obj.cartouche_params[index]
            cart_frame, cart_nodata = _data_for(index)
            cart_data = map_obj._prepare_cartouche_data(cart_frame, params)
            cart_nd = map_obj._prepare_cartouche_data(cart_nodata, params)
            if not cart_data.empty:
                _draw_classified_gdf(vp, cart_data, colors, column, stroke, sw, z, layer_id,
                                     simplify=simplify, opacity_column=opacity_column,
                                     min_opacity=min_opacity, max_opacity=max_opacity,
                                     blend_background=blend_background,
                                     border_cfg=border_cfg)
            if not cart_nd.empty:
                _draw_nodata_gdf(vp, cart_nd, legend_cfg.hatch_color, sw, z, layer_id,
                                 map_obj.svg._defs, hatch_style=legend_cfg.hatch_style,
                                 simplify=simplify)

    # Legend
    if not show_legend:
        pass
    elif isinstance(legend_cfg, FactorLegend):
        _draw_factor_legend(map_obj.svg, colors, bins, legend_cfg,
                            not nodata.empty, map_obj.main, map_obj)
    else:
        _draw_legend(map_obj.svg, colors, bins, legend_cfg, not nodata.empty,
                     map_obj.main, map_obj, values=hist_values)

    return layer_id
