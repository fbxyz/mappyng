"""Chrome elements of a Map: title, scale bar, north arrow, source text.

Mixin for :class:`mappyng.map.Map`; methods rely on Map attributes."""

from __future__ import annotations

import math
import textwrap
import xml.etree.ElementTree as ET
from typing import Any

from . import defaults as D
from ._map_base import MapBase
from .position import resolve_position


class ChromeMixin(MapBase):
    """Chrome elements of a Map: title, scale bar, north arrow, source text."""

    # ------------------------------------------------------------------
    # Title
    # ------------------------------------------------------------------

    def _render_title(self, params: dict[str, Any]) -> None:
        """Add a title (and optional subtitle) above the map.

        Parameters (dict keys)
        ----------------------
        text : str
            Title text (required).
        subtitle : str, optional
            Subtitle rendered below the title in a lighter style.
        max_chars : int
            Max characters per line before wrapping.
        font_size, fill, font_weight, font_family
            Title font properties (defaults from style).
        subtitle_font_size, subtitle_color, subtitle_font_weight
            Subtitle font properties.
        top_gap : float
            Vertical gap in pixels between the title baseline and the top edge
            of the map content area.  Positive values move the title up (away
            from the map); negative values move it down (toward or into the map).
            Default: ``TITLE_TOP_GAP`` (8 px).
        offset_x : float
            Additional horizontal shift in pixels (positive = right). Default 0.
        offset_y : float
            Additional vertical shift in pixels (positive = down). Default 0.

        Example::

            m.title(
                "Population par département",
                subtitle="Données fictives, 2024",
                font_size=14,
            )
        """
        cfg = dict(params)
        text = cfg.pop("text", "")
        if not text:
            return

        subtitle = cfg.pop("subtitle", None)
        max_chars = cfg.pop("max_chars", D.TITLE_MAX_CHARS)
        font_size = cfg.pop("font_size", self.style["title_size"]) * self.font_scale
        fill = cfg.pop("fill", self.style["title_color"])
        font_weight = cfg.pop("font_weight", self.style["title_fontweight"])
        font_family = cfg.pop("font_family", self.style["title_font_family"])
        sub_font_size = cfg.pop("subtitle_font_size",
                                round(font_size * D.TITLE_SUBTITLE_SIZE_RATIO))
        sub_color = cfg.pop("subtitle_color", fill)
        sub_font_weight = cfg.pop("subtitle_font_weight",
                                  D.TITLE_SUBTITLE_WEIGHT)
        offset_x = cfg.pop("offset_x", 0.0)
        offset_y = cfg.pop("offset_y", 0.0)
        loc = cfg.pop("loc", "left")
        position = cfg.pop("position", None)

        lines = textwrap.wrap(text, max_chars) if len(text) > max_chars else [text]
        line_height = font_size * D.TITLE_LINE_HEIGHT_RATIO

        vb = self.main.viewbox
        top_gap = cfg.pop("top_gap", D.TITLE_TOP_GAP)
        manual = resolve_position(position, vb)

        x, text_anchor = self._title_alignment(vb, loc, manual, offset_x)

        # Pre-compute subtitle lines so we can anchor the whole block from the bottom.
        # The last text element's baseline is fixed at content_y - top_gap; lines above
        # grow upward, so multi-line titles never overflow into the map.
        sub_lh = sub_font_size * D.TITLE_LINE_HEIGHT_RATIO
        sub_lines = self._title_subtitle_lines(
            subtitle, cfg.pop("subtitle_max_chars", None), max_chars,
            font_size, sub_font_size)

        # Bottom-anchor: last baseline sits at content_y - top_gap
        if manual is not None:
            y_bottom = manual[1] + offset_y
        else:
            y_bottom = vb.content_y - top_gap + offset_y
        if sub_lines:
            # subtitle block height above y_bottom
            sub_block = (len(sub_lines) - 1) * sub_lh
            sub_y = y_bottom - sub_block
            y_start = sub_y - D.TITLE_SUBTITLE_GAP - (len(lines) - 1) * line_height - line_height
        else:
            y_start = y_bottom - (len(lines) - 1) * line_height

        attrs = {
            "text_anchor": text_anchor,
            "font_size": font_size,
            "fill": fill,
            "font_weight": font_weight,
            "font_family": font_family,
        }
        attrs.update(cfg)

        for i, line in enumerate(lines):
            self.svg.add_overlay_text(
                "title", x, y_start + i * line_height, line,
                z_order=D.Z_TITLE, **attrs,
            )

        for j, sline in enumerate(sub_lines):
            self.svg.add_overlay_text(
                "title", x, sub_y + j * sub_lh, sline,
                z_order=D.Z_TITLE,
                text_anchor=text_anchor,
                font_size=sub_font_size,
                fill=sub_color,
                font_weight=sub_font_weight,
                font_family=font_family,
            )

        # Register chrome bbox for label avoidance
        cx0 = vb.content_x
        cx1 = vb.content_x + vb.content_width
        cy0 = y_start - font_size          # top of first line cap-height (approx)
        cy1 = y_bottom + sub_lh * 0.3     # bottom of last baseline + descenders
        self._register_chrome_bbox(cx0, cy0, cx1, cy1)

    @staticmethod
    def _title_alignment(vb: Any, loc: str, manual: tuple[float, float] | None,
                         offset_x: float) -> tuple[float, str]:
        """Return the title's ``(x, text_anchor)`` for the alignment *loc*.

        With a manual position the x of that position is used instead of the
        content-area edge or centre.
        """
        text_anchor = {"center": "middle", "right": "end"}.get(loc, "start")
        if manual is not None:
            return manual[0] + offset_x, text_anchor
        if loc == "center":
            return vb.content_x + vb.content_width / 2 + offset_x, text_anchor
        if loc == "right":
            return vb.content_x + vb.content_width + offset_x, text_anchor
        return vb.content_x + offset_x, text_anchor  # "left" (default)

    @staticmethod
    def _title_subtitle_lines(subtitle: str | None,
                              sub_max_chars: int | None, max_chars: int,
                              font_size: float, sub_font_size: float
                              ) -> list[str]:
        """Wrap the subtitle on its own character budget (``[]`` if none).

        Reusing the title's *max_chars* would break lines far too early
        because the subtitle is drawn in a smaller font, so by default the
        budget is scaled by the font-size ratio to keep the same *physical*
        width.
        """
        if not subtitle:
            return []
        if sub_max_chars is None:
            ratio = font_size / sub_font_size if sub_font_size else 1.0
            sub_max_chars = max(1, int(round(max_chars * ratio)))
        return (textwrap.wrap(subtitle, sub_max_chars)
                if len(subtitle) > sub_max_chars else [subtitle])

    # ------------------------------------------------------------------
    # Scale bar
    # ------------------------------------------------------------------

    @staticmethod
    def _nice_scale_length(max_geo_length: float) -> float:
        """Pick a round geographic length that fits comfortably on the map.

        Returns a "nice" value (1, 2, 5 × 10^n) that is <= *max_geo_length*.
        """
        import math
        if max_geo_length <= 0:
            return 1.0
        exp = math.floor(math.log10(max_geo_length))
        base = 10 ** exp
        for nice in (5, 2, 1):
            candidate = nice * base
            if candidate <= max_geo_length:
                return candidate
        return base

    def _render_scale_bar(self, params: dict[str, Any]) -> None:
        """Add a scale bar to the map.

        Parameters (dict keys)
        ----------------------
        length : float, optional
            Bar length in map CRS units (e.g. meters).  If omitted, a
            round value is chosen automatically (~20 % of map width).
        label : str, optional
            Text above the bar.  If omitted and *length* is set, an
            auto-label is generated using *unit* / *unit_factor*.
            Pass ``""`` to suppress the label entirely.
        unit : str
            Display unit appended to auto-labels (default ``"km"``).
        unit_factor : float
            Divisor for CRS to display conversion (default ``1000`` for
            metres to km).
        location : str
            Preset position: ``"lower right"``, ``"lower left"``,
            ``"upper right"``, ``"upper left"``.
        position : dict, optional
            Manual placement ``{"x": frac, "y": frac}`` relative to
            the content area (overrides *location*).
        color : str, optional
            Color for bar, ticks and label (default from style).
        bar_color : str, optional
            Bar line color (overrides *color*).
        tick_color : str, optional
            Tick line color (overrides *color*).
        label_color : str, optional
            Label text color (overrides *color*).
        font_size : int
            Label font size (default 8).
        font_weight : str
            Label font weight (default ``"normal"``).
        font_family : str
            Label font family (default sans-serif).
        bar_height : float
            Bar thickness in SVG px (default 3).
        tick_height : float
            Tick height in SVG px (default ``bar_height + 3``).
        tick_width : float
            Tick stroke width (default 1).
        margin : float
            Distance from content edge in px (default 15).

        Examples::

            m.scale_bar()                               # fully automatic
            m.scale_bar(length=200000, label="200 km")
            m.scale_bar(length=100000, color="red",
                        bar_height=4, font_size=10)
            m.scale_bar(position={"x": 0.05, "y": 0.95})
        """
        cfg = dict(params)
        vb = self.main.viewbox

        length, label = self._scale_bar_length_and_label(cfg, vb)
        if length <= 0:
            return

        # --- Styling ----------------------------------------------------------
        base_color = cfg.pop("color", None) or self.style.config.scale.color
        bar_color = cfg.pop("bar_color", None) or base_color
        tick_color = cfg.pop("tick_color", None) or base_color
        label_color = cfg.pop("label_color", None) or base_color
        font_size = cfg.pop("font_size", D.SCALE_BAR_FONT_SIZE) * self.font_scale
        font_weight = cfg.pop("font_weight", D.SCALE_BAR_FONT_WEIGHT)
        font_family = cfg.pop("font_family", D.FONT_FAMILY)
        bar_height = cfg.pop("bar_height", D.SCALE_BAR_HEIGHT)
        tick_height = cfg.pop("tick_height", None)
        if tick_height is None:
            tick_height = bar_height + D.SCALE_BAR_TICK_EXTRA
        tick_width = cfg.pop("tick_width", D.SCALE_BAR_TICK_WIDTH)
        margin = cfg.pop("margin", D.SCALE_BAR_MARGIN)
        opacity = float(cfg.pop("opacity", 1.0))

        x1, x2, y = self._scale_bar_anchor(
            cfg, vb, vb.geo_length_to_svg(length), font_size, margin)

        # --- Draw -------------------------------------------------------------
        opacity_kwarg = {"opacity": opacity} if opacity < 1.0 else {}

        # Bar line
        self.svg.add_overlay_line(
            "scale_bar", x1, y, x2, y, z_order=D.Z_SCALE_BAR,
            stroke=bar_color, stroke_width=bar_height, **opacity_kwarg,
        )
        # End ticks
        for tx in (x1, x2):
            self.svg.add_overlay_line(
                "scale_bar", tx, y - tick_height / 2, tx, y + tick_height / 2,
                z_order=D.Z_SCALE_BAR,
                stroke=tick_color, stroke_width=tick_width, **opacity_kwarg,
            )
        # Label
        if label:
            label_x = (x1 + x2) / 2
            label_y = y - bar_height - D.SCALE_BAR_LABEL_GAP
            self.svg.add_overlay_text(
                "scale_bar", label_x, label_y, label, z_order=D.Z_SCALE_BAR,
                text_anchor="middle", font_size=font_size, fill=label_color,
                font_family=font_family, font_weight=font_weight, **opacity_kwarg,
            )

        # Register chrome bbox for label avoidance
        pad = 4
        self._register_chrome_bbox(
            x1 - pad,
            y - bar_height - font_size - D.SCALE_BAR_LABEL_GAP - pad,
            x2 + pad,
            y + bar_height + pad,
        )

    def _scale_bar_length_and_label(self, cfg: dict[str, Any], vb: Any
                                    ) -> tuple[float, str]:
        """Pop the length, unit and label options; return ``(length, label)``.

        With no *length* a round value near 20 % of the map width is chosen;
        with no *label* one is generated from the length and unit.
        """
        unit = cfg.pop("unit", D.SCALE_BAR_UNIT)
        unit_factor = cfg.pop("unit_factor", D.SCALE_BAR_UNIT_FACTOR)

        length = cfg.pop("length", None)
        if length is None:
            # Auto: pick a nice round value ~ 20% of map geographic width
            geo_w = vb.content_width / vb.scale if vb.scale else 1
            length = self._nice_scale_length(geo_w * 0.20)

        label = cfg.pop("label", None)
        if label is None:
            display_val = length / unit_factor
            if display_val == int(display_val):
                label = f"{int(display_val)} {unit}"
            else:
                label = f"{display_val:.1f} {unit}"
        return length, label

    @staticmethod
    def _scale_bar_anchor(cfg: dict[str, Any], vb: Any, bar_px: float,
                          font_size: float, margin: float
                          ) -> tuple[float, float, float]:
        """Pop the placement options; return ``(x1, x2, y)`` in SVG pixels.

        A manual ``position`` anchors the left end of the bar; otherwise the
        bar sits in the corner given by ``location``.
        """
        position = cfg.pop("position", D.SCALE_BAR_POSITION)
        location = cfg.pop("location", D.SCALE_BAR_LOCATION)

        manual = resolve_position(position, vb)
        if manual is not None:
            x1, y = manual
            return x1, x1 + bar_px, y

        if "right" in location:
            x2 = vb.content_x + vb.content_width - margin
            x1 = x2 - bar_px
        else:
            x1 = vb.content_x + margin
            x2 = x1 + bar_px
        if "upper" in location:
            y = vb.content_y + margin + font_size + D.SCALE_BAR_UPPER_OFFSET
        else:
            y = vb.content_y + vb.content_height - margin
        return x1, x2, y

    # ------------------------------------------------------------------
    # North arrow
    # ------------------------------------------------------------------

    def _render_north_arrow(self, params: dict[str, Any] | None = None) -> None:
        """Add a discreet north arrow to the map.

        By convention the top of the map is north, so a north arrow is only
        needed to lift an ambiguity. It is therefore optional and drawn
        discreetly.  The arrow points up; pass ``rotation`` only if the map
        itself is rotated (mappyng does not rotate maps automatically).

        Parameters (dict keys)
        ----------------------
        location : str
            Preset corner: ``"upper right"`` (default), ``"upper left"``,
            ``"lower right"``, ``"lower left"``.
        position : dict, optional
            Manual placement ``{"x": frac, "y": frac}`` relative to the
            content area (overrides *location*).
        size : float
            Total arrow height in SVG px (default 24).
        color : str
            Color for shaft, arrowhead and label.
        margin : float
            Distance from content edge in px (default 15).
        label : str
            Text above the arrow (default ``"N"``; pass ``""`` to hide).
        font_size : int
            Label font size (default 9).
        stroke_width : float
            Shaft stroke width (default 1).
        rotation : float
            Manual rotation in degrees (default 0 = points up).

        Examples
        --------
        >>> m.north_arrow()                               # upper-right, default
        >>> m.north_arrow(location="lower left")
        >>> m.north_arrow(position={"x": 0.92, "y": 0.08})
        """
        cfg = dict(params or {})
        vb = self.main.viewbox

        # --- Parameters ---
        size         = cfg.pop("size",         D.NORTH_ARROW_SIZE)
        color        = cfg.pop("color",        D.NORTH_ARROW_COLOR)
        margin       = cfg.pop("margin",       D.NORTH_ARROW_MARGIN)
        label        = cfg.pop("label",        D.NORTH_ARROW_LABEL)
        font_size    = cfg.pop("font_size",    D.NORTH_ARROW_FONT_SIZE)
        stroke_width = cfg.pop("stroke_width", D.NORTH_ARROW_STROKE_WIDTH)
        rotation     = cfg.pop("rotation",     D.NORTH_ARROW_ROTATION)
        position     = cfg.pop("position",     D.NORTH_ARROW_POSITION)
        location     = cfg.pop("location",     D.NORTH_ARROW_LOCATION)

        # head = top quarter of size; shaft = remaining three quarters
        head_h = size * 0.35
        shaft_h = size - head_h
        head_w = size * 0.40

        tip_x, tip_y = self._north_arrow_tip(
            position, location, vb, margin, label, font_size, head_h, shaft_h)
        self._draw_north_arrow(
            tip_x, tip_y, size, head_h, head_w, shaft_h, color, stroke_width,
            rotation, label, font_size)

    @staticmethod
    def _north_arrow_tip(position: Any, location: str, vb: Any, margin: float,
                         label: str, font_size: float, head_h: float,
                         shaft_h: float) -> tuple[float, float]:
        """Anchor point (tip of the arrowhead) in SVG pixels.

        A manual *position* wins; otherwise the arrow sits in the corner given
        by *location*.
        """
        manual = resolve_position(position, vb)
        if manual is not None:
            return manual
        if "right" in location:
            tip_x = vb.content_x + vb.content_width - margin
        else:
            tip_x = vb.content_x + margin
        if "upper" in location:
            tip_y = vb.content_y + margin + (font_size + 2 if label else 0) + head_h
        else:
            tip_y = vb.content_y + vb.content_height - margin - shaft_h
        return tip_x, tip_y

    def _draw_north_arrow(self, cx: float, tip_y: float, size: float,
                          head_h: float, head_w: float, shaft_h: float,
                          color: str, stroke_width: float, rotation: float,
                          label: str, font_size: float) -> None:
        """Draw the arrow (head, shaft, optional label) centred on *cx*."""
        shaft_top_y = tip_y
        shaft_bot_y = tip_y + shaft_h

        # --- SVG group ---
        group = self.svg.add_overlay_group(
            "north_arrow", z_order=D.Z_NORTH_ARROW,
            id="north-arrow",
        )
        # Apply rotation around the centroid of the arrow
        if rotation:
            centre_y = tip_y + size / 2
            group.set("transform", f"rotate({rotation:.2f},{cx:.2f},{centre_y:.2f})")

        # Arrowhead, filled triangle (tip up)
        pts = (
            f"{cx:.2f},{shaft_top_y:.2f} "
            f"{cx - head_w / 2:.2f},{shaft_top_y + head_h:.2f} "
            f"{cx + head_w / 2:.2f},{shaft_top_y + head_h:.2f}"
        )
        tri = ET.SubElement(group, "polygon", points=pts)
        tri.set("fill", color)
        tri.set("stroke", color)
        tri.set("stroke-width", "0.5")
        tri.set("class", "north-arrow")

        # Shaft
        shaft = ET.SubElement(
            group, "line",
            x1=f"{cx:.2f}", y1=f"{shaft_top_y + head_h:.2f}",
            x2=f"{cx:.2f}", y2=f"{shaft_bot_y:.2f}",
        )
        shaft.set("stroke", color)
        shaft.set("stroke-width", str(stroke_width))
        shaft.set("class", "north-arrow")

        # Label
        if label:
            lbl_y = shaft_top_y - 2
            txt = ET.SubElement(
                group, "text",
                x=f"{cx:.2f}", y=f"{lbl_y:.2f}",
            )
            txt.text = label
            txt.set("font-size", str(font_size))
            txt.set("font-family", D.FONT_FAMILY)
            txt.set("fill", color)
            txt.set("text-anchor", "middle")
            txt.set("class", "north-arrow")

        # Chrome bbox for label avoidance
        label_top = (shaft_top_y - font_size - 2) if label else shaft_top_y
        self._register_chrome_bbox(
            cx - head_w / 2 - 2,
            label_top,
            cx + head_w / 2 + 2,
            shaft_bot_y + 2,
        )

    # ------------------------------------------------------------------
    # Source text
    # ------------------------------------------------------------------

    def _render_source(self, params: dict[str, Any]) -> None:
        """Add source attribution text.

        Parameters (dict keys)
        ----------------------
        text : str
            Source text (required).  Use ``"\\n"`` to split into multiple lines
            (useful in horizontal layout).
        layout : str, optional
            ``"vertical"`` (default), rotated 90° at the right edge of the
            basemap, reading bottom-to-top, aligned with the basemap bottom.
            ``"horizontal"``, normal horizontal text at the bottom-right of
            the basemap.
        position : dict, optional
            Manual placement as ``{"x": frac, "y": frac}`` relative to the
            basemap content area (0,0 = top-left, 1,1 = bottom-right).
            Overrides the automatic positioning of both layouts.
        rotation : float, optional
            Explicit rotation in degrees (default 90 for vertical, 0 for
            horizontal).  Only used if ``position`` is not set.
        font_size : int, optional
            Font size (default from style).
        color : str, optional
            Text color (default from style).
        opacity : float, optional
            Text opacity (default from style).
        font_style : str, optional
            CSS font-style (default ``"italic"``).
        font_weight : str, optional
            CSS font-weight (default ``"normal"``).
        font_family : str, optional
            Font family (default from style).
        text_anchor : str, optional
            SVG text-anchor: ``"start"``, ``"middle"``, or ``"end"``.
            Default depends on layout/position.

        Examples::

            m.source("Source : INSEE")
            m.source("Source : INSEE\\nTraitement : auteur",
                     layout="horizontal")
            m.source("Source : INSEE", position={"x": 0.5, "y": 1.05})
        """
        cfg = dict(params)
        text = cfg.pop("text", "")
        if not text:
            return

        layout = cfg.pop("layout", D.SOURCE_LAYOUT)
        position = cfg.pop("position", D.SOURCE_POSITION)
        fs = (cfg.pop("font_size", None)
              or self.style.config.source.font.size) * self.font_scale
        c = cfg.pop("color", None) or self.style.config.source.font.color
        a = cfg.pop("opacity", None) or self.style.config.source.font.opacity
        font_style = cfg.pop("font_style", D.SOURCE_FONT_STYLE)
        font_weight = cfg.pop("font_weight", D.SOURCE_FONT_WEIGHT)
        font_family = cfg.pop("font_family", None) or self.style.config.source.font.family
        text_anchor = cfg.pop("text_anchor", None)

        vb = self.main.viewbox
        lines = text.replace("\\n", "\n").split("\n")

        # --- Manual position -------------------------------------------------
        manual = resolve_position(position, vb)
        if manual is not None:
            x, y = manual
            rotation = cfg.pop("rotation", 0)
            anchor = text_anchor or "start"
            self._render_source_lines(
                lines, x, y, fs, c, a, font_style, font_weight,
                font_family, anchor, rotation,
            )
            return

        # --- Vertical (default), rotated 90° at right edge ------------------
        if layout == "vertical":
            rotation = cfg.pop("rotation", D.SOURCE_ROTATION)
            x = vb.svg_x + vb.svg_width + D.SOURCE_OFFSET_X
            # Align text start with basemap bottom
            y = vb.content_y + vb.content_height
            anchor = text_anchor or "start"
            self._render_source_lines(
                lines, x, y, fs, c, a, font_style, font_weight,
                font_family, anchor, rotation,
            )
            # Rotated 90°: lines stack to the right, text runs upward
            text_length = max(len(ln) for ln in lines) * fs * 0.6
            width = fs + (len(lines) - 1) * fs * D.SOURCE_HORIZONTAL_LINE_SPACING
            self.overflow.register(x, y - text_length, x + width, y)
            return

        # --- Horizontal, bottom-right of basemap ----------------------------
        rotation = cfg.pop("rotation", 0)
        margin = D.SOURCE_HORIZONTAL_MARGIN
        x = vb.content_x + vb.content_width - margin
        y = vb.content_y + vb.content_height - margin
        anchor = text_anchor or "end"
        self._render_source_lines(
            lines, x, y, fs, c, a, font_style, font_weight,
            font_family, anchor, rotation, bottom_up=True,
        )

    def _render_source_lines(
        self,
        lines: list,
        x: float, y: float,
        font_size: float, fill: str, opacity: float,
        font_style: str, font_weight: str, font_family: str,
        text_anchor: str, rotation: float,
        bottom_up: bool = False,
    ) -> None:
        """Render one or more source text lines as SVG ``<text>`` elements.

        Lines are stacked perpendicular to the text direction, so rotated
        text keeps its lines side by side. With ``bottom_up``, the last line
        sits on the anchor point.
        """
        line_h = font_size * D.SOURCE_HORIZONTAL_LINE_SPACING
        # Unit vector pointing to the next line once rotated by -rotation
        theta = math.radians(rotation)
        dx, dy = math.sin(theta), math.cos(theta)

        n = len(lines)
        for i, line_text in enumerate(lines):
            k = i - (n - 1) if bottom_up else i
            lx = x + k * line_h * dx
            ly = y + k * line_h * dy
            if not line_text.strip():
                continue
            attrs = {
                "font_size": font_size,
                "fill": fill,
                "opacity": opacity,
                "font_family": font_family,
                "font_style": font_style,
                "font_weight": font_weight,
                "text_anchor": text_anchor,
            }
            if rotation:
                attrs["transform"] = f"rotate(-{rotation}, {lx:.2f}, {ly:.2f})"
            self.svg.add_overlay_text(
                "source", lx, ly, line_text,
                z_order=D.Z_SOURCE, **attrs,
            )

    # ------------------------------------------------------------------
    # Chrome tracking
    # ------------------------------------------------------------------

    def _register_chrome_bbox(self, x0: float, y0: float,
                               x1: float, y1: float) -> None:
        """Store a chrome element bounding box (SVG px) for label avoidance."""
        self._state.chrome_bboxes.append((x0, y0, x1, y1))
