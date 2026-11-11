"""Choropleth legends: configuration and SVG drawing (classed, histogram, factor)."""

from __future__ import annotations

import math
import textwrap
import warnings
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any  # noqa: F401 - resolves inherited annotations (docs)

import numpy as np

from . import defaults as D
from .legend import (
    SWATCH_SHAPES,
    BaseLegendConfig,
    add_legend_swatch,
    add_legend_text,
    begin_legend,
    begin_legend_group,
    compute_legend_position,
    draw_config_frame,
    draw_legend_title,
    ensure_nodata_hatch,
    estimate_text_width,
    legend_fonts,
    legend_id_suffix,
)
from .renderer import SvgViewport

# ============================================================================
# Legend
# ============================================================================

@dataclass
class ChoroplethLegendConfig(BaseLegendConfig):
    """Choropleth-specific legend configuration.

    Inherits all shared fields from :class:`~mappyng.legend.BaseLegendConfig`.
    Pass as the ``legend`` dict in :meth:`~mappyng.Map.add_choropleth`.

    Attributes
    ----------
    decimals : int
        Number of decimal places for class boundary labels (default 1).
    orientation : str
        Legend layout: ``"horizontal"`` (default) or ``"vertical"``.
    swatch_width : float
        Width of each color swatch in horizontal mode (SVG px).
    swatch_size : float or None
        Sets the swatch width for both horizontal and vertical modes at once.
        Height is always derived as ``swatch_size / phi``.  When ``None``,
        ``swatch_width`` and ``vertical_swatch_width`` are used independently.
    swatch_height : float or None
        Height of each color swatch in horizontal mode.
        Defaults to ``swatch_width / phi`` (golden ratio).
    swatch_spacing : float
        Gap between swatches (SVG px).
    swatch_shape : str
        Swatch shape: ``"rect"`` (default), ``"rounded"`` (rectangle with
        rounded corners) or ``"circle"`` (disc, diameter equal to the
        shorter side of the swatch).
    swatch_radius : float or None
        Corner radius of ``"rounded"`` swatches (SVG px). Defaults to a
        quarter of the shorter side.
    label_rotation : float
        Rotation of bin labels in degrees (0 = horizontal, default 0).
    label_position : str
        Horizontal legend label placement: ``"border"`` (default, n+1
        labels at swatch edges) or ``"center"`` (n labels centered inside
        each swatch).
    label_format : str
        Label content when ``label_position="center"``: ``"value"`` (lower
        bound only) or ``"range"`` (``[min, max]`` interval).
    range_format : str
        Wording of a ``"range"`` label, with the placeholders ``{low}`` and
        ``{high}`` (default ``"from {low} to {high}"``; for French,
        ``"de {low} à {high}"``).
    label_anchor : str
        SVG ``text-anchor`` for rotated labels: ``"middle"`` (default) or
        ``"end"``.
    label_margin : float
        Gap in SVG px between the bottom of swatches and label baseline.
    nodata_gap : float
        Horizontal gap between the last class swatch and the N/A swatch.
    nodata_label_gap : float
        Gap between the N/A swatch right edge and its label.
    nodata_label : str or None
        Custom label for missing-value swatch.  Defaults to ``"N/A"``.
    nodata_position : str
        Vertical legend only: ``"right"`` (default) puts the N/A swatch in
        a column to the right of the classes, ``"below"`` puts it under the
        last class, ``nodata_gap`` below it, for narrow legends.
    vertical_swatch_width : float
        Swatch width in vertical mode (SVG px).
    vertical_swatch_height : float or None
        Swatch height in vertical mode.
        Defaults to ``vertical_swatch_width / phi`` (golden ratio).
    vertical_label_gap : float
        Gap between swatch right edge and label in vertical mode.
    labels : list of str or None
        Custom label list that replaces auto-generated range labels, one
        per class, drawn centred on each swatch. Must have length ==
        num_classes.
    """

    decimals: int = D.CHOROPLETH_DECIMALS
    orientation: str = D.CHOROPLETH_ORIENTATION
    swatch_size: float | None = None  # global width override for both modes
    swatch_width: float = D.CHOROPLETH_SWATCH_WIDTH
    swatch_height: float | None = None  # default: swatch_width / phi
    swatch_spacing: float = D.CHOROPLETH_SWATCH_SPACING
    swatch_shape: str = D.LEGEND_SWATCH_SHAPE
    swatch_radius: float | None = None
    label_rotation: float = D.CHOROPLETH_LABEL_ROTATION
    label_position: str = "border"
    """Horizontal legend label placement: 'border' (default, n+1 at swatch edges)
    or 'center' (n labels centered inside each swatch)."""
    label_format: str = "value"
    """Label content in center mode: 'value' (min bound) or 'range' ([min, max])."""
    range_format: str = "from {low} to {high}"
    """Wording of a 'range' label, with {low} and {high} placeholders."""
    label_anchor: str = "middle"
    """SVG text-anchor for rotated labels: 'end' or 'middle' (default).
    With 'middle', vertical offset is auto-adjusted to prevent overlap."""
    label_margin: float = D.CHOROPLETH_LABEL_MARGIN
    """Gap in pixels between the bottom of the swatches and the label baseline."""
    nodata_gap: float = D.LEGEND_NODATA_GAP
    """Horizontal gap in pixels between the last class swatch and the N/A swatch."""
    nodata_label_gap: float = D.LEGEND_NODATA_LABEL_GAP
    """Horizontal gap in pixels between the N/A swatch right edge and its label."""
    nodata_label: str | None = None
    """Custom label for the N/A swatch. Defaults to D.LEGEND_NODATA_LABEL ('N/A')."""
    nodata_position: str = "right"
    """Vertical legend: 'right' (N/A swatch in its own column) or 'below' (under the classes)."""
    # Vertical-specific overrides (used when orientation == "vertical")
    vertical_swatch_width: float = D.CHOROPLETH_VERTICAL_SWATCH_WIDTH
    vertical_swatch_height: float | None = None  # default: vertical_swatch_width / phi
    vertical_label_gap: float = D.CHOROPLETH_VERTICAL_LABEL_GAP
    # Custom label list (overrides auto-generated range labels)
    labels: list[str] | None = None
    decimal_sep: str = "."
    """Decimal separator. Use ',' for French convention (e.g. '12,5')."""
    thousands_sep: str = " "
    """Thousands separator. Default narrow space ('1 234'); use '' for none."""
    # Distribution histogram
    histogram: bool = False
    """Draw a mini distribution histogram to the right of the legend block."""
    histogram_bins: int = D.CHOROPLETH_HIST_DEFAULT_BINS
    """Number of bars in the histogram."""
    histogram_width: float = D.CHOROPLETH_HIST_WIDTH
    """Width of the histogram area (SVG px)."""
    histogram_height: float = D.CHOROPLETH_HIST_HEIGHT
    """Height of the histogram area (SVG px)."""
    histogram_gap: float = D.CHOROPLETH_HIST_GAP
    """Horizontal gap between legend block and histogram (SVG px)."""

    def __post_init__(self) -> None:
        if self.swatch_shape not in SWATCH_SHAPES:
            raise ValueError(
                f"Unknown legend swatch_shape {self.swatch_shape!r}. Use one "
                f"of {', '.join(repr(v) for v in SWATCH_SHAPES)}."
            )
        if self.nodata_position not in ("right", "below"):
            raise ValueError(
                f"Unknown legend nodata_position {self.nodata_position!r}. "
                f"Use 'right' or 'below'."
            )

    def resolve_defaults(self, style, font_scale: float = 1.0) -> None:
        super().resolve_defaults(style, font_scale)
        s = D.LEGEND_SWATCH_SCALE
        if self.swatch_radius is not None:
            self.swatch_radius = self.swatch_radius * s
        # swatch_size overrides both widths; height is always derived via PHI
        if self.swatch_size is not None:
            self.swatch_width = self.swatch_size
            self.vertical_swatch_width = self.swatch_size
            self.swatch_height = None
            self.vertical_swatch_height = None
        self.swatch_width = self.swatch_width * s
        if self.swatch_height is not None:
            self.swatch_height = self.swatch_height * s
        self.swatch_spacing = self.swatch_spacing * s
        self.vertical_swatch_width = self.vertical_swatch_width * s
        if self.vertical_swatch_height is not None:
            self.vertical_swatch_height = self.vertical_swatch_height * s
        self.label_margin = self.label_margin * font_scale
        self.nodata_gap = self.nodata_gap * s


@dataclass
class FactorLegend(ChoroplethLegendConfig):
    """Legend for a principal-component (factor) choropleth.

    A factor map shows the score of one component of a principal component
    analysis. The axis is diverging and centred on zero. This legend adds,
    around the usual class block, the elements such a map needs: the factor
    and its share of variance in the title, an interpretation text at each
    pole of the axis, and a methodology note. Pass it as the ``legend``
    argument of a :class:`~mappyng.Choropleth`; the layer's breaks and
    colours are reused as is.

    Attributes
    ----------
    variance : float or None
        Share of total variance carried by the factor, a fraction in
        ``[0, 1]``. Appended to the title as a percentage. ``None`` omits it.
    pole_high : str or None
        Meaning of the positive end of the axis (the highest class).
    pole_low : str or None
        Meaning of the negative end of the axis (the lowest class).
    note : str or None
        Methodology note, rendered small at the foot of the legend.
    pole_fontsize : int or None
        Font size of the pole texts. Defaults to the item label size.
    note_fontsize : int or None
        Font size of the note. Defaults to the subtitle size.
    pole_max_chars : int
        Characters per line before a pole text wraps.
    note_max_chars : int
        Characters per line before the note wraps.
    variance_label : str
        Wording of the variance line, with the placeholder ``{pct}``
        (default ``"{pct}% of total variance"``; for French,
        ``"{pct} % de la variance totale"``).
    """

    variance: float | None = None
    pole_high: str | None = None
    pole_low: str | None = None
    note: str | None = None
    pole_fontsize: int | None = None
    note_fontsize: int | None = None
    value_fontsize: int | None = None
    pole_max_chars: int = D.FACTOR_POLE_MAX_CHARS
    note_max_chars: int = D.FACTOR_NOTE_MAX_CHARS
    variance_label: str = "{pct}% of total variance"

    def variance_text(self) -> str:
        """Return the variance line (``variance`` must be set)."""
        pct = _fmt_value((self.variance or 0.0) * 100, 1, self.thousands_sep,
                         self.decimal_sep)
        return self.variance_label.format(pct=pct)

    def resolve_defaults(self, style, font_scale: float = 1.0) -> None:
        super().resolve_defaults(style, font_scale)
        self.pole_fontsize = round(
            (self.pole_fontsize or style["legend_fontsize"]) * font_scale)
        self.note_fontsize = round(
            (self.note_fontsize or D.LEGEND_SUBTITLE_FONT_SIZE) * font_scale)
        # Break values and the no-data label are smaller than the pole texts.
        self.value_fontsize = round(
            (self.value_fontsize or D.FACTOR_VALUE_FONT_SIZE) * font_scale)

    def title_with_variance(self) -> str | None:
        """Return the title with the variance share appended, if any."""
        if self.variance is None:
            return self.title
        suffix = self.variance_text()
        return f"{self.title} ({suffix})" if self.title else f"({suffix})"


def _fmt_value(v, decimals: int, thousands_sep: str = " ", decimal_sep: str = ".") -> str:
    """Format a single numeric value respecting decimals (0 to integer, no trailing .0)."""
    if decimals <= 0:
        s = f"{int(round(v)):,}"
    else:
        s = f"{v:,.{decimals}f}"
    return s.replace(",", "\x00").replace(".", decimal_sep).replace("\x00", thousands_sep)


def _format_range_label(low, high, decimals: int,
                        thousands_sep: str = " ", decimal_sep: str = ".",
                        template: str = "from {low} to {high}") -> str:
    """Format a range label like ``from 123 to 456``."""
    return template.format(
        low=_fmt_value(low, decimals, thousands_sep, decimal_sep),
        high=_fmt_value(high, decimals, thousands_sep, decimal_sep))


def _draw_legend_histogram(
    legend_g,
    x: float,
    y: float,
    values: np.ndarray,
    bins: np.ndarray,
    colors: list[str],
    config: ChoroplethLegendConfig,
) -> tuple[float, float, float, float] | None:
    """Draw a per-class-coloured distribution histogram to the right of the legend.

    Parameters
    ----------
    legend_g : xml.etree.ElementTree.Element
        Parent SVG group element.
    x, y : float
        Top-left corner of the histogram area (SVG px).
    values : np.ndarray
        Raw data values (pre-dissolve, pre-NaN-drop).
    bins : np.ndarray
        Class boundaries including true minimum: [min, b1, b2, ..., bk].
    colors : list of str
        Class colors (len == number of classes).
    config : ChoroplethLegendConfig
        Legend configuration.

    Returns
    -------
    tuple (x0, y0, x1, y1) or None
        Histogram bounding box, or None when skipped (degenerate distribution).
    """
    import xml.etree.ElementTree as ET

    hist_min = float(values.min())
    hist_max = float(values.max())
    if len(values) < 2 or hist_min == hist_max:
        warnings.warn(
            "Histogram skipped: column has no spread.",
            UserWarning,
            stacklevel=6,
        )
        return None

    n_bars = config.histogram_bins
    w = config.histogram_width
    h = config.histogram_height
    bar_w = w / n_bars

    counts, edges = np.histogram(values, bins=n_bars, range=(hist_min, hist_max))
    max_count = int(counts.max())
    if max_count == 0:
        return None

    # bins[1:] are the upper class boundaries (== scheme.bins).
    # np.searchsorted with side='left' matches mapclassify's own assignment.
    upper_bounds = np.asarray(bins[1:], dtype=float)

    for i, count in enumerate(counts):
        if count == 0:
            continue
        center = float((edges[i] + edges[i + 1]) / 2)
        class_idx = int(np.clip(
            np.searchsorted(upper_bounds, center, side="left"),
            0, len(colors) - 1,
        ))
        bar_h = h * count / max_count
        bar_x = x + i * bar_w
        bar_y = y + h - bar_h

        rect = ET.SubElement(
            legend_g, "rect",
            x=f"{bar_x:.2f}", y=f"{bar_y:.2f}",
            width=f"{bar_w:.2f}", height=f"{bar_h:.2f}",
            fill=colors[class_idx],
        )
        rect.set("class", "choropleth-legend-hist-bar")
        rect.set("stroke", "#ffffff")
        rect.set("stroke-width", str(D.CHOROPLETH_HIST_BAR_STROKE_WIDTH))
        rect.set("data-count", str(count))

    # Baseline
    baseline = ET.SubElement(
        legend_g, "line",
        x1=f"{x:.2f}", y1=f"{y + h:.2f}",
        x2=f"{x + w:.2f}", y2=f"{y + h:.2f}",
        stroke=D.CHOROPLETH_HIST_BASELINE_COLOR,
    )
    baseline.set("stroke-width", "0.5")

    return (x, y, x + w, y + h)


def _draw_legend(
    svg_doc,
    colors: list[str],
    bins: np.ndarray,
    config: ChoroplethLegendConfig,
    has_nodata: bool,
    main_viewport: SvgViewport,
    map_obj=None,
    values: np.ndarray | None = None,
) -> tuple[float, float, float, float] | None:
    """Draw a choropleth legend below the main map.

    Supports horizontal (classic boundary labels) and vertical
    (swatch + range text) orientations. Returns the legend bounding box.
    """
    if config.labels is not None and len(config.labels) != len(colors):
        raise ValueError(
            f"The legend has {len(config.labels)} custom label(s) "
            f"({list(config.labels)!r}) but the layer has {len(colors)} "
            f"class(es). Give exactly one label per class."
        )
    if config.orientation == "vertical":
        bbox = _draw_legend_vertical(svg_doc, colors, bins, config, has_nodata, main_viewport, values=values)
    else:
        bbox = _draw_legend_horizontal(svg_doc, colors, bins, config, has_nodata, main_viewport, values=values)
    if map_obj is not None and bbox is not None:
        map_obj.overflow.register(*bbox)
    return bbox


def _fmt_bin(config: ChoroplethLegendConfig, value) -> str:
    """Format a class boundary with the legend's decimals and separators."""
    return _fmt_value(value, config.decimals, config.thousands_sep,
                      config.decimal_sep)


def _class_label(config: ChoroplethLegendConfig, bins: np.ndarray, i: int) -> str:
    """Label of class *i* in "center" mode: custom text, range, or lower bound."""
    if config.labels is not None and i < len(config.labels):
        return str(config.labels[i])
    if config.label_format == "range":
        return _format_range_label(
            bins[i], bins[i + 1], config.decimals,
            config.thousands_sep, config.decimal_sep, config.range_format)
    return _fmt_bin(config, bins[i])


def _draw_nodata_entry(
    legend_g, svg_doc, config: ChoroplethLegendConfig, pattern_id: str,
    x: float, y: float, sw_w: float, sw_h: float, font_size: float,
    ff: str, fc: str,
) -> float:
    """Draw the no-data swatch at (x, y) and its label to the right of it.

    Returns the estimated width of the label.
    """
    suffix = legend_id_suffix(legend_g, "choropleth-legend")
    fill, hc = ensure_nodata_hatch(svg_doc, config, pattern_id + suffix)
    add_legend_swatch(
        legend_g, x, y, sw_w, sw_h, config, fill=fill, stroke=hc,
        id=f"choropleth-legend{suffix}-nodata",
        css_class="choropleth-legend choropleth-nodata",
    )
    nd_label = config.nodata_label or D.LEGEND_NODATA_LABEL
    add_legend_text(
        legend_g, x + sw_w + config.nodata_label_gap,
        y + sw_h / 2 + font_size * 0.35, nd_label, font_size, ff, fc,
    )
    return estimate_text_width(nd_label, font_size)


def _draw_class_swatch(legend_g, config, x, y, sw_w, sw_h, color, i, fc):
    """Draw the swatch of class *i*."""
    suffix = legend_id_suffix(legend_g, "choropleth-legend")
    add_legend_swatch(
        legend_g, x, y, sw_w, sw_h, config, fill=color, stroke=fc,
        id=f"choropleth-legend{suffix}-swatch-{i}",
        css_class=f"choropleth-legend choropleth-{i}",
    )


def _draw_legend_horizontal(
    svg_doc,
    colors: list[str],
    bins: np.ndarray,
    config: ChoroplethLegendConfig,
    has_nodata: bool,
    main_viewport: SvgViewport,
    values: np.ndarray | None = None,
):
    """Draw a horizontal choropleth legend (classic boundary labels). Returns (x0,y0,x1,y1)."""
    num = len(colors)

    sw_w = config.swatch_width
    sw_h = (config.swatch_height if config.swatch_height is not None
            else round(sw_w / D.PHI, 1))
    sw_gap = config.swatch_spacing
    font_size, fc, ff = legend_fonts(config)
    label_rot = config.label_rotation

    # Total width of swatches + gaps
    total_w = num * sw_w + (num - 1) * sw_gap

    legend_g, legend_x, legend_y, y_cursor = begin_legend(
        svg_doc, "choropleth-legend", config, main_viewport.viewbox)

    # ---- Color swatches ----
    for i, color in enumerate(colors):
        _draw_class_swatch(legend_g, config, legend_x + i * (sw_w + sw_gap),
                           y_cursor, sw_w, sw_h, color, i, fc)

    # ---- Bin labels ----
    label_y = y_cursor + sw_h + config.label_margin + font_size
    # When middle anchor + rotation: the right half of the text rises toward the swatches.
    # Add extra vertical margin = (sw_w/2) * sin(|angle|) to prevent overlap.
    if label_rot and config.label_anchor == "middle":
        label_y += (sw_w / 2) * math.sin(math.radians(abs(label_rot)))

    def rotation(lx):
        return {"transform": f"rotate({label_rot}, {lx:.2f}, {label_y:.2f})"}

    label_texts: list[str] = []
    last_lx = legend_x
    if config.label_position == "center" or config.labels is not None:
        # n labels, one per swatch, centered inside each swatch. Custom
        # labels name the classes, so they are always centred.
        for i in range(num):
            lx = last_lx = legend_x + i * (sw_w + sw_gap) + sw_w / 2
            label_texts.append(_class_label(config, bins, i))
            add_legend_text(
                legend_g, lx, label_y, label_texts[-1],
                font_size, ff, fc,
                anchor=config.label_anchor if label_rot else "middle",
                **(rotation(lx) if label_rot else {}),
            )
    else:
        # Default "border" mode: n+1 labels.
        # Labels at i=0 (far left) and i=n (far right) sit at the outer edges of
        # the first/last swatch. Interior labels (i=1..n-1) are centered in the
        # gap between swatch[i-1] and swatch[i].
        n_bins = len(bins)
        for i, value in enumerate(bins):
            if i == 0:
                lx = legend_x
            elif i == n_bins - 1:
                lx = legend_x + (i - 1) * (sw_w + sw_gap) + sw_w
            else:
                # Center of the gap between swatch[i-1] and swatch[i]
                lx = legend_x + (i - 1) * (sw_w + sw_gap) + sw_w + sw_gap / 2
            last_lx = lx
            label_texts.append(_fmt_bin(config, value))

            if label_rot:
                add_legend_text(
                    legend_g, lx, label_y, _fmt_bin(config, value),
                    font_size, ff, fc, anchor=None,
                    **rotation(lx), **{"text-anchor": config.label_anchor},
                )
            else:
                anchor = ("start" if i == 0
                          else "end" if i == n_bins - 1 else "middle")
                add_legend_text(legend_g, lx, label_y, _fmt_bin(config, value),
                                font_size, ff, fc, anchor=anchor)

    # ---- No-data indicator, swatch à droite, label à droite du swatch ----
    x1 = legend_x + total_w
    if has_nodata:
        nd_label_w = _draw_nodata_entry(
            legend_g, svg_doc, config, "hatch-legend-choropleth-horiz",
            legend_x + total_w + config.nodata_gap, y_cursor,
            sw_w, sw_h, font_size, ff, fc)
        x1 = (legend_x + total_w + config.nodata_gap + sw_w
              + config.nodata_label_gap + nd_label_w)

    # Rotated labels reach below their baseline and past the last swatch:
    # count their full length, whichever way they turn.
    y1 = label_y + font_size
    max_label_w = max(
        (estimate_text_width(t, font_size) for t in label_texts), default=0.0)
    if label_rot:
        theta = math.radians(abs(label_rot))
        y1 = label_y + max_label_w * math.sin(theta) + font_size * 0.3
        x1 = max(x1, last_lx + max_label_w * abs(math.cos(theta)))
    elif label_texts and (config.label_position == "center"
                          or config.labels is not None):
        # Centred labels may be wider than their swatch.
        x1 = max(x1, last_lx + estimate_text_width(label_texts[-1],
                                                   font_size) / 2)

    # ---- Frame (encloses the no-data entry and the labels) ----
    draw_config_frame(
        legend_g, svg_doc, config,
        legend_x, legend_y - font_size, x1 - legend_x,
        y1 - (legend_y - font_size),
    )

    if config.histogram and values is not None:
        hist_bbox = _draw_legend_histogram(
            legend_g, x1 + config.histogram_gap, legend_y,
            values, bins, colors, config,
        )
        if hist_bbox is not None:
            x1 = hist_bbox[2]
            y1 = max(y1, hist_bbox[3])

    return (legend_x, legend_y, x1, y1)


def _draw_legend_vertical(
    svg_doc,
    colors: list[str],
    bins: np.ndarray,
    config: ChoroplethLegendConfig,
    has_nodata: bool,
    main_viewport: SvgViewport,
    values: np.ndarray | None = None,
):
    """Draw a vertical choropleth legend. Returns (x0,y0,x1,y1).

    Label modes (controlled by ``config.label_position`` and ``config.label_format``):

    * ``"border"`` (default), n+1 bin values at class junctions, like the
      horizontal legend: true min at top, true max at bottom.
    * ``"center"`` + ``"range"``, one ``from xx to xx`` label per swatch,
      centered vertically on the swatch.
    * ``"center"`` + ``"value"``, lower-bound value per swatch, centered.
    * ``config.labels`` supplied, custom text per class (implies center).
    """
    num = len(colors)

    sw_w = config.vertical_swatch_width
    sw_h = (config.vertical_swatch_height if config.vertical_swatch_height is not None
            else round(sw_w / D.PHI, 1))
    sw_gap = config.swatch_spacing
    label_gap = config.vertical_label_gap
    font_size, fc, ff = legend_fonts(config)

    legend_g, legend_x, legend_y, y_cursor = begin_legend(
        svg_doc, "choropleth-legend", config, main_viewport.viewbox)

    # Determine effective mode
    use_border = (config.label_position == "border") and (config.labels is None)

    # ---- Color swatches (always the same) ----
    for i, color in enumerate(colors):
        _draw_class_swatch(legend_g, config, legend_x,
                           y_cursor + i * (sw_h + sw_gap),
                           sw_w, sw_h, color, i, fc)

    label_x = legend_x + sw_w + label_gap
    max_label_w = 0.0

    # ---- Labels: (baseline y, text) pairs ----
    if use_border:
        # n+1 bin values with uniform spacing.
        # Treat min and max as if they sit in a virtual gap above/below the block:
        #   edge_y[i] = y_cursor - sw_gap/2 + i * (sw_h + sw_gap)
        # to spacing between every consecutive pair = sw_h + sw_gap (constant).
        rows = [
            (y_cursor - sw_gap / 2 + i * (sw_h + sw_gap) + font_size * 0.35,
             _fmt_bin(config, value))
            for i, value in enumerate(bins)
        ]
    else:
        # center mode: one label per swatch
        if config.labels is not None:
            center_labels = list(config.labels)
        else:
            center_labels = [_class_label(config, bins, i) for i in range(num)]
        rows = [
            (y_cursor + i * (sw_h + sw_gap) + sw_h / 2 + font_size * 0.35, text)
            for i, text in enumerate(center_labels)
        ]
    for label_y, label_text in rows:
        add_legend_text(legend_g, label_x, label_y, label_text,
                        font_size, ff, fc)
        max_label_w = max(max_label_w, estimate_text_width(label_text, font_size))

    # ---- Compute precise bounding box ----
    # Bottom of content depends on label mode:
    # - border: last label baseline = y_cursor - sw_gap/2 + num*(sw_h+sw_gap), add font_size margin
    # - center/custom: bottom of last swatch
    if use_border:
        y_content_bottom = y_cursor - sw_gap / 2 + num * (sw_h + sw_gap) + font_size
    else:
        y_content_bottom = y_cursor + (num - 1) * (sw_h + sw_gap) + sw_h

    # ---- No-data entry: own column to the right, or under the classes ----
    nd_col_w = 0.0
    if has_nodata and config.nodata_position == "below":
        nd_y = y_content_bottom + config.nodata_gap
        nd_label_w = _draw_nodata_entry(
            legend_g, svg_doc, config, "hatch-legend-choropleth",
            legend_x, nd_y, sw_w, sw_h, font_size, ff, fc)
        max_label_w = max(max_label_w,
                          config.nodata_label_gap - label_gap + nd_label_w)
        y_content_bottom = nd_y + sw_h
    elif has_nodata:
        nd_col_x = legend_x + sw_w + label_gap + max_label_w + config.nodata_gap
        nd_label_w = _draw_nodata_entry(
            legend_g, svg_doc, config, "hatch-legend-choropleth",
            nd_col_x, y_cursor, sw_w, sw_h, font_size, ff, fc)
        nd_col_w = config.nodata_gap + sw_w + config.nodata_label_gap + nd_label_w

    content_w = sw_w + label_gap + max_label_w + nd_col_w
    title_size = config.title_fontsize or D.LEGEND_TITLE_FONT_SIZE
    frame_top = legend_y - title_size * 0.3   # small margin above title text

    draw_config_frame(
        legend_g, svg_doc, config,
        legend_x, frame_top, content_w, y_content_bottom - frame_top,
    )

    x1 = legend_x + content_w
    y1 = y_content_bottom

    if config.histogram and values is not None:
        hist_bbox = _draw_legend_histogram(
            legend_g, x1 + config.histogram_gap, y_cursor,
            values, bins, colors, config,
        )
        if hist_bbox is not None:
            x1 = hist_bbox[2]
            y1 = max(y1, hist_bbox[3])

    return (legend_x, legend_y, x1, y1)


def _draw_wrapped_text(parent, x, y, text, max_chars, font_size, ff, fc,
                       weight=None, anchor="start"):
    """Draw wrapped text from baseline y. Return (y_below, max_line_width)."""
    lines = textwrap.wrap(text, max_chars) if len(text) > max_chars else [text]
    line_h = font_size * D.FACTOR_LINE_HEIGHT
    max_w = 0.0
    for i, line in enumerate(lines):
        extra = {"font-weight": weight} if weight else {}
        add_legend_text(parent, x, y + font_size + i * line_h, line,
                        font_size, ff, fc, anchor=anchor, **extra)
        max_w = max(max_w, estimate_text_width(line, font_size))
    return y + font_size + (len(lines) - 1) * line_h, max_w


def _arrow_v(parent, x, tail_y, tip_y, color):
    """Vertical single arrow from tail_y to tip_y, head at the tip."""
    h = D.FACTOR_ARROW_HEAD
    ln = ET.SubElement(parent, "line", x1=f"{x:.2f}", y1=f"{tail_y:.2f}",
                       x2=f"{x:.2f}", y2=f"{tip_y:.2f}", stroke=color)
    ln.set("stroke-width", str(D.FACTOR_ARROW_WIDTH))
    d = h if tip_y > tail_y else -h  # head points toward the tip
    ET.SubElement(parent, "polygon", fill=color, points=(
        f"{x:.2f},{tip_y:.2f} {x - h / 2:.2f},{tip_y - d:.2f} "
        f"{x + h / 2:.2f},{tip_y - d:.2f}"))


def _arrow_h(parent, y, tail_x, tip_x, color):
    """Horizontal single arrow from tail_x to tip_x, head at the tip."""
    h = D.FACTOR_ARROW_HEAD
    ln = ET.SubElement(parent, "line", x1=f"{tail_x:.2f}", y1=f"{y:.2f}",
                       x2=f"{tip_x:.2f}", y2=f"{y:.2f}", stroke=color)
    ln.set("stroke-width", str(D.FACTOR_ARROW_WIDTH))
    d = h if tip_x > tail_x else -h
    ET.SubElement(parent, "polygon", fill=color, points=(
        f"{tip_x:.2f},{y:.2f} {tip_x - d:.2f},{y - h / 2:.2f} "
        f"{tip_x - d:.2f},{y + h / 2:.2f}"))


def _draw_factor_legend(svg_doc, colors, bins, config, has_nodata,
                        main_viewport, map_obj=None):
    """Draw a factor (PCA) legend: title, poles, class block, note.

    Returns the legend bounding box ``(x0, y0, x1, y1)``.

    Vertical: poles sit above and below the stacked swatches. Horizontal:
    poles sit at the two ends above the swatch row. Breaks and colours come
    from the choropleth layer unchanged.
    """
    vb = main_viewport.viewbox
    num = len(colors)
    fs, fc, ff = legend_fonts(config)
    pfs = config.pole_fontsize or fs
    nfs = config.note_fontsize or D.LEGEND_SUBTITLE_FONT_SIZE
    vertical = config.orientation == "vertical"

    # By default the legend sits outside the map, below the content. The
    # overflow registry then expands the canvas downward to show it. A manual
    # position keeps the old behaviour.
    if config.position is None:
        legend_x = vb.content_x
        legend_y = vb.content_y + vb.content_height + D.FACTOR_BELOW_GAP
    else:
        legend_x, legend_y = compute_legend_position(config, vb)
    legend_g = begin_legend_group(svg_doc, "factor-legend")
    sfx = legend_id_suffix(legend_g, "factor-legend")
    hatch_id = f"hatch-legend-factor{sfx}"

    y = draw_legend_title(legend_g, legend_x, legend_y, config, align="left")
    x1 = legend_x
    vfs = config.value_fontsize or D.FACTOR_VALUE_FONT_SIZE

    # Variance share, smaller, on its own line below the title.
    if config.variance is not None:
        y, w = _draw_wrapped_text(legend_g, legend_x, y,
                                  config.variance_text(),
                                  config.note_max_chars, nfs, ff, fc)
        x1 = max(x1, legend_x + w)
        y += D.FACTOR_POLE_GAP

    if vertical:
        sw_w = config.vertical_swatch_width
        sw_h = (config.vertical_swatch_height
                if config.vertical_swatch_height is not None
                else round(sw_w / D.PHI, 1))
        sw_gap = config.swatch_spacing
        label_gap = config.vertical_label_gap
        arrow_x = legend_x + D.FACTOR_ARROW_GAP / 2
        swatch_x = legend_x + D.FACTOR_ARROW_GAP

        # Positive pole on top; its baseline ends just above the up arrow tip.
        if config.pole_high:
            y, w = _draw_wrapped_text(legend_g, legend_x, y, config.pole_high,
                                      config.pole_max_chars, pfs, ff, fc)
            x1 = max(x1, legend_x + w)
        up_tip = y + D.FACTOR_POLE_GAP
        block_top = up_tip + D.FACTOR_ARROW_LEN + vfs

        # Factor axis reads high to low, top to bottom.
        vcolors = list(reversed(colors))
        vbins = list(reversed(bins))
        for i, color in enumerate(vcolors):
            row_y = block_top + i * (sw_h + sw_gap)
            add_legend_swatch(
                legend_g, swatch_x, row_y, sw_w, sw_h, config, fill=color,
                stroke=fc, id=f"factor-legend{sfx}-swatch-{i}",
                css_class=f"factor-legend factor-{i}")
        label_x = swatch_x + sw_w + label_gap
        max_lw = 0.0
        for i, value in enumerate(vbins):
            edge_y = block_top - sw_gap / 2 + i * (sw_h + sw_gap)
            txt = _fmt_bin(config, value)
            add_legend_text(legend_g, label_x, edge_y + vfs * 0.35, txt,
                            vfs, ff, fc)
            max_lw = max(max_lw, estimate_text_width(txt, vfs))
        block_bottom = block_top - sw_gap / 2 + num * (sw_h + sw_gap)
        x1 = max(x1, label_x + max_lw)

        # Two separate arrows: one up to the positive pole, one down to the
        # negative pole, each ending at its pole text.
        _arrow_v(legend_g, arrow_x, block_top, up_tip, fc)
        down_tip = block_bottom + D.FACTOR_ARROW_LEN
        _arrow_v(legend_g, arrow_x, block_bottom, down_tip, fc)
        y = down_tip + vfs

        # Negative pole below, starting at the down arrow tip.
        if config.pole_low:
            y, w = _draw_wrapped_text(legend_g, legend_x, y, config.pole_low,
                                      config.pole_max_chars, pfs, ff, fc)
            x1 = max(x1, legend_x + w)

        # No-data row, set further down for separation.
        if has_nodata:
            y += D.FACTOR_NODATA_GAP
            fill, hc = ensure_nodata_hatch(svg_doc, config, hatch_id)
            add_legend_swatch(
                legend_g, swatch_x, y, sw_w, sw_h, config, fill=fill,
                stroke=hc, id=f"factor-legend{sfx}-nodata")
            nd = config.nodata_label or D.LEGEND_NODATA_LABEL
            add_legend_text(legend_g, label_x, y + sw_h / 2 + vfs * 0.35, nd,
                            vfs, ff, fc)
            x1 = max(x1, label_x + estimate_text_width(nd, vfs))
            y += sw_h
    else:
        sw_w = config.swatch_width
        sw_h = (config.swatch_height if config.swatch_height is not None
                else round(sw_w / D.PHI, 1))
        sw_gap = config.swatch_spacing
        bar_w = num * sw_w + (num - 1) * sw_gap

        def _est_width(text):
            lines = (textwrap.wrap(text, config.pole_max_chars)
                     if len(text) > config.pole_max_chars else [text])
            return max(len(ln) for ln in lines) * pfs * 0.55

        # Poles centred over each half of the bar, symmetric about the bar
        # centre. Each text gets a half at least as wide as itself, so the bar
        # is centred in a wider row and the two texts mirror each other.
        low_text = ("- " + config.pole_low) if config.pole_low else None
        high_text = (config.pole_high + " +") if config.pole_high else None
        content_w = bar_w
        bar_x = legend_x
        if low_text or high_text:
            wl = _est_width(low_text) if low_text else 0.0
            wh = _est_width(high_text) if high_text else 0.0
            content_w = max(bar_w, 2 * max(wl, wh))
            bar_x = legend_x + (content_w - bar_w) / 2
            mid = legend_x + content_w / 2
            yl = yr = y
            if low_text:
                yl, _ = _draw_wrapped_text(
                    legend_g, legend_x + content_w / 4, y, low_text,
                    config.pole_max_chars, pfs, ff, fc, anchor="middle")
            if high_text:
                yr, _ = _draw_wrapped_text(
                    legend_g, legend_x + 3 * content_w / 4, y, high_text,
                    config.pole_max_chars, pfs, ff, fc, anchor="middle")
            y = max(yl, yr) + D.FACTOR_POLE_GAP
            # Two separate arrows, symmetric about the centre, pointing to the
            # bar ends.
            _arrow_h(legend_g, y, mid - D.FACTOR_ARROW_HEAD, bar_x, fc)
            _arrow_h(legend_g, y, mid + D.FACTOR_ARROW_HEAD, bar_x + bar_w, fc)
            y += D.FACTOR_POLE_GAP

        bar_top = y
        for i, color in enumerate(colors):
            cx = bar_x + i * (sw_w + sw_gap)
            add_legend_swatch(
                legend_g, cx, bar_top, sw_w, sw_h, config, fill=color,
                stroke=fc, id=f"factor-legend{sfx}-swatch-{i}",
                css_class=f"factor-legend factor-{i}")

        # Break values at the class boundaries, rotated like the choropleth.
        label_rot = config.label_rotation
        lbl_y = bar_top + sw_h + config.label_margin + vfs
        if label_rot and config.label_anchor == "middle":
            lbl_y += (sw_w / 2) * math.sin(math.radians(abs(label_rot)))
        last = len(bins) - 1
        for i, value in enumerate(bins):
            if i == 0:
                ex = bar_x
            elif i == last:
                ex = bar_x + bar_w
            else:
                ex = bar_x + i * (sw_w + sw_gap) - sw_gap / 2
            extra = ({"transform": f"rotate({label_rot}, {ex:.2f}, {lbl_y:.2f})"}
                     if label_rot else {})
            add_legend_text(legend_g, ex, lbl_y, _fmt_bin(config, value),
                            vfs, ff, fc,
                            anchor=config.label_anchor if label_rot else "middle",
                            **extra)
        x1 = max(x1, legend_x + content_w)
        y = lbl_y + vfs

        if has_nodata:
            fill, hc = ensure_nodata_hatch(svg_doc, config, hatch_id)
            nd_x = bar_x + bar_w + config.nodata_gap
            add_legend_swatch(
                legend_g, nd_x, bar_top, sw_w, sw_h, config, fill=fill,
                stroke=hc, id=f"factor-legend{sfx}-nodata")
            nd = config.nodata_label or D.LEGEND_NODATA_LABEL
            nd_label_x = nd_x + sw_w + config.nodata_label_gap
            add_legend_text(legend_g, nd_label_x,
                            bar_top + sw_h / 2 + vfs * 0.35, nd, vfs, ff, fc)
            x1 = max(x1, nd_label_x + estimate_text_width(nd, vfs))

    # Methodology note at the foot.
    if config.note:
        y += D.FACTOR_NOTE_GAP
        y, w = _draw_wrapped_text(legend_g, legend_x, y, config.note,
                                  config.note_max_chars, nfs, ff, fc)
        x1 = max(x1, legend_x + w)

    y1 = y
    title_size = config.title_fontsize or D.LEGEND_TITLE_FONT_SIZE
    frame_top = legend_y - title_size * 0.3
    draw_config_frame(legend_g, svg_doc, config, legend_x, frame_top,
                      x1 - legend_x, y1 - frame_top)

    if map_obj is not None:
        map_obj.overflow.register(legend_x, legend_y, x1, y1)
    return (legend_x, legend_y, x1, y1)
