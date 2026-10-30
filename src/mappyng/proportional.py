"""
Proportional symbols for mappyng.

Renders area-proportional circles on all viewports (main, cartouches, zoom)
with a nested-circle legend.

Sizing is area-proportional: ``area proportional to value``.  A fixed reference can be
passed via ``reference_value`` / ``reference_size`` so that two maps sharing
the same reference produce comparable circles.

All default values are imported from :mod:`mappyng.defaults`.

Example
-------
>>> from mappyng import Proportional
>>> m.add(Proportional(
...     gdf_pts, column="population", fill="#e31a1c",
...     legend={"title": "Population"},
... ))
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

import geopandas as gpd
import numpy as np
from shapely.geometry import MultiPoint, Point, box

from . import defaults as D
from .detail import ZOOM, detail_for, join_detail, normalize_detail
from .legend import (
    BaseLegendConfig,
    add_legend_text,
    begin_legend,
    draw_config_frame,
    estimate_text_width,
    legend_fonts,
)
from .renderer import SvgViewport

# Internal column name holding a resolved per-circle fill colour (categorical
# colouring). Set by add_proportional when fill_column/fill_map are given; read
# by _draw_circles. Prefixed to avoid colliding with user columns.
_FILL_COL = "__mappyng_prop_fill__"


# ============================================================================
# Size calculation
# ============================================================================

def _calculate_radii(
    values: np.ndarray,
    max_radius: float = D.PROPORTIONAL_MAX_RADIUS,
    reference_value: float | None = None,
    reference_radius: float | None = None,
) -> np.ndarray:
    """Return SVG pixel radii for *values* (area-proportional).

    Area is proportional to value, so radius is proportional to sqrt(value).

    Parameters
    ----------
    values : array
        Positive numeric values.
    max_radius : float
        Maximum circle radius in SVG pixels (used when no reference is given).
    reference_value : float, optional
        A data value that should map to *reference_radius* pixels.
    reference_radius : float, optional
        The circle radius in SVG pixels for *reference_value*.

    Returns
    -------
    ndarray of radii (same length as *values*).
    """
    abs_vals = np.abs(values).astype(float)
    sqrt_vals = np.sqrt(abs_vals)

    if reference_value is not None and reference_radius is not None:
        # Fixed scale: radius = reference_radius * sqrt(value / reference_value)
        sqrt_ref = math.sqrt(abs(reference_value))
        if sqrt_ref == 0:
            return np.zeros_like(sqrt_vals)
        scale = reference_radius / sqrt_ref
    else:
        # Auto-scale to max_radius
        max_sqrt = sqrt_vals.max()
        if max_sqrt == 0:
            return np.zeros_like(sqrt_vals)
        scale = max_radius / max_sqrt

    return sqrt_vals * scale


def _format_value(val: float, decimals: int = 0, number_format: str = "space") -> str:
    """Format a numeric value.

    Parameters
    ----------
    number_format : ``"space"`` (default) or ``"none"``
        ``"space"``: narrow-space thousands separator; ``"none"``: no separator.
    """
    if decimals == 0:
        s = f"{int(round(val)):,}"
    else:
        s = f"{val:,.{decimals}f}"
    if number_format == "space":
        s = s.replace(",", " ")  # narrow no-break space
    else:
        s = s.replace(",", "")
    return s


# ============================================================================
# SVG rendering
# ============================================================================

def _draw_circles(
    viewport: SvgViewport,
    gdf: gpd.GeoDataFrame,
    radii: np.ndarray,
    fill: str,
    fill_opacity: float,
    stroke: str,
    stroke_width: float,
    z_order: int,
    layer_id: int,
    column: str,
) -> None:
    """Render proportional circles as SVG <circle> elements.

    Circles are drawn largest-first so smaller circles sit on top.
    """
    layer_name = "proportional"
    vb = viewport.viewbox

    # Per-circle fill (categorical colouring): if the data carries a resolved
    # fill column, each circle uses its own colour; otherwise the scalar `fill`.
    # This lets a SINGLE proportional layer mix colours, so the global
    # "smallest on top" ordering below holds across categories (splitting into
    # one layer per colour would break it: a later layer always overlays an
    # earlier one regardless of radius).
    has_fill_col = _FILL_COL in gdf.columns

    # Sort by radius descending (largest drawn first to smallest on top)
    order = np.argsort(-radii)

    for idx in order:
        row = gdf.iloc[idx]
        r = radii[idx]
        if r < D.PROPORTIONAL_MIN_RADIUS:
            continue

        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        # Get centroid
        if isinstance(geom, (Point, MultiPoint)):
            pt = geom if isinstance(geom, Point) else geom.centroid
        else:
            pt = geom.centroid

        cx, cy = vb.geo_to_svg(pt.x, pt.y)
        viewport.add_symbol_footprint(cx, cy, r + stroke_width / 2.0)

        viewport.add_circle(
            layer_name, cx, cy, r,
            z_order=z_order,
            fill=(row[_FILL_COL] if has_fill_col else fill),
            fill_opacity=fill_opacity,
            stroke=stroke,
            stroke_width=stroke_width,
            id=f"prop-{layer_id}-{row.name}",
            **{"class": "proportional"},
            data_value=str(row.get(column, "")),
        )


# ============================================================================
# Legend
# ============================================================================

@dataclass
class ProportionalLegendConfig(BaseLegendConfig):
    """Proportional-symbol legend configuration.

    Inherits all shared fields from :class:`~mappyng.legend.BaseLegendConfig`.
    Pass as the ``legend`` dict in :meth:`~mappyng.Map.add_proportional`.

    Attributes
    ----------
    orientation : str
        Legend layout: ``"nested"`` (default, concentric circles),
        ``"vertical"`` (stacked), or ``"horizontal"`` (side by side).
    values : list of float or None
        Explicit data values to show in the legend.  Auto-generated if None.
    num_values : int
        Number of auto-generated legend values (default 4).
    decimals : int
        Decimal places for value labels (default 0).
    number_format : str
        Thousands separator: ``"space"`` (default, narrow no-break space)
        or ``"none"`` (no separator).
    circle_fill : str or None
        Legend circle fill color override.  Uses the layer fill if None.
    circle_fill_opacity : float
        Legend circle fill opacity 0-1.
    circle_stroke : str
        Legend circle stroke color.
    circle_stroke_width : float
        Legend circle stroke width (SVG px).
    circle_spacing : float or None
        Fixed horizontal gap between circles in horizontal mode (SVG px).
        Auto-computed from circle sizes if None.
    label_gap : float
        Gap between circle edge and label text (SVG px).
    leader_color : str
        Leader line color in nested mode.
    leader_width : float
        Leader line stroke width (SVG px).
    leader_dash : str
        Leader line SVG ``stroke-dasharray`` (e.g. ``"4 2"``).
    leader_opacity : float
        Leader line opacity 0-1.
    """
    orientation: str = D.PROPORTIONAL_LEGEND_ORIENTATION
    values: list[float] | None = None
    num_values: int = D.LEGEND_CIRCLE_NUM_VALUES
    decimals: int = 0
    number_format: str = "space"
    """Thousands separator: ``"space"`` (default) or ``"none"``."""
    circle_fill: str | None = None
    circle_fill_opacity: float = D.LEGEND_CIRCLE_FILL_OPACITY
    circle_stroke: str = D.LEGEND_CIRCLE_EDGECOLOR
    circle_stroke_width: float = D.LEGEND_CIRCLE_LINEWIDTH
    circle_spacing: float | None = None
    """Fixed horizontal gap between circles in horizontal mode (SVG px). Overrides default."""
    label_gap: float = D.LEGEND_CIRCLE_LABEL_GAP
    leader_color: str = D.LEGEND_CIRCLE_LEADER_COLOR
    leader_width: float = D.LEGEND_CIRCLE_LEADER_WIDTH
    leader_dash: str = D.LEGEND_CIRCLE_LEADER_DASH
    leader_opacity: float = D.LEGEND_CIRCLE_LEADER_OPACITY
    """Opacity of leader lines in nested legend (0-1)."""


def _auto_legend_values(
    values: np.ndarray,
    num: int = D.LEGEND_CIRCLE_NUM_VALUES,
) -> list[float]:
    """Generate visually balanced legend values from data range.

    Spacing is done in sqrt-space so that legend circles are visually
    distinguishable (not bunched at the top).
    """
    vmin, vmax = float(np.nanmin(values)), float(np.nanmax(values))
    if vmin == vmax:
        return [vmax]
    sqrt_space = np.linspace(math.sqrt(vmin), math.sqrt(vmax), num)
    return [round(v ** 2) for v in sqrt_space]


def _draw_proportional_legend(
    svg_doc,
    config: ProportionalLegendConfig,
    legend_values: list[float],
    legend_radii: np.ndarray,
    fill: str,
    main_viewport: SvgViewport,
):
    """Draw a proportional legend below the main map.

    Dispatches to the appropriate layout based on ``config.orientation``:
    ``"nested"`` (default), ``"vertical"``, or ``"horizontal"``.

    Returns (x0, y0, x1, y1) bounding box or None if nothing was drawn.
    """
    orientation = config.orientation
    if orientation == "vertical":
        return _draw_prop_legend_vertical(svg_doc, config, legend_values, legend_radii, fill, main_viewport)
    elif orientation == "horizontal":
        return _draw_prop_legend_horizontal(svg_doc, config, legend_values, legend_radii, fill, main_viewport)
    else:
        return _draw_prop_legend_nested(svg_doc, config, legend_values, legend_radii, fill, main_viewport)


def _prepare_prop_legend(config, legend_values, legend_radii):
    """Shared start of the proportional layouts.

    Returns ``(sorted_pairs, max_r)`` with the (value, radius) pairs ordered
    largest first, or None when there is nothing to draw.
    """
    max_r = float(max(legend_radii))
    if max_r <= 0:
        return None
    sorted_pairs = sorted(zip(legend_values, legend_radii), key=lambda p: -p[1])
    return sorted_pairs, max_r


def _add_legend_circle(legend_g, config, circle_fill, cx, cy, r, i):
    """Draw the legend circle of rank *i*."""
    ET.SubElement(
        legend_g, "circle",
        cx=f"{cx:.2f}", cy=f"{cy:.2f}", r=f"{r:.2f}",
        fill=circle_fill,
        stroke=config.circle_stroke,
        id=f"proportional-legend-circle-{i}",
        **{
            "fill-opacity": str(config.circle_fill_opacity),
            "stroke-width": str(config.circle_stroke_width),
            "class": "proportional-legend",
        },
    )


def _finish_prop_legend(legend_g, svg_doc, config, legend_x, legend_y,
                        content_w, content_h):
    """Draw the optional frame and return the legend bbox."""
    title_offset = (config.title_fontsize or D.LEGEND_TITLE_FONT_SIZE) * 0.3
    draw_config_frame(
        legend_g, svg_doc, config,
        legend_x, legend_y - title_offset,
        content_w, content_h + title_offset,
    )
    return (legend_x, legend_y, legend_x + content_w, legend_y + content_h)


def _draw_prop_legend_nested(
    svg_doc,
    config: ProportionalLegendConfig,
    legend_values: list[float],
    legend_radii: np.ndarray,
    fill: str,
    main_viewport: SvgViewport,
) -> None:
    """Nested-circle legend: stacked circles with leader lines and labels."""
    font_size, fc, ff = legend_fonts(config)
    circle_fill = config.circle_fill or fill

    prepared = _prepare_prop_legend(config, legend_values, legend_radii)
    if prepared is None:
        return
    sorted_pairs, max_r = prepared

    legend_g, legend_x, legend_y, y_cursor = begin_legend(
        svg_doc, "proportional-legend", config, main_viewport.viewbox)

    baseline_y = y_cursor + 2 * max_r
    cx = legend_x + max_r
    label_x = cx + max_r + config.label_gap

    for i, (val, r) in enumerate(sorted_pairs):
        if r <= 0:
            continue
        cy = baseline_y - r
        _add_legend_circle(legend_g, config, circle_fill, cx, cy, r, i)

        line_y = baseline_y - 2 * r
        ET.SubElement(
            legend_g, "line",
            x1=f"{cx:.2f}", y1=f"{line_y:.2f}",
            x2=f"{label_x:.2f}", y2=f"{line_y:.2f}",
            stroke=config.leader_color,
            **{  # type: ignore[arg-type]
                "stroke-width": str(config.leader_width),
                "stroke-dasharray": config.leader_dash,
                "stroke-opacity": str(config.leader_opacity),
            },
        )

        add_legend_text(
            legend_g, label_x + 3, line_y + font_size * 0.35,
            _format_value(val, config.decimals, config.number_format),
            font_size, ff, fc,
        )

    # ---- Bbox and frame ----
    max_label_chars = max(
        len(_format_value(v, config.decimals)) for v in legend_values
    ) if legend_values else 0
    content_w = label_x + 3 + max_label_chars * font_size * 0.55 - legend_x
    content_h = baseline_y - legend_y + max_r

    return _finish_prop_legend(legend_g, svg_doc, config, legend_x, legend_y,
                               content_w, content_h)


def _draw_prop_legend_vertical(
    svg_doc,
    config: ProportionalLegendConfig,
    legend_values: list[float],
    legend_radii: np.ndarray,
    fill: str,
    main_viewport: SvgViewport,
) -> None:
    """Vertical legend: one circle + label per row, top to bottom."""
    font_size, fc, ff = legend_fonts(config)
    circle_fill = config.circle_fill or fill
    circle_gap = D.PROPORTIONAL_LEGEND_CIRCLE_GAP

    prepared = _prepare_prop_legend(config, legend_values, legend_radii)
    if prepared is None:
        return
    sorted_pairs, max_r = prepared

    legend_g, legend_x, legend_y, y_cursor = begin_legend(
        svg_doc, "proportional-legend", config, main_viewport.viewbox)

    # Draw rows: largest first, each circle + label
    max_label_w = 0.0
    label_x = legend_x + max_r * 2 + config.label_gap

    for i, (val, r) in enumerate(sorted_pairs):
        if r <= 0:
            continue

        cy = y_cursor + r
        _add_legend_circle(legend_g, config, circle_fill,
                           legend_x + max_r, cy, r, i)

        label_text = _format_value(val, config.decimals, config.number_format)
        add_legend_text(legend_g, label_x, cy + font_size * 0.35, label_text,
                        font_size, ff, fc)
        max_label_w = max(max_label_w, estimate_text_width(label_text, font_size))

        y_cursor += 2 * r + circle_gap

    # ---- Bbox and frame ----
    content_w = label_x + max_label_w - legend_x
    content_h = y_cursor - circle_gap - legend_y

    return _finish_prop_legend(legend_g, svg_doc, config, legend_x, legend_y,
                               content_w, content_h)


def _draw_prop_legend_horizontal(
    svg_doc,
    config: ProportionalLegendConfig,
    legend_values: list[float],
    legend_radii: np.ndarray,
    fill: str,
    main_viewport: SvgViewport,
) -> None:
    """Horizontal legend: circles in a row with labels below."""
    font_size, fc, ff = legend_fonts(config)
    circle_fill = config.circle_fill or fill
    h_gap = config.circle_spacing if config.circle_spacing is not None else D.PROPORTIONAL_LEGEND_HORIZONTAL_GAP

    prepared = _prepare_prop_legend(config, legend_values, legend_radii)
    if prepared is None:
        return
    sorted_pairs, max_r = prepared

    legend_g, legend_x, legend_y, y_cursor = begin_legend(
        svg_doc, "proportional-legend", config, main_viewport.viewbox)

    # Baseline: all circles sit on the same baseline (bottom-aligned)
    baseline_y = y_cursor + 2 * max_r

    # Draw circles left-to-right, largest first
    x_cursor = legend_x
    label_y = baseline_y + font_size + 4

    for i, (val, r) in enumerate(sorted_pairs):
        if r <= 0:
            continue

        cx = x_cursor + r
        _add_legend_circle(legend_g, config, circle_fill, cx, baseline_y - r, r, i)

        # Label centered below circle
        add_legend_text(
            legend_g, cx, label_y,
            _format_value(val, config.decimals, config.number_format),
            font_size, ff, fc, anchor="middle",
        )

        x_cursor += 2 * r + h_gap

    # ---- Bbox and frame ----
    content_w = x_cursor - h_gap - legend_x
    content_h = label_y + font_size * 0.3 - legend_y

    return _finish_prop_legend(legend_g, svg_doc, config, legend_x, legend_y,
                               content_w, content_h)


# ============================================================================
# Public API, integrated into Map
# ============================================================================


def add_proportional(
    map_obj,
    gdf: gpd.GeoDataFrame,
    column: str,
    fill: str = D.PROPORTIONAL_FILL,
    fill_opacity: float = D.PROPORTIONAL_FILL_OPACITY,
    stroke: str = D.PROPORTIONAL_STROKE,
    stroke_width: float = D.PROPORTIONAL_STROKE_WIDTH,
    max_radius: float = D.PROPORTIONAL_MAX_RADIUS,
    reference_value: float | None = None,
    reference_radius: float | None = None,
    legend_params: dict[str, Any] | None = None,
    on_zoom: bool = True,
    on_cartouches: bool = True,
    fill_column: str | None = None,
    fill_map: dict[Any, str] | None = None,
    detail: Any = None,
    detail_join: Any = None,
) -> int:
    """Add proportional circles to a Map.

    Parameters
    ----------
    map_obj : mappyng.Map
        The map instance.
    gdf : GeoDataFrame
        Data with point/polygon geometries and a numeric column.
    column : str
        Column name for sizing.
    fill : str
        Circle fill color.
    fill_opacity : float
        Circle fill opacity (0-1).
    stroke : str
        Circle stroke color.
    stroke_width : float
        Circle stroke width.
    max_radius : float
        Maximum circle radius in SVG pixels (auto-scale mode).
    reference_value : float, optional
        Data value that should map to *reference_radius* pixels.
        Allows consistent sizing across multiple maps.
    reference_radius : float, optional
        Circle radius in SVG pixels for *reference_value*.
    legend_params : dict, optional
        Legend configuration (see ProportionalLegendConfig fields).
    on_zoom : bool
        Render on zoom viewport.
    on_cartouches : bool
        Render on cartouche viewports.
    fill_column : str, optional
        Column holding a category per feature. Combined with *fill_map*, each
        circle is coloured individually, so a SINGLE layer can mix colours and
        keep the global "smallest on top" ordering across categories (splitting
        into one layer per colour breaks that ordering).
    fill_map : dict, optional
        Mapping ``category -> colour`` used with *fill_column*. Categories absent
        from the mapping fall back to *fill*.
    detail : GeoDataFrame or dict, optional
        Finer geometry for the zoom window and the cartouches: the circles
        are placed from it instead of from *gdf*, and keep the values and
        colours of *gdf* through *detail_join*. A GeoDataFrame applies to the
        zoom and every cartouche; a dict maps ``"zoom"``, ``"cartouches"`` or a
        cartouche index to a GeoDataFrame. See :mod:`mappyng.detail`.
    detail_join : str, tuple or None
        Key shared by *gdf* and *detail* (column name, a
        ``(gdf_column, detail_column)`` pair, or None for the index).
    """
    layer_id = map_obj._next_layer_id("proportional")

    z = map_obj.style.config.z_order.PROPORTIONAL

    # Drop NaN / zero
    data = gdf.dropna(subset=[column]).copy()
    data = data[data[column] != 0]
    if data.empty:
        return layer_id

    # Categorical colouring: resolve a per-circle fill column carried by `data`
    # (survives clipping/cartouche subsetting) and read back in _draw_circles.
    if fill_column is not None and fill_map is not None:
        data[_FILL_COL] = data[fill_column].map(fill_map).fillna(fill)

    values = data[column].values

    # One scale for the whole layer. Without an explicit reference, the largest
    # value of the layer's data maps to max_radius. Fixing it here (instead of
    # letting each call rescale to the largest value it is given) keeps a value
    # at the same radius on the main map, the zoom, the cartouches and in the
    # legend, whatever subset of the data a viewport shows.
    if reference_value is None or reference_radius is None:
        reference_value = float(np.abs(values).max())
        reference_radius = max_radius

    # ---- Legend setup ----
    legend_cfg = ProportionalLegendConfig(**(legend_params or {}))
    legend_cfg.resolve_defaults(map_obj.style, font_scale=getattr(map_obj, "font_scale", 1.0))

    legend_values = legend_cfg.values
    if legend_values is None:
        legend_values = _auto_legend_values(values, legend_cfg.num_values)

    legend_radii = _calculate_radii(
        np.array(legend_values, dtype=float),
        max_radius, reference_value, reference_radius,
    )

    # ---- Render on viewports ----

    # Finer geometry for the zoom and cartouches: centres are taken from it,
    # values and colours stay those of `data`.
    details = normalize_detail(detail)
    _detail_cache: dict[int, gpd.GeoDataFrame] = {}

    def _data_for(target: Any) -> gpd.GeoDataFrame:
        finer = detail_for(details, target)
        if finer is None:
            return data
        if id(finer) not in _detail_cache:
            _detail_cache[id(finer)] = join_detail(
                data, finer, detail_join, what="proportional")
        return _detail_cache[id(finer)]

    def _render_on(viewport: SvgViewport, data_gdf: gpd.GeoDataFrame,
                   clip_bbox: list) -> None:
        clip_geom = box(*clip_bbox)
        # Use centroids for clipping (a polygon whose centroid is in bbox should show)
        centroids = data_gdf.geometry.centroid
        mask = centroids.within(clip_geom)
        clipped = data_gdf[mask]
        if clipped.empty:
            return
        clip_vals = clipped[column].values
        clip_radii = _calculate_radii(
            clip_vals, max_radius, reference_value, reference_radius,
        )
        # Proportional symbols encode a DATA VALUE through their pixel area, not a
        # geographic size: their radius must stay constant (in SVG pixels) across
        # viewports so a given value reads at the same circle size on the main map,
        # the zoom and the cartouches.  We therefore do NOT rescale by the
        # viewport's pixel/geo scale -- only the centres are reprojected.  (The
        # whole point of a zoom inset for proportional symbols is to spread out
        # overlapping centres, not to shrink the glyphs.)
        _draw_circles(viewport, clipped, clip_radii, fill, fill_opacity,
                       stroke, stroke_width, z, layer_id, column)

    # Main viewport
    _render_on(map_obj.main, data, map_obj.bbox)

    # Zoom
    if on_zoom and map_obj._zoom_viewport and map_obj._zoom_bbox:
        _render_on(map_obj._zoom_viewport, _data_for(ZOOM), map_obj._zoom_bbox)

    # Cartouches
    if on_cartouches:
        for index, vp in map_obj._cartouche_viewports.items():
            params = map_obj.cartouche_params[index]
            cart_data = map_obj._prepare_cartouche_data(_data_for(index), params)
            if not cart_data.empty:
                cart_vals = cart_data[column].values
                cart_radii = _calculate_radii(
                    cart_vals, max_radius, reference_value, reference_radius,
                )
                # Constant pixel radius across viewports (see _render_on): a
                # proportional glyph must not shrink/grow with the cartouche scale.
                _draw_circles(vp, cart_data, cart_radii, fill, fill_opacity,
                               stroke, stroke_width, z, layer_id, column)

    # Legend
    legend_bbox = _draw_proportional_legend(
        map_obj.svg, legend_cfg, legend_values, legend_radii,
        fill, map_obj.main,
    )
    if legend_bbox is not None:
        map_obj.overflow.register(*legend_bbox)

    return layer_id
