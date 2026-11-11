"""
Shared legend primitives for mappyng.

Provides reusable building blocks (title, no-data indicator, hatch patterns,
legend frame) that any legend type (choropleth, proportional, categorical...)
can compose.

All default values are imported from :mod:`mappyng.defaults`.
"""

from __future__ import annotations

import dataclasses
import difflib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, cast

from . import defaults as D
from .config import Style
from .position import resolve_position

#: Accepted values of the ``swatch_shape`` legend option.
SWATCH_SHAPES = ("rect", "rounded", "circle")


def add_swatch(parent: ET.Element, x: float, y: float, width: float,
               height: float, shape: str = D.LEGEND_SWATCH_SHAPE,
               radius: float | None = None, **attrs: str) -> ET.Element:
    """Add a legend swatch to *parent* and return it.

    Parameters
    ----------
    parent : Element
        Group receiving the swatch.
    x, y, width, height : float
        Box of the swatch (SVG px).
    shape : str
        ``"rect"``, ``"rounded"`` (rectangle with rounded corners) or
        ``"circle"`` (disc centred in the box, diameter equal to the
        shorter side).
    radius : float, optional
        Corner radius of a ``"rounded"`` swatch. Defaults to a quarter of
        the shorter side.
    **attrs
        SVG attributes (``fill``, ``stroke``, ``id``...).
    """
    if shape == "circle":
        return ET.SubElement(
            parent, "circle",
            cx=f"{x + width / 2:.2f}", cy=f"{y + height / 2:.2f}",
            r=f"{min(width, height) / 2:.2f}", **attrs,  # type: ignore[arg-type]
        )
    rect = ET.SubElement(
        parent, "rect",
        x=f"{x:.2f}", y=f"{y:.2f}",
        width=f"{width:.2f}", height=f"{height:.2f}", **attrs,  # type: ignore[arg-type]
    )
    if shape == "rounded":
        if radius is None:
            radius = min(width, height) * D.LEGEND_SWATCH_ROUNDED_RATIO
        rect.set("rx", f"{radius:.2f}")
    return rect


# ============================================================================
# Legend frame configuration
# ============================================================================

@dataclass
class LegendFrameConfig:
    """Configuration for the optional legend background frame.

    Pass as ``frame=True`` (defaults) or ``frame={...}`` (overrides) in
    the legend params dict.

    Attributes
    ----------
    enabled : bool
        Show the frame (default False).
    fill : str
        Frame background color.
    fill_opacity : float
        Frame background opacity 0-1.
    stroke : str
        Frame border color.
    stroke_width : float
        Frame border width in SVG px.
    border_radius : float
        Frame corner radius in SVG px.
    padding : float
        Uniform inner padding on all four sides (SVG px). Used as fallback
        when individual side overrides are not set.
    padding_top : float or None
        Top padding override (SVG px). Falls back to ``padding`` when None.
    padding_right : float or None
        Right padding override (SVG px). Falls back to ``padding`` when None.
    padding_bottom : float or None
        Bottom padding override (SVG px). Falls back to ``padding`` when None.
    padding_left : float or None
        Left padding override (SVG px). Falls back to ``padding`` when None.
    shadow : bool
        Add a drop shadow behind the frame.
    shadow_dx : float
        Shadow horizontal offset (SVG px).
    shadow_dy : float
        Shadow vertical offset (SVG px).
    shadow_blur : float
        Shadow blur radius (SVG px).
    shadow_opacity : float
        Shadow opacity 0-1.
    """

    enabled: bool = D.LEGEND_FRAME
    fill: str = D.LEGEND_FRAME_FILL
    fill_opacity: float = D.LEGEND_FRAME_FILL_OPACITY
    stroke: str = D.LEGEND_FRAME_STROKE
    stroke_width: float = D.LEGEND_FRAME_STROKE_WIDTH
    border_radius: float = D.LEGEND_FRAME_BORDER_RADIUS
    padding: float = D.LEGEND_FRAME_PADDING
    padding_top: float | None = None
    padding_right: float | None = None
    padding_bottom: float | None = None
    padding_left: float | None = None
    shadow: bool = D.LEGEND_FRAME_SHADOW
    shadow_dx: float = D.LEGEND_FRAME_SHADOW_DX
    shadow_dy: float = D.LEGEND_FRAME_SHADOW_DY
    shadow_blur: float = D.LEGEND_FRAME_SHADOW_BLUR
    shadow_opacity: float = D.LEGEND_FRAME_SHADOW_OPACITY

    def effective_padding(self) -> tuple:
        """Return (top, right, bottom, left) padding values."""
        p = self.padding
        return (
            self.padding_top    if self.padding_top    is not None else p,
            self.padding_right  if self.padding_right  is not None else p,
            self.padding_bottom if self.padding_bottom is not None else p,
            self.padding_left   if self.padding_left   is not None else p,
        )


def _parse_frame_config(raw) -> LegendFrameConfig:
    """Parse a ``frame`` parameter into a :class:`LegendFrameConfig`.

    Accepts:
    - ``False`` / ``None``: disabled
    - ``True``: enabled with all defaults
    - ``dict``: enabled with overrides (unless it sets ``enabled`` to
      False); the ``padding`` key may be either a
      float (uniform) or a dict with keys ``top``, ``right``, ``bottom``,
      ``left`` (any omitted side falls back to ``D.LEGEND_FRAME_PADDING``).
    """
    if not raw:
        return LegendFrameConfig(enabled=False)
    if raw is True:
        return LegendFrameConfig(enabled=True)
    if isinstance(raw, dict):
        _check_options(LegendFrameConfig, raw, "legend frame")
        kwargs = {k: v for k, v in raw.items()
                  if k not in ("padding", "enabled")}
        if not raw.get("enabled", True):
            return LegendFrameConfig(enabled=False)
        padding_raw = raw.get("padding", D.LEGEND_FRAME_PADDING)
        if isinstance(padding_raw, dict):
            # Per-side dict: {"top": x, "right": y, "bottom": z, "left": w}
            default = D.LEGEND_FRAME_PADDING
            kwargs["padding"]        = default
            kwargs["padding_top"]    = padding_raw.get("top",    default)
            kwargs["padding_right"]  = padding_raw.get("right",  default)
            kwargs["padding_bottom"] = padding_raw.get("bottom", default)
            kwargs["padding_left"]   = padding_raw.get("left",   default)
        else:
            kwargs["padding"] = padding_raw
        return LegendFrameConfig(enabled=True, **kwargs)
    return LegendFrameConfig(enabled=False)


# ============================================================================
# Base legend configuration
# ============================================================================

@dataclass
class BaseLegendConfig:
    """Shared configuration fields for all legend types.

    All fields can be passed as keys in the ``legend`` dict of
    ``Choropleth``, ``Proportional``, and ``Situation``.
    ``None`` values are filled from the active style at render time.

    Attributes
    ----------
    title : str or None
        Legend title text.
    title_fontsize : int or None
        Title font size.  Defaults to style value.
    title_fontcolor : str or None
        Title font color.
    title_fontweight : str or None
        Title font weight (e.g. ``"bold"``).
    title_fontfamily : str or None
        Title font family.
    title_max_chars : int
        Maximum characters per line before title wraps (default 35).
    title_offset_x : float
        Additional horizontal offset for the title in SVG px (default 0).
    title_offset_y : float
        Additional vertical offset for the title in SVG px (default 0).
    subtitle : str or None
        Optional subtitle rendered below the title.
    subtitle_fontsize : int or None
        Subtitle font size.
    subtitle_fontcolor : str or None
        Subtitle font color.
    subtitle_fontweight : str or None
        Subtitle font weight.
    subtitle_fontfamily : str or None
        Subtitle font family.
    fontsize : int or None
        Legend item label font size.
    fontcolor : str or None
        Legend item label color.
    fontweight : str or None
        Legend item label weight.
    fontfamily : str or None
        Legend item label font family.
    hatch_color : str or None
        Hatch pattern color (used for choropleth swatch hatching).
    hatch_style : str or None
        Hatch pattern style.  Available: ``"///"`` , ``"\\\\"``,
        ``"xxx"``, ``"..."`` , ``"|||"``, ``"---"``.
    spacing : float
        Extra vertical spacing added to the auto-computed legend position
        as a fraction of the content height (default 0.01).
    position : dict, tuple or None
        Manual position of the legend's top-left corner. Fractions
        ``{"x": frac, "y": frac}`` or percentages (``"40%"``) where (0, 0)
        = top-left and (1, 1) = bottom-right of the content area; pixels
        ``{"px": x, "py": y}``; or geographic coordinates
        ``{"geo": (x, y)}`` (map CRS) / ``{"lon": ..., "lat": ...}``
        (WGS 84). When ``None``, position is computed automatically.
    frame : bool or dict or None
        Background frame behind the legend.  ``False``/``None`` = no frame,
        ``True`` = frame with defaults, dict = frame with overrides
        (see :class:`~mappyng.legend.LegendFrameConfig`).
    """

    title: str | None = None
    title_fontsize: int | None = None
    title_fontcolor: str | None = None
    title_fontweight: str | None = None
    title_fontfamily: str | None = None
    title_max_chars: int = D.LEGEND_TITLE_MAX_CHARS
    title_offset_x: float = 0.0
    """Horizontal offset applied to the legend title (pixels). Positive = right."""
    title_offset_y: float = 0.0
    """Vertical offset applied to the legend title (pixels). Positive = down."""
    subtitle: str | None = None
    subtitle_fontsize: int | None = None
    subtitle_fontcolor: str | None = None
    subtitle_fontweight: str | None = None
    subtitle_fontfamily: str | None = None
    fontsize: int | None = None
    fontcolor: str | None = None
    fontweight: str | None = None
    fontfamily: str | None = None
    hatch_color: str | None = None
    hatch_style: str | None = None
    spacing: float = D.LEGEND_SPACING
    position: Any = D.LEGEND_POSITION  # None or dict {"x": frac, "y": frac}
    frame: Any = None  # True, False, or dict of LegendFrameConfig overrides

    def resolve_defaults(self, style: Style, font_scale: float = 1.0) -> None:
        """Fill ``None`` fields from the active style.

        Parameters
        ----------
        font_scale : float
            Multiplier applied to all resolved font sizes (default 1.0 = no change).
        """
        self.title_fontsize = round((self.title_fontsize or style["legend_title_fontsize"]) * font_scale)
        self.title_fontcolor = self.title_fontcolor or style["legend_title_fontcolor"]
        self.title_fontweight = self.title_fontweight or style["legend_title_fontweight"]
        self.title_fontfamily = self.title_fontfamily or style["legend_title_fontfamily"]
        self.subtitle_fontsize = round((self.subtitle_fontsize or D.LEGEND_SUBTITLE_FONT_SIZE) * font_scale)
        self.subtitle_fontcolor = self.subtitle_fontcolor or style["legend_fontcolor"]
        self.subtitle_fontweight = self.subtitle_fontweight or D.LEGEND_SUBTITLE_FONT_WEIGHT
        self.subtitle_fontfamily = self.subtitle_fontfamily or style["legend_fontfamily"]
        self.fontsize = round((self.fontsize or style["legend_fontsize"]) * font_scale)
        self.fontcolor = self.fontcolor or style["legend_fontcolor"]
        self.fontweight = self.fontweight or style["legend_fontweight"]
        self.fontfamily = self.fontfamily or style["legend_fontfamily"]
        self.hatch_color = self.hatch_color or style["legend_hatch_color"]
        self.hatch_style = self.hatch_style or style["legend_hatch_style"]


def compute_legend_position(config: BaseLegendConfig, vb) -> tuple:
    """Compute (legend_x, legend_y) from config.position and a ViewBox.

    Parameters
    ----------
    config : BaseLegendConfig
        Legend configuration (reads ``position``).
    vb : ViewBox
        The main viewport's viewbox.

    Returns
    -------
    (legend_x, legend_y) : tuple of float

    ``config.position`` is ``None`` (default placement: left-aligned, below
    the map) or any form understood by
    :func:`mappyng.position.resolve_position`: fractions or percentages of
    the content area, SVG pixels (``{"px": x, "py": y}``) or geographic
    coordinates (``{"geo": (x, y)}``, ``{"lon": ..., "lat": ...}``).
    The point designates the top-left corner of the legend.
    """
    pos = config.position
    if pos is None:
        spacing_px = getattr(config, "spacing", 0.0) * vb.content_height
        return (
            vb.content_x,
            vb.content_y + vb.content_height + D.LEGEND_BELOW_MAP_GAP + spacing_px,
        )
    return cast(tuple[float, float], resolve_position(pos, vb))


# ============================================================================
# Shared SVG helpers
# ============================================================================

def ensure_hatch_pattern(
    defs: ET.Element,
    pattern_id: str,
    color: str,
    size: int = D.LEGEND_HATCH_PATTERN_SIZE,
    style: str = D.LEGEND_HATCH_STYLE,
) -> None:
    """Add a hatch ``<pattern>`` to *defs* if not already present.

    Parameters
    ----------
    style : str
        Hatch style. Supported values (matplotlib-compatible names):

        - ``"///"``, diagonal lines at 45° (default)
        - ``"\\\\\\\\"``, ``"back"``, diagonal lines at 135°
        - ``"xxx"``, cross-hatching (45° + 135°)
        - ``"..."``, dot grid
        - ``"|||"``, vertical lines
        - ``"---"``, horizontal lines

        Unrecognised values fall back to ``"///"``.
    """
    for child in defs:
        if child.get("id") == pattern_id:
            return

    lw = str(D.LEGEND_HATCH_LINE_WIDTH)
    s = str(size)

    # Normalise style aliases
    _style = style.strip() if style else "///"
    if _style in ("back", "backslash") or (
            _style and set(_style) == {"\\"}):
        _style = "back"
    elif _style in ("xxx", "x", "cross_hatch"):
        _style = "xxx"
    elif _style in ("...", "dots", "dot"):
        _style = "..."
    elif _style in ("|||", "vertical", "vert"):
        _style = "|||"
    elif _style in ("---", "horizontal", "horiz"):
        _style = "---"
    else:
        _style = "///"

    if _style == "///":
        pat = ET.SubElement(defs, "pattern", id=pattern_id,
                            width=s, height=s, patternUnits="userSpaceOnUse",
                            patternTransform="rotate(45)")
        line = ET.SubElement(pat, "line", x1="0", y1="0", x2="0", y2=s, stroke=color)
        line.set("stroke-width", lw)

    elif _style == "back":
        pat = ET.SubElement(defs, "pattern", id=pattern_id,
                            width=s, height=s, patternUnits="userSpaceOnUse",
                            patternTransform="rotate(-45)")
        line = ET.SubElement(pat, "line", x1="0", y1="0", x2="0", y2=s, stroke=color)
        line.set("stroke-width", lw)

    elif _style == "xxx":
        pat = ET.SubElement(defs, "pattern", id=pattern_id,
                            width=s, height=s, patternUnits="userSpaceOnUse")
        l1 = ET.SubElement(pat, "line",
                           x1="0", y1="0", x2=s, y2=s, stroke=color)
        l1.set("stroke-width", lw)
        l2 = ET.SubElement(pat, "line",
                           x1=s, y1="0", x2="0", y2=s, stroke=color)
        l2.set("stroke-width", lw)

    elif _style == "...":
        half = str(size / 2)
        r = str(max(1, size // 5))
        pat = ET.SubElement(defs, "pattern", id=pattern_id,
                            width=s, height=s, patternUnits="userSpaceOnUse")
        ET.SubElement(pat, "circle", cx="0", cy="0", r=r, fill=color)
        ET.SubElement(pat, "circle", cx=s, cy="0", r=r, fill=color)
        ET.SubElement(pat, "circle", cx="0", cy=s, r=r, fill=color)
        ET.SubElement(pat, "circle", cx=s, cy=s, r=r, fill=color)
        ET.SubElement(pat, "circle", cx=half, cy=half, r=r, fill=color)

    elif _style == "|||":
        pat = ET.SubElement(defs, "pattern", id=pattern_id,
                            width=s, height=s, patternUnits="userSpaceOnUse")
        line = ET.SubElement(pat, "line", x1="0", y1="0", x2="0", y2=s, stroke=color)
        line.set("stroke-width", lw)

    elif _style == "---":
        pat = ET.SubElement(defs, "pattern", id=pattern_id,
                            width=s, height=s, patternUnits="userSpaceOnUse")
        line = ET.SubElement(pat, "line", x1="0", y1="0", x2=s, y2="0", stroke=color)
        line.set("stroke-width", lw)


def draw_legend_title(
    parent: ET.Element,
    x: float,
    y: float,
    config: BaseLegendConfig,
    align: str | None = None,
) -> float:
    """Draw the legend title text and return the updated *y* cursor.

    Parameters
    ----------
    parent : ET.Element
        ``<g>`` element to append the ``<text>`` to.
    x : float
        Horizontal position of the legend title (SVG px).
    y : float
        Baseline *y* for the title text.
    config : BaseLegendConfig
        Legend configuration (title text + font settings).
    align : str, optional
        ``"left"`` or ``"center"``. Defaults to ``D.LEGEND_ALIGN``.

    Returns
    -------
    float
        Updated *y* position below the title, ready for the next element.
    """
    if not config.title:
        return y

    import textwrap

    align = align or D.LEGEND_ALIGN
    anchor = "start" if align == "left" else "middle"
    title_size = config.title_fontsize or D.LEGEND_TITLE_FONT_SIZE
    tx = x + (config.title_offset_x or 0.0)
    ty = y + (config.title_offset_y or 0.0)
    max_chars = getattr(config, "title_max_chars", D.LEGEND_TITLE_MAX_CHARS)
    line_h = title_size * 1.2

    attrs = {
        "text-anchor": anchor,
        "font-size": str(title_size),
        "font-weight": config.title_fontweight or D.LEGEND_TITLE_FONT_WEIGHT,
        "font-family": config.title_fontfamily or D.FONT_FAMILY,
        "fill": config.title_fontcolor or config.fontcolor or D.FONT_COLOR,
    }

    lines = textwrap.wrap(config.title, max_chars) if len(config.title) > max_chars else [config.title]
    for i, line in enumerate(lines):
        ET.SubElement(
            parent, "text",
            x=f"{tx:.2f}", y=f"{ty + i * line_h:.2f}",
            **attrs,  # type: ignore[arg-type]
        ).text = line

    return ty + len(lines) * line_h + D.LEGEND_TITLE_SPACING


def draw_legend_subtitle(
    parent: ET.Element,
    x: float,
    y: float,
    config: BaseLegendConfig,
    align: str | None = None,
) -> float:
    """Draw the legend subtitle text and return the updated *y* cursor.

    Parameters
    ----------
    parent : ET.Element
        ``<g>`` element to append the ``<text>`` to.
    x : float
        Horizontal position of the subtitle (SVG px).
    y : float
        Baseline *y* for the subtitle text.
    config : BaseLegendConfig
        Legend configuration (subtitle text + font settings).
    align : str, optional
        ``"left"`` or ``"center"``. Defaults to ``D.LEGEND_ALIGN``.

    Returns
    -------
    float
        Updated *y* position below the subtitle, ready for the next element.
    """
    if not config.subtitle:
        return y

    align = align or D.LEGEND_ALIGN
    anchor = "start" if align == "left" else "middle"
    subtitle_size = config.subtitle_fontsize or D.LEGEND_SUBTITLE_FONT_SIZE
    # Subtitle is part of the title block, follow its offset. The vertical
    # offset is already in *y* when a title was drawn above.
    sx = x + (config.title_offset_x or 0.0)
    sy = y if config.title else y + (config.title_offset_y or 0.0)

    ET.SubElement(
        parent, "text",
        x=f"{sx:.2f}", y=f"{sy:.2f}",
        **{  # type: ignore[arg-type]
            "text-anchor": anchor,
            "font-size": str(subtitle_size),
            "font-weight": config.subtitle_fontweight or D.LEGEND_SUBTITLE_FONT_WEIGHT,
            "font-family": config.subtitle_fontfamily or D.FONT_FAMILY,
            "fill": config.subtitle_fontcolor or config.fontcolor or D.FONT_COLOR,
        },
    ).text = config.subtitle

    return sy + subtitle_size + D.LEGEND_SUBTITLE_SPACING


def draw_nodata_indicator(
    parent: ET.Element,
    defs: ET.Element,
    x: float,
    y: float,
    swatch_width: float,
    swatch_height: float,
    label_y: float,
    config: BaseLegendConfig,
    legend_prefix: str = "choropleth",
) -> None:
    """Draw a hatched swatch + 'N/A' label for missing data.

    Parameters
    ----------
    parent : ET.Element
        Legend ``<g>`` group.
    defs : ET.Element
        Document ``<defs>`` for the hatch pattern.
    x, y : float
        Top-left corner of the N/A swatch.
    swatch_width, swatch_height : float
        Swatch dimensions.
    label_y : float
        Baseline *y* for the label text.
    config : BaseLegendConfig
        Legend configuration.
    legend_prefix : str
        CSS class prefix (e.g. ``"choropleth"`` or ``"proportional"``).
    """
    hc = config.hatch_color or D.LEGEND_HATCH_COLOR
    hs = config.hatch_style or D.LEGEND_HATCH_STYLE
    fc = config.fontcolor or D.FONT_COLOR
    ff = config.fontfamily or D.FONT_FAMILY
    font_size = config.fontsize or D.LEGEND_FONT_SIZE

    pattern_id = f"hatch-legend-{legend_prefix}"
    ensure_hatch_pattern(defs, pattern_id, hc, style=hs)

    rect = ET.SubElement(
        parent, "rect",
        x=f"{x:.2f}", y=f"{y:.2f}",
        width=f"{swatch_width:.2f}", height=f"{swatch_height:.2f}",
        fill=f"url(#{pattern_id})",
        stroke=hc,
        id=f"{legend_prefix}-legend-nodata",
    )
    rect.set("stroke-width", str(D.LEGEND_SWATCH_STROKE_WIDTH))
    rect.set("class", f"{legend_prefix}-legend {legend_prefix}-nodata")

    ET.SubElement(
        parent, "text",
        x=f"{x + swatch_width / 2:.2f}",
        y=f"{label_y:.2f}",
        **{  # type: ignore[arg-type]
            "font-size": str(font_size),
            "font-family": ff,
            "fill": fc,
            "text-anchor": "middle",
        },
    ).text = D.LEGEND_NODATA_LABEL


# ============================================================================
# Legend frame
# ============================================================================

def draw_legend_frame(
    legend_g: ET.Element,
    defs: ET.Element,
    x: float,
    y: float,
    width: float,
    height: float,
    frame_cfg: LegendFrameConfig,
) -> None:
    """Draw a background frame (rect) behind the legend content.

    The frame ``<rect>`` is inserted as the **first** child of *legend_g*
    so it sits behind all other legend elements.

    Parameters
    ----------
    legend_g : ET.Element
        The ``<g>`` that contains all legend content.
    defs : ET.Element
        Document ``<defs>`` for optional shadow filter.
    x, y : float
        Top-left corner of the content area (before padding).
    width, height : float
        Size of the content area (before padding).
    frame_cfg : LegendFrameConfig
        Frame styling options.
    """
    if not frame_cfg.enabled:
        return

    pt, pr, pb, pl = frame_cfg.effective_padding()
    fx = x - pl
    fy = y - pt
    fw = width + pl + pr
    fh = height + pt + pb

    attrs = {
        "x": f"{fx:.2f}",
        "y": f"{fy:.2f}",
        "width": f"{fw:.2f}",
        "height": f"{fh:.2f}",
        "fill": frame_cfg.fill,
        "fill-opacity": f"{frame_cfg.fill_opacity:.2f}",
        "stroke": frame_cfg.stroke,
        "stroke-width": str(frame_cfg.stroke_width),
    }

    if frame_cfg.border_radius > 0:
        attrs["rx"] = f"{frame_cfg.border_radius:.1f}"
        attrs["ry"] = f"{frame_cfg.border_radius:.1f}"

    filter_ref = None
    if frame_cfg.shadow:
        # Unique within this document: depends only on the shadows already in
        # its <defs>, not on process-wide state.
        n_shadows = sum(
            1 for el in defs
            if (el.get("id") or "").startswith("legend-frame-shadow-")
        )
        fid = f"legend-frame-shadow-{n_shadows + 1}"
        _ensure_shadow_filter(
            defs, fid,
            frame_cfg.shadow_dx, frame_cfg.shadow_dy,
            frame_cfg.shadow_blur, frame_cfg.shadow_opacity,
        )
        filter_ref = f"url(#{fid})"

    if filter_ref:
        attrs["filter"] = filter_ref

    frame_rect = ET.Element("rect", **attrs)  # type: ignore[arg-type]
    frame_rect.set("class", "legend-frame")
    # Insert as first child so it's behind everything
    legend_g.insert(0, frame_rect)


# ---------------------------------------------------------------------------
# Composite primitives shared by the choropleth, factor and proportional legends
# ---------------------------------------------------------------------------

def legend_fonts(config: BaseLegendConfig) -> tuple:
    """Return the resolved ``(font_size, font_color, font_family)`` of a legend."""
    return (
        config.fontsize or D.LEGEND_FONT_SIZE,
        config.fontcolor or D.FONT_COLOR,
        config.fontfamily or D.FONT_FAMILY,
    )


def estimate_text_width(text: str, font_size: float) -> float:
    """Rough rendered width (SVG px) of *text*, used to size legend boxes."""
    return len(text) * font_size * 0.55


def add_legend_text(
    parent: ET.Element, x: float, y: float, text: str,
    font_size: float, font_family: str, fill: str,
    anchor: str | None = "start", **extra: str,
) -> ET.Element:
    """Add a ``<text>`` element positioned at (*x*, *y*) and return it.

    Attributes are written in a fixed order: font size, family, fill, then
    ``text-anchor`` (skipped when *anchor* is None), then *extra*
    (e.g. ``transform`` or ``font-weight``). Pass ``anchor=None`` and put
    ``text-anchor`` in *extra* to place the anchor after other attributes.
    """
    attrs = {"font-size": str(font_size), "font-family": font_family,
             "fill": fill}
    if anchor is not None:
        attrs["text-anchor"] = anchor
    attrs.update(extra)
    el = ET.SubElement(parent, "text", x=f"{x:.2f}", y=f"{y:.2f}", **attrs)  # type: ignore[arg-type]
    el.text = text
    return el


def add_legend_swatch(
    parent: ET.Element, x: float, y: float, width: float, height: float,
    config: Any, *, fill: str, stroke: str, id: str,
    css_class: str | None = None,
) -> ET.Element:
    """Add a legend swatch with the legend's shape and standard stroke width.

    *config* is any legend config exposing ``swatch_shape`` and
    ``swatch_radius`` (for example :class:`ChoroplethLegendConfig`).
    """
    sw = add_swatch(
        parent, x, y, width, height, config.swatch_shape,
        config.swatch_radius, fill=fill, stroke=stroke, id=id,
    )
    sw.set("stroke-width", str(D.LEGEND_SWATCH_STROKE_WIDTH))
    if css_class is not None:
        sw.set("class", css_class)
    return sw


def ensure_nodata_hatch(svg_doc, config: BaseLegendConfig,
                        pattern_id: str) -> tuple:
    """Register the no-data hatch pattern and return ``(fill_url, hatch_color)``."""
    hc = config.hatch_color or D.LEGEND_HATCH_COLOR
    hs = config.hatch_style or D.LEGEND_HATCH_STYLE
    ensure_hatch_pattern(svg_doc._defs, pattern_id, hc, style=hs)
    return f"url(#{pattern_id})", hc


def begin_legend_group(svg_doc, group_id: str) -> ET.Element:
    """Create the ``<g>`` of a legend in the legend overlay layer.

    Its id is *group_id*, or ``group_id-2``, ``group_id-3``... when the map
    already holds a legend of that kind, so ids stay unique. The ids of the
    elements inside are derived from it (see :func:`legend_id_suffix`).
    """
    layer = svg_doc.get_overlay_layer("legend", z_order=D.Z_LEGEND)
    taken = {child.get("id") for child in layer}
    unique, n = group_id, 1
    while unique in taken:
        n += 1
        unique = f"{group_id}-{n}"
    return ET.SubElement(layer, "g", id=unique)


def legend_id_suffix(legend_g: ET.Element, group_id: str) -> str:
    """Suffix that tells this legend's ids apart: ``""``, ``"-2"``..."""
    return (legend_g.get("id") or group_id)[len(group_id):]


def _check_options(cls: type, options: dict, what: str) -> None:
    """Raise in plain language when *options* holds a key *cls* lacks."""
    known = [f.name for f in dataclasses.fields(cls)]
    unknown = [k for k in options if k not in known]
    if not unknown:
        return
    hints = []
    for key in unknown:
        close = difflib.get_close_matches(str(key), known, n=1)
        hints.append(f"{key!r} (did you mean {close[0]!r}?)" if close
                     else repr(key))
    raise ValueError(
        f"Unknown {what} option(s): {', '.join(hints)}. Available options: "
        f"{', '.join(sorted(known))}."
    )


def make_legend_config(cls: type, options: dict | None, what: str = "legend"):
    """Build the legend config *cls* from a dict of options.

    An unknown option (typically a typo) raises a ``ValueError`` that names
    it and lists the accepted ones.
    """
    options = dict(options or {})
    _check_options(cls, options, what)
    return cls(**options)


def stack_legend(map_obj, config: BaseLegendConfig) -> bool:
    """Place a legend with no explicit position below the previous one.

    Legends without a ``position`` all default to the same spot under the
    map. From the second one on, the legend is moved under the lowest
    legend placed automatically so far. Returns True when the legend is
    placed automatically; pass the result to :func:`record_legend`.
    """
    if config.position is not None:
        return False
    bottom = map_obj._state.legend_bottom
    if bottom is not None:
        # The title baseline sits on the anchor: leave room for the text.
        title_h = (config.title_fontsize or 0) if config.title else 0
        config.position = {
            "px": map_obj.main.viewbox.content_x,
            "py": bottom + D.LEGEND_STACK_GAP + title_h,
        }
    return True


def record_legend(map_obj, stacked: bool, bbox) -> None:
    """Remember the bottom of an automatically placed legend."""
    if not stacked or bbox is None:
        return
    previous = map_obj._state.legend_bottom
    map_obj._state.legend_bottom = (
        bbox[3] if previous is None else max(previous, bbox[3]))


def begin_legend(svg_doc, group_id: str, config: BaseLegendConfig, vb) -> tuple:
    """Open a legend: group, position, title and subtitle.

    Returns ``(legend_g, legend_x, legend_y, y_cursor)`` where *y_cursor* is
    the y position just below the title block.
    """
    legend_x, legend_y = compute_legend_position(config, vb)
    legend_g = begin_legend_group(svg_doc, group_id)
    y_cursor = draw_legend_title(
        legend_g, legend_x, legend_y, config, align="left",
    )
    y_cursor = draw_legend_subtitle(
        legend_g, legend_x, y_cursor, config, align="left",
    )
    return legend_g, legend_x, legend_y, y_cursor


def draw_config_frame(legend_g: ET.Element, svg_doc, config: BaseLegendConfig,
                      x: float, y: float, width: float, height: float) -> None:
    """Draw the frame requested by ``config.frame`` (no-op when disabled)."""
    frame_cfg = _parse_frame_config(config.frame)
    if frame_cfg.enabled:
        draw_legend_frame(legend_g, svg_doc._defs, x, y, width, height,
                          frame_cfg)


def _ensure_shadow_filter(
    defs: ET.Element,
    filter_id: str,
    dx: float, dy: float,
    blur: float, opacity: float,
) -> None:
    """Add a drop-shadow ``<filter>`` to *defs* if not present."""
    for child in defs:
        if child.get("id") == filter_id:
            return

    margin = 30
    f = ET.SubElement(
        defs, "filter", id=filter_id,
        x=f"-{margin}%", y=f"-{margin}%",
        width=f"{100 + 2 * margin}%", height=f"{100 + 2 * margin}%",
    )
    ET.SubElement(f, "feDropShadow", **{  # type: ignore[arg-type]
        "dx": str(dx), "dy": str(dy),
        "stdDeviation": str(blur),
        "flood-color": "#000000",
        "flood-opacity": str(opacity),
    })
