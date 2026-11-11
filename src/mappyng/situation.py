"""
Situation (point symbol) layer for mappyng.

Renders categorical or uniform point symbols on the map using SVG
primitives, circles, squares, triangles, diamonds, stars, crosses,
custom SVG files, or *composite* markers (combinations of shapes).

Configured through :class:`~mappyng.Situation`.

Example
-------
>>> from mappyng import Situation
>>> m.add(Situation(
...     gdf_pts, column="type",
...     symbol={
...         "Hospital": {"marker": "cross", "fill": "#e63946", "size": 12},
...         "School":   {"marker": "square", "fill": "#457b9d", "size": 10},
...     },
...     legend={"title": "Équipements"},
... ))
"""

from __future__ import annotations

import math
import warnings
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
from shapely.geometry import MultiPoint, Point

from . import defaults as D
from .detail import ZOOM, detail_for, join_detail, normalize_detail
from .errors import GEO_ERRORS
from .legend import (
    BaseLegendConfig,
    _parse_frame_config,
    compute_legend_position,
    draw_legend_frame,
    draw_legend_subtitle,
    draw_legend_title,
    make_legend_config,
    record_legend,
    stack_legend,
)
from .renderer import SvgViewport

# ============================================================================
# Defaults
# ============================================================================

SITUATION_DEFAULT_MARKER = "circle"
SITUATION_DEFAULT_COLOR = "#e31a1c"
SITUATION_DEFAULT_SIZE = 8.0
SITUATION_DEFAULT_STROKE = "#ffffff"
SITUATION_DEFAULT_STROKE_WIDTH = 0.5
SITUATION_DEFAULT_FILL_OPACITY = 1.0
SITUATION_MISSING_COLOR = "#e63946"
SITUATION_MISSING_MARKER = "cross"


# ============================================================================
# Shape path generators
# ============================================================================

def _circle_path(cx: float, cy: float, r: float) -> str:
    """SVG path for a circle (two arcs)."""
    return (
        f"M{cx - r:.2f},{cy:.2f}"
        f"A{r:.2f},{r:.2f} 0 1,0 {cx + r:.2f},{cy:.2f}"
        f"A{r:.2f},{r:.2f} 0 1,0 {cx - r:.2f},{cy:.2f}Z"
    )


def _square_path(cx: float, cy: float, r: float) -> str:
    """SVG path for a square inscribed in radius *r*."""
    s = r * 0.85  # half-side
    return (
        f"M{cx - s:.2f},{cy - s:.2f}"
        f"L{cx + s:.2f},{cy - s:.2f}"
        f"L{cx + s:.2f},{cy + s:.2f}"
        f"L{cx - s:.2f},{cy + s:.2f}Z"
    )


def _triangle_path(cx: float, cy: float, r: float) -> str:
    """SVG path for an upward-pointing equilateral triangle."""
    # Top vertex
    tx, ty = cx, cy - r
    # Bottom-left and bottom-right
    bx = r * math.cos(math.radians(30))
    by = r * math.sin(math.radians(30))
    return (
        f"M{tx:.2f},{ty:.2f}"
        f"L{cx + bx:.2f},{cy + by:.2f}"
        f"L{cx - bx:.2f},{cy + by:.2f}Z"
    )


def _diamond_path(cx: float, cy: float, r: float) -> str:
    """SVG path for a diamond (rotated square)."""
    return (
        f"M{cx:.2f},{cy - r:.2f}"
        f"L{cx + r * 0.7:.2f},{cy:.2f}"
        f"L{cx:.2f},{cy + r:.2f}"
        f"L{cx - r * 0.7:.2f},{cy:.2f}Z"
    )


def _star_path(cx: float, cy: float, r: float) -> str:
    """SVG path for a 5-pointed star."""
    points = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        rad = r if i % 2 == 0 else r * 0.4
        px = cx + rad * math.cos(angle)
        py = cy + rad * math.sin(angle)
        points.append(f"{px:.2f},{py:.2f}")
    return "M" + "L".join(points) + "Z"


def _cross_path(cx: float, cy: float, r: float) -> str:
    """SVG path for a + cross (thick arms)."""
    t = r * 0.3  # arm thickness
    return (
        f"M{cx - t:.2f},{cy - r:.2f}"
        f"L{cx + t:.2f},{cy - r:.2f}"
        f"L{cx + t:.2f},{cy - t:.2f}"
        f"L{cx + r:.2f},{cy - t:.2f}"
        f"L{cx + r:.2f},{cy + t:.2f}"
        f"L{cx + t:.2f},{cy + t:.2f}"
        f"L{cx + t:.2f},{cy + r:.2f}"
        f"L{cx - t:.2f},{cy + r:.2f}"
        f"L{cx - t:.2f},{cy + t:.2f}"
        f"L{cx - r:.2f},{cy + t:.2f}"
        f"L{cx - r:.2f},{cy - t:.2f}"
        f"L{cx - t:.2f},{cy - t:.2f}Z"
    )


def _x_cross_path(cx: float, cy: float, r: float) -> str:
    """SVG path for an X cross (diagonal)."""
    t = r * 0.22
    d = r * 0.707  # r / sqrt(2)
    dt = t * 0.707
    # Build the 12-pointed shape of an X
    return (
        f"M{cx:.2f},{cy - dt:.2f}"
        f"L{cx + d - dt:.2f},{cy - d:.2f}"
        f"L{cx + d:.2f},{cy - d + dt:.2f}"
        f"L{cx + dt:.2f},{cy:.2f}"
        f"L{cx + d:.2f},{cy + d - dt:.2f}"
        f"L{cx + d - dt:.2f},{cy + d:.2f}"
        f"L{cx:.2f},{cy + dt:.2f}"
        f"L{cx - d + dt:.2f},{cy + d:.2f}"
        f"L{cx - d:.2f},{cy + d - dt:.2f}"
        f"L{cx - dt:.2f},{cy:.2f}"
        f"L{cx - d:.2f},{cy - d + dt:.2f}"
        f"L{cx - d + dt:.2f},{cy - d:.2f}Z"
    )


def _pentagon_path(cx: float, cy: float, r: float) -> str:
    """SVG path for a regular pentagon."""
    points = []
    for i in range(5):
        angle = math.radians(i * 72 - 90)
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        points.append(f"{px:.2f},{py:.2f}")
    return "M" + "L".join(points) + "Z"


def _hexagon_path(cx: float, cy: float, r: float) -> str:
    """SVG path for a regular hexagon (flat-top)."""
    points = []
    for i in range(6):
        angle = math.radians(i * 60)
        px = cx + r * math.cos(angle)
        py = cy + r * math.sin(angle)
        points.append(f"{px:.2f},{py:.2f}")
    return "M" + "L".join(points) + "Z"


_SHAPE_BUILDERS = {
    "circle": _circle_path,
    "square": _square_path,
    "triangle": _triangle_path,
    "diamond": _diamond_path,
    "star": _star_path,
    "cross": _cross_path,
    "plus": _cross_path,
    "x": _x_cross_path,
    "pentagon": _pentagon_path,
    "hexagon": _hexagon_path,
}


# ============================================================================
# Composite markers
# ============================================================================

def _parse_marker(marker: Any) -> list[str]:
    """Parse a marker specification into a list of shape names.

    Accepts:
    - ``"circle"``: single shape
    - ``"circle+cross"``: composite (circle behind, cross on top)
    - ``["circle", "cross"]``: same as above
    - ``"path/to/icon.svg"``: custom SVG (returned as-is in a list)
    """
    if isinstance(marker, list):
        return marker
    if isinstance(marker, str):
        if "+" in marker and not marker.endswith(".svg"):
            return [m.strip() for m in marker.split("+")]
        return [marker]
    return [SITUATION_DEFAULT_MARKER]


def _category_key(value: Any) -> str:
    """Text key of a category value, the same for ``1``, ``1.0`` and ``"1"``.

    A column of whole numbers is often stored as floats (as soon as it has
    a missing value), while the ``symbol`` dict is keyed with integers.
    """
    if isinstance(value, bool):
        return str(value)
    try:
        if float(value) == int(float(value)) and not isinstance(value, str):
            return str(int(float(value)))
    except (TypeError, ValueError, OverflowError):
        pass
    return str(value)


def _check_markers(categories: dict[str, MarkerConfig]) -> None:
    """Warn about marker names that will be drawn as a plain circle."""
    unknown: list[str] = []
    missing_files: list[str] = []
    for cfg in categories.values():
        for shape in cfg.shapes:
            if shape in _SHAPE_BUILDERS:
                continue
            if _is_svg_file(str(shape)):
                if not Path(shape).exists() and shape not in missing_files:
                    missing_files.append(shape)
            elif shape not in unknown:
                unknown.append(shape)
    if unknown:
        warnings.warn(
            f"Situation: unknown marker(s) {unknown}, drawn as circles. "
            f"Available markers: {sorted(_SHAPE_BUILDERS)}, or the path of "
            f"an .svg file.",
            UserWarning, stacklevel=3,
        )
    if missing_files:
        warnings.warn(
            f"Situation: marker file(s) not found: {missing_files}. The "
            f"points are drawn as circles instead.",
            UserWarning, stacklevel=3,
        )


def _is_svg_file(name: str) -> bool:
    """Check if a marker name refers to an external SVG file."""
    return name.endswith(".svg") and "/" in name or name.endswith(".svg")


# ============================================================================
# SVG marker rendering
# ============================================================================

def _load_svg_marker(path: str) -> str | None:
    """Load an SVG file and return its inner content as a string."""
    p = Path(path)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")


def _draw_marker_on_viewport(
    viewport: SvgViewport,
    layer: str,
    cx: float,
    cy: float,
    shapes: list[str],
    size: float,
    fill: str,
    stroke: str,
    stroke_width: float,
    fill_opacity: float,
    z_order: int,
    elem_id: str | None = None,
    inner_fill: str | None = None,
    inner_stroke: str | None = None,
) -> None:
    """Draw a (possibly composite) marker at SVG coordinates (cx, cy).

    For composite markers, each shape after the first uses ``inner_fill``
    (default: stroke color) and ``inner_stroke`` so they stand out.
    """
    r = size / 2.0
    viewport.add_symbol_footprint(cx, cy, r + stroke_width / 2.0)

    for i, shape_name in enumerate(shapes):
        is_first = (i == 0)
        cur_fill = fill if is_first else (inner_fill or stroke)
        cur_stroke = stroke if is_first else (inner_stroke or fill)
        cur_opacity = str(fill_opacity) if is_first else "1"

        attrs: dict[str, Any] = {
            "fill": cur_fill,
            "stroke": cur_stroke,
            "stroke-width": str(stroke_width),
            "fill-opacity": cur_opacity,
        }
        if elem_id and is_first:
            attrs["id"] = elem_id

        # Inner shapes are slightly smaller
        cur_r = r if is_first else r * 0.55

        if shape_name in _SHAPE_BUILDERS:
            d = _SHAPE_BUILDERS[shape_name](cx, cy, cur_r)
            group = viewport.get_layer(layer, z_order)
            elem = ET.SubElement(group, "path", d=d)
            for k, v in attrs.items():
                elem.set(k, str(v))

        elif _is_svg_file(shape_name):
            svg_content = _load_svg_marker(shape_name)
            if svg_content is None:
                # Fallback to circle
                d = _circle_path(cx, cy, cur_r)
                group = viewport.get_layer(layer, z_order)
                elem = ET.SubElement(group, "path", d=d)
                for k, v in attrs.items():
                    elem.set(k, str(v))
            else:
                _inject_svg_marker(viewport, layer, cx, cy, cur_r * 2,
                                   svg_content, z_order, elem_id if is_first else None)
        else:
            # Unknown shape, fallback to circle
            d = _circle_path(cx, cy, cur_r)
            group = viewport.get_layer(layer, z_order)
            elem = ET.SubElement(group, "path", d=d)
            for k, v in attrs.items():
                elem.set(k, str(v))


def _inject_svg_marker(
    viewport: SvgViewport,
    layer: str,
    cx: float,
    cy: float,
    size: float,
    svg_content: str,
    z_order: int,
    elem_id: str | None = None,
) -> None:
    """Inject a custom SVG marker centered at (cx, cy)."""
    group = viewport.get_layer(layer, z_order)
    _append_svg_marker(group, cx, cy, size, svg_content, elem_id)


def _append_svg_marker(
    parent: ET.Element,
    cx: float,
    cy: float,
    size: float,
    svg_content: str,
    elem_id: str | None = None,
) -> None:
    """Append a custom SVG marker to *parent*, its viewBox centered at (cx, cy)
    and scaled so that its longer side equals *size*."""
    try:
        svg_root = ET.fromstring(svg_content)
    except ET.ParseError:
        return
    g = ET.SubElement(parent, "g")
    if elem_id:
        g.set("id", elem_id)

    vb_x = vb_y = 0.0
    vb = svg_root.get("viewBox", "")
    parts = vb.replace(",", " ").split()
    if len(parts) == 4:
        vb_x, vb_y = float(parts[0]), float(parts[1])
        vb_w, vb_h = float(parts[2]), float(parts[3])
    else:
        vb_w = float(svg_root.get("width", size))
        vb_h = float(svg_root.get("height", size))

    # Scale to fit within size
    scale = size / max(vb_w, vb_h)
    actual_w = vb_w * scale
    actual_h = vb_h * scale

    # Translate so the viewBox (origin included) is centered at (cx, cy)
    tx = cx - actual_w / 2 - vb_x * scale
    ty = cy - actual_h / 2 - vb_y * scale
    g.set("transform", f"translate({tx:.2f},{ty:.2f}) scale({scale:.4f})")

    # Append children of the SVG root (skip the <svg> wrapper)
    for child in svg_root:
        g.append(child)


# ============================================================================
# Legend marker preview (for legend swatches)
# ============================================================================

def _draw_legend_marker(
    parent: ET.Element,
    cx: float,
    cy: float,
    shapes: list[str],
    size: float,
    fill: str,
    stroke: str,
    stroke_width: float,
    fill_opacity: float,
    inner_fill: str | None = None,
    inner_stroke: str | None = None,
) -> None:
    """Draw a marker preview inside a legend element."""
    r = size / 2.0
    for i, shape_name in enumerate(shapes):
        is_first = (i == 0)
        cur_fill = fill if is_first else (inner_fill or stroke)
        cur_stroke = stroke if is_first else (inner_stroke or fill)
        cur_r = r if is_first else r * 0.55

        if shape_name in _SHAPE_BUILDERS:
            d = _SHAPE_BUILDERS[shape_name](cx, cy, cur_r)
            elem = ET.SubElement(parent, "path", d=d)
            elem.set("fill", cur_fill)
            elem.set("stroke", cur_stroke)
            elem.set("stroke-width", str(stroke_width))
            if is_first:
                elem.set("fill-opacity", str(fill_opacity))
        elif _is_svg_file(shape_name):
            svg_content = _load_svg_marker(shape_name)
            if svg_content is not None:
                _append_svg_marker(parent, cx, cy, cur_r * 2, svg_content)
                continue
            # Unreadable file: circle placeholder, as on the map
            d = _circle_path(cx, cy, cur_r)
            elem = ET.SubElement(parent, "path", d=d)
            elem.set("fill", cur_fill)
            elem.set("stroke", cur_stroke)
            elem.set("stroke-width", str(stroke_width))


# ============================================================================
# Symbol config parsing
# ============================================================================

@dataclass
class MarkerConfig:
    """Resolved configuration for a single marker type."""
    shapes: list[str]
    fill: str = SITUATION_DEFAULT_COLOR
    size: float = SITUATION_DEFAULT_SIZE
    stroke: str = SITUATION_DEFAULT_STROKE
    stroke_width: float = SITUATION_DEFAULT_STROKE_WIDTH
    fill_opacity: float = SITUATION_DEFAULT_FILL_OPACITY
    inner_fill: str | None = None
    inner_stroke: str | None = None
    label: str | None = None


def _parse_symbol_config(raw: dict[str, Any]) -> MarkerConfig:
    """Parse a single symbol dict into a MarkerConfig."""
    marker = raw.get("marker", SITUATION_DEFAULT_MARKER)
    shapes = _parse_marker(marker)
    return MarkerConfig(
        shapes=shapes,
        fill=raw.get("fill", SITUATION_DEFAULT_COLOR),
        size=raw.get("size", SITUATION_DEFAULT_SIZE),
        stroke=raw.get("stroke", SITUATION_DEFAULT_STROKE),
        stroke_width=raw.get("stroke_width", SITUATION_DEFAULT_STROKE_WIDTH),
        fill_opacity=raw.get("fill_opacity", SITUATION_DEFAULT_FILL_OPACITY),
        inner_fill=raw.get("inner_fill", None),
        inner_stroke=raw.get("inner_stroke", None),
        label=raw.get("label", None),
    )


# ============================================================================
# Situation legend
# ============================================================================

@dataclass
class SituationLegendConfig(BaseLegendConfig):
    """Legend configuration for situation (categorical marker) layers.

    Inherits all shared fields from :class:`~mappyng.legend.BaseLegendConfig`.
    Pass as the ``legend`` dict in ``Situation``.

    Attributes
    ----------
    marker_size : float
        Size of the marker preview in the legend (SVG px, default 10.0).
    label_gap : float
        Gap between marker preview and label text (SVG px, default 6.0).
    row_spacing : float
        Vertical gap between legend rows (SVG px, default 4.0).
    col_gap : float
        Horizontal gap between columns in multi-column layout (SVG px,
        default 20.0).
    columns_n : int
        Number of columns in the legend (default 1).
    """
    marker_size: float = 10.0
    label_gap: float = 6.0
    row_spacing: float = 4.0
    col_gap: float = 20.0
    """Horizontal gap between columns in multi-column layout (SVG px)."""
    columns_n: int = 1
    """Number of columns in the legend (default 1 = single column)."""


def _draw_situation_legend(
    map_obj: Any,
    categories: dict[str, MarkerConfig],
    legend_params: dict[str, Any] | None,
    layer_id: int,
):
    """Draw a categorical legend with marker previews.

    Supports single-column (default) and multi-column (``columns_n > 1``) layouts.
    Uses :class:`SituationLegendConfig` for all styling, consistent with
    other legend types.
    """
    if legend_params is None:
        return
    if not categories:
        return

    lp = dict(legend_params)
    sit_cfg = make_legend_config(SituationLegendConfig, lp, "Situation legend")
    sit_cfg.resolve_defaults(map_obj.style, font_scale=getattr(map_obj, "font_scale", 1.0))
    stacked = stack_legend(map_obj, sit_cfg)
    frame_cfg = _parse_frame_config(sit_cfg.frame)

    font_size = sit_cfg.fontsize or D.LEGEND_FONT_SIZE
    ff = sit_cfg.fontfamily or D.FONT_FAMILY
    fc = sit_cfg.fontcolor or D.FONT_COLOR
    marker_size = sit_cfg.marker_size
    label_gap = sit_cfg.label_gap
    row_spacing = sit_cfg.row_spacing
    col_gap = sit_cfg.col_gap
    n_cols = max(1, sit_cfg.columns_n)

    svg = map_obj.svg
    vb = map_obj.main.viewbox

    legend_x, legend_y = compute_legend_position(sit_cfg, vb)

    layer_name = f"legend_situation_{layer_id}"
    legend_group = svg.add_overlay_group(layer_name, z_order=D.Z_LEGEND)

    y_cursor = legend_y
    y_cursor = draw_legend_title(legend_group, legend_x, y_cursor, sit_cfg, align="left")
    y_cursor = draw_legend_subtitle(legend_group, legend_x, y_cursor, sit_cfg, align="left")

    content_top = y_cursor

    # Marker slot sized on the largest category marker so the legend
    # shows each marker at its on-map size while rows stay aligned.
    cat_items = list(categories.items())
    slot = max([marker_size] + [mcfg.size for _, mcfg in cat_items])
    half_marker = slot / 2.0
    row_h = max(slot, font_size) + row_spacing

    # Estimate per-column width (used for col offsets and frame)
    n_rows = math.ceil(len(cat_items) / n_cols)
    max_label_px = max(
        (len(mcfg.label or cat) * font_size * 0.6) for cat, mcfg in cat_items
    ) if cat_items else 100.0
    col_width = slot + label_gap + max_label_px + col_gap

    for i, (cat_name, mcfg) in enumerate(cat_items):
        col_idx = i % n_cols
        row_idx = i // n_cols

        x0 = legend_x + col_idx * col_width
        row_y = content_top + row_idx * row_h + half_marker

        # Marker preview
        _draw_legend_marker(
            legend_group,
            x0 + half_marker, row_y,
            mcfg.shapes, mcfg.size,
            mcfg.fill, mcfg.stroke, mcfg.stroke_width, mcfg.fill_opacity,
            inner_fill=mcfg.inner_fill, inner_stroke=mcfg.inner_stroke,
        )

        # Label
        label = mcfg.label or cat_name
        label_elem = ET.SubElement(
            legend_group, "text",
            x=f"{x0 + slot + label_gap:.2f}",
            y=f"{row_y + font_size * 0.35:.2f}",
        )
        label_elem.text = label
        label_elem.set("font-size", str(font_size))
        label_elem.set("fill", fc)
        label_elem.set("font-family", ff)

    total_h = n_rows * row_h
    content_w = n_cols * col_width - col_gap
    content_h = total_h + (content_top - legend_y)

    # Frame
    if frame_cfg.enabled:
        title_offset = (sit_cfg.title_fontsize or D.LEGEND_TITLE_FONT_SIZE) * 0.3
        draw_legend_frame(
            legend_group, svg._defs,
            legend_x, legend_y - title_offset,
            content_w, content_h + title_offset,
            frame_cfg,
        )

    bbox = (legend_x, legend_y, legend_x + content_w, legend_y + content_h)
    record_legend(map_obj, stacked, bbox)
    return bbox


# ============================================================================
# Main drawing function
# ============================================================================

def _get_points(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Extract point coordinates from a GeoDataFrame.

    For polygon geometries, uses the centroid.
    """
    result = gdf.copy()
    geom_types = result.geometry.geom_type.unique()
    needs_centroid = any(t in ("Polygon", "MultiPolygon") for t in geom_types)
    if needs_centroid:
        result = result.copy()
        result.geometry = result.geometry.centroid
    return result


def add_situation(
    map_obj: Any,
    gdf: gpd.GeoDataFrame,
    *,
    column: str | None = None,
    symbol: dict[str, dict[str, Any]] | None = None,
    marker: str = SITUATION_DEFAULT_MARKER,
    fill: str = SITUATION_DEFAULT_COLOR,
    size: float = SITUATION_DEFAULT_SIZE,
    stroke: str = SITUATION_DEFAULT_STROKE,
    stroke_width: float = SITUATION_DEFAULT_STROKE_WIDTH,
    fill_opacity: float = SITUATION_DEFAULT_FILL_OPACITY,
    inner_fill: str | None = None,
    inner_stroke: str | None = None,
    label: str | None = None,
    legend_params: dict[str, Any] | None = None,
    on_zoom: bool = True,
    on_cartouches: bool = True,
    detail: Any = None,
    detail_join: Any = None,
) -> int:
    """Add a situation (point symbol) layer to the map.

    Two modes:
    1. **Categorical**: pass ``column`` + ``symbol`` dict mapping each
       category value to its marker config.
    2. **Uniform**: pass ``marker``, ``fill``, ``size`` etc. directly,
       all points get the same symbol.

    Parameters
    ----------
    detail : GeoDataFrame or dict, optional
        Finer geometry for the zoom window and the cartouches: the markers
        are placed from it instead of from *gdf*, and keep the values and
        colours of *gdf* through *detail_join*. A GeoDataFrame applies to the
        zoom and every cartouche; a dict maps ``"zoom"``, ``"cartouches"`` or a
        cartouche index to a GeoDataFrame. See :mod:`mappyng.detail`.
    detail_join : str, tuple or None
        Key shared by *gdf* and *detail* (column name, a
        ``(gdf_column, detail_column)`` pair, or None for the index).

    Returns
    -------
    int
        Layer ID for interactivity tracking.
    """
    layer_id = map_obj._next_layer_id("situation")

    # Convert polygons to centroids
    gdf_pts = _get_points(gdf)

    # Build category to MarkerConfig mapping
    categories: dict[str, MarkerConfig] = {}

    if column and symbol:
        # Categorical mode. The >N-categories readability check lives
        # in Situation.validate(), emitted at construction.
        for cat_value, sym_dict in symbol.items():
            categories[_category_key(cat_value)] = _parse_symbol_config(sym_dict)
        if column in gdf.columns:
            present = {_category_key(v) for v in gdf[column].dropna().unique()}
            unmapped = sorted(present - set(categories))
            if unmapped:
                shown = ", ".join(repr(c) for c in unmapped[:5])
                more = (f" and {len(unmapped) - 5} more"
                        if len(unmapped) > 5 else "")
                warnings.warn(
                    f"Situation: {len(unmapped)} value(s) of {column!r} have "
                    f"no entry in symbol ({shown}{more}). Their points are "
                    f"drawn with a red cross. Add them to symbol, or filter "
                    f"the data.",
                    UserWarning, stacklevel=2,
                )
    else:
        # Uniform mode, single marker for all points
        shapes = _parse_marker(marker)
        default_cfg = MarkerConfig(
            shapes=shapes, fill=fill, size=size,
            stroke=stroke, stroke_width=stroke_width,
            fill_opacity=fill_opacity,
            inner_fill=inner_fill, inner_stroke=inner_stroke,
            label=label,
        )
        categories["__all__"] = default_cfg
    _check_markers(categories)

    layer_name = f"situation_{layer_id}"
    z = D.Z_SITUATION
    id_prefix = f"situ-{layer_id}-"

    # --- Render on main viewport ---
    _draw_situation_on_viewport(
        map_obj.main, gdf_pts, column, categories,
        layer_name, z, id_prefix, map_obj.bbox, map_obj,
    )

    # Finer geometry for the zoom and cartouches: markers are placed from it,
    # attributes stay those of `gdf`.
    details = normalize_detail(detail)
    _detail_cache: dict[int, gpd.GeoDataFrame] = {}

    def _points_for(target: Any) -> gpd.GeoDataFrame:
        finer = detail_for(details, target)
        if finer is None:
            return gdf_pts
        if id(finer) not in _detail_cache:
            _detail_cache[id(finer)] = _get_points(
                join_detail(gdf, finer, detail_join, what="situation"))
        return _detail_cache[id(finer)]

    # --- Render on zoom ---
    if on_zoom and map_obj._zoom_viewport and map_obj._zoom_bbox:
        zoom_gdf = map_obj._clip_gdf(_points_for(ZOOM), map_obj._zoom_bbox)
        if not zoom_gdf.empty:
            _draw_situation_on_viewport(
                map_obj._zoom_viewport, zoom_gdf, column, categories,
                layer_name, z, None, map_obj._zoom_bbox, map_obj,
            )

    # --- Render on cartouches ---
    if on_cartouches and map_obj.cartouche_params:
        for index, vp in map_obj._cartouche_viewports.items():
            cart_gdf = map_obj._prepare_cartouche_data(
                _points_for(index), map_obj.cartouche_params[index])
            if cart_gdf is not None and not cart_gdf.empty:
                _draw_situation_on_viewport(
                    vp, cart_gdf, column, categories,
                    layer_name, z, None, None, map_obj,
                )

    # --- Legend ---
    if legend_params is not None and legend_params is not False:
        legend_cats = {k: v for k, v in categories.items() if k != "__all__"}
        if not legend_cats and "__all__" in categories:
            cfg = categories["__all__"]
            if cfg.label:
                legend_cats = {cfg.label: cfg}
        if legend_cats:
            legend_bbox = _draw_situation_legend(map_obj, legend_cats, legend_params, layer_id)
            if legend_bbox is not None:
                map_obj.overflow.register(*legend_bbox)

    return layer_id


def _draw_situation_on_viewport(
    viewport: SvgViewport,
    gdf: gpd.GeoDataFrame,
    column: str | None,
    categories: dict[str, MarkerConfig],
    layer_name: str,
    z_order: int,
    id_prefix: str | None,
    bbox: list | None,
    map_obj: Any,
) -> None:
    """Draw situation markers on a single viewport."""
    vb = viewport.viewbox

    # Clip to bbox if provided
    if bbox is not None:
        from shapely.geometry import box as geo_box
        clip_geom = geo_box(*bbox)
        try:
            gdf = gdf.clip(mask=clip_geom)
            gdf = gdf[~gdf.is_empty]
        except GEO_ERRORS as e:
            warnings.warn(
                f"Situation: clipping to the bbox failed ({e}); "
                f"the data is drawn unclipped."
            )

    if gdf.empty:
        return

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        # Determine category
        if column and column in row.index:
            cat = _category_key(row[column])
        else:
            cat = "__all__"

        if cat in categories:
            mcfg = categories[cat]
        elif "__all__" in categories:
            mcfg = categories["__all__"]
        else:
            # Missing category, render with warning marker
            mcfg = MarkerConfig(
                shapes=_parse_marker(SITUATION_MISSING_MARKER),
                fill=SITUATION_MISSING_COLOR,
                size=SITUATION_DEFAULT_SIZE,
                stroke="#ffffff",
                stroke_width=SITUATION_DEFAULT_STROKE_WIDTH,
                fill_opacity=1.0,
            )

        # Get point coordinates
        points = []
        if isinstance(geom, Point):
            points.append((geom.x, geom.y))
        elif isinstance(geom, MultiPoint):
            for pt in geom.geoms:
                points.append((pt.x, pt.y))

        for px, py in points:
            cx, cy = vb.geo_to_svg(px, py)
            eid = f"{id_prefix}{idx}" if id_prefix else None

            _draw_marker_on_viewport(
                viewport, layer_name, cx, cy,
                mcfg.shapes, mcfg.size, mcfg.fill, mcfg.stroke,
                mcfg.stroke_width, mcfg.fill_opacity, z_order,
                elem_id=eid,
                inner_fill=mcfg.inner_fill,
                inner_stroke=mcfg.inner_stroke,
            )
