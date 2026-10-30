"""Map elements other than layers.

Title, source, scale bar, north arrow, cartouches, zoom window,
tooltips and gradients. Each is added to a map like a layer::

    m = Map(gdf) + Basemap() + Title("Population") + ScaleBar()

The chrome elements (title, source, scale bar, north arrow) are drawn
when the map is built. Adding the same kind of element twice keeps the
last one.
"""

from __future__ import annotations

import copy
import hashlib
from collections.abc import Sequence
from typing import Any

from .layers.base import _UNSET, collect_set


def _as_position(value: Any) -> Any:
    """Convert an ``(x, y)`` pair to the ``{"x": x, "y": y}`` form."""
    if isinstance(value, (tuple, list)) and len(value) == 2:
        return {"x": value[0], "y": value[1]}
    return value


class Element:
    """Base class of the non-layer map elements."""

    params: dict[str, Any]

    def _apply(self, m: Any) -> None:
        """Register the element on map *m*."""
        raise NotImplementedError

    def copy(self) -> Element:
        """Return a shallow copy of the element."""
        new = copy.copy(self)
        if hasattr(self, "params"):
            new.params = dict(self.params)
        return new

    def __repr__(self) -> str:
        return f"{type(self).__name__}({getattr(self, 'params', {})!r})"


class _Chrome(Element):
    """Chrome element stored under a fixed name on the map."""

    name = ""

    def __init__(self, **params: Any) -> None:
        self.params: dict[str, Any] = collect_set(**params)
        if "position" in self.params:
            self.params["position"] = _as_position(self.params["position"])

    def _apply(self, m: Any) -> None:
        m._state.chrome[self.name] = dict(self.params)


class Title(_Chrome):
    """Map title, drawn above the map content.

    Parameters
    ----------
    text : str
        Title text. Wrapped onto several lines past ``max_chars``.
    subtitle : str, optional
        Subtitle drawn below the title in a lighter style.
    loc : str, optional
        Horizontal alignment: ``"left"`` (default), ``"center"`` or
        ``"right"``.
    max_chars : int, optional
        Maximum characters per line of the title before wrapping.
    subtitle_max_chars : int, optional
        Maximum characters per line of the subtitle. If omitted, derived
        from ``max_chars`` scaled by the title/subtitle font-size ratio.
    font_size : float, optional
        Title font size in points (default from style).
    fill : str, optional
        Title color as ``#RRGGBB`` (default from style).
    font_weight : str, optional
        Title font weight, e.g. ``"bold"`` (default from style).
    font_family : str, optional
        Title font family (default from style).
    subtitle_font_size : float, optional
        Subtitle font size (default derived from ``font_size``).
    subtitle_color : str, optional
        Subtitle color as ``#RRGGBB`` (default: same as ``fill``).
    subtitle_font_weight : str, optional
        Subtitle font weight (default ``"normal"``).
    top_gap : float, optional
        Vertical gap in pixels between the title baseline and the top of
        the map content. Default 8.
    position : tuple or dict, optional
        Place the title anywhere instead of above the map. The point is the
        baseline of the last line, aligned according to ``loc``. Same forms
        as the scale bar ``position`` (fractions, percentages, pixels,
        geographic coordinates).
    offset_x : float, optional
        Extra horizontal shift in pixels (positive = right). Default 0.
    offset_y : float, optional
        Extra vertical shift in pixels (positive = down). Default 0.

    Examples
    --------
    >>> m = m + Title("Population", subtitle="2024", loc="center")
    """

    name = "title"

    def __init__(
        self,
        text: str,
        *,
        subtitle: Any = _UNSET,
        loc: Any = _UNSET,
        max_chars: Any = _UNSET,
        subtitle_max_chars: Any = _UNSET,
        font_size: Any = _UNSET,
        fill: Any = _UNSET,
        font_weight: Any = _UNSET,
        font_family: Any = _UNSET,
        subtitle_font_size: Any = _UNSET,
        subtitle_color: Any = _UNSET,
        subtitle_font_weight: Any = _UNSET,
        top_gap: Any = _UNSET,
        position: Any = _UNSET,
        offset_x: Any = _UNSET,
        offset_y: Any = _UNSET,
    ) -> None:
        super().__init__(
            text=text, subtitle=subtitle, loc=loc, max_chars=max_chars,
            subtitle_max_chars=subtitle_max_chars, font_size=font_size,
            fill=fill, font_weight=font_weight, font_family=font_family,
            subtitle_font_size=subtitle_font_size,
            subtitle_color=subtitle_color,
            subtitle_font_weight=subtitle_font_weight, top_gap=top_gap,
            position=position, offset_x=offset_x, offset_y=offset_y,
        )


class Source(_Chrome):
    """Source or credit line.

    Parameters
    ----------
    text : str
        Source text, rendered in italic by default. Use ``"\\n"`` to split
        it into several lines.
    layout : str, optional
        ``"vertical"`` (default), rotated 90 degrees at the right edge, or
        ``"horizontal"`` at the bottom-right of the map.
    position : tuple or dict, optional
        Manual placement of the start of the text, overriding ``layout``. Fractions
        ``(x, y)`` / ``{"x": 0.5, "y": 0.9}`` or percentages
        (``{"x": "50%", "y": "90%"}``) of the map content area, pixels
        (``{"px": 120, "py": 80}``), or geographic coordinates
        (``{"geo": (x, y)}`` in the map CRS, ``{"lon": 4.2, "lat": 42.6}``
        in WGS 84). See :mod:`mappyng.position`.
    rotation : float, optional
        Explicit rotation in degrees. Used only when ``position`` is unset.
    font_size : float, optional
        Font size in points (default from style).
    color : str, optional
        Text color as ``#RRGGBB`` (default from style).
    opacity : float, optional
        Text opacity in ``[0, 1]`` (default from style).
    font_style : str, optional
        CSS font style (default ``"italic"``).
    font_weight : str, optional
        CSS font weight (default ``"normal"``).
    font_family : str, optional
        Font family (default from style).
    text_anchor : str, optional
        SVG text anchor: ``"start"``, ``"middle"`` or ``"end"``.

    Examples
    --------
    >>> m = m + Source("Source : INSEE", layout="horizontal")
    """

    name = "source"

    def __init__(
        self,
        text: str,
        *,
        layout: Any = _UNSET,
        position: Any = _UNSET,
        rotation: Any = _UNSET,
        font_size: Any = _UNSET,
        color: Any = _UNSET,
        opacity: Any = _UNSET,
        font_style: Any = _UNSET,
        font_weight: Any = _UNSET,
        font_family: Any = _UNSET,
        text_anchor: Any = _UNSET,
    ) -> None:
        super().__init__(
            text=text, layout=layout, position=position, rotation=rotation,
            font_size=font_size, color=color, opacity=opacity,
            font_style=font_style, font_weight=font_weight,
            font_family=font_family, text_anchor=text_anchor,
        )


class ScaleBar(_Chrome):
    """Scale bar.

    Parameters
    ----------
    length : float, optional
        Bar length in map CRS units, e.g. metres. If omitted, a round
        value near 20 percent of the map width is chosen.
    label : str, optional
        Text above the bar. Generated from ``length`` if omitted. Pass
        ``""`` to hide it.
    unit : str, optional
        Display unit for generated labels (default ``"km"``).
    unit_factor : float, optional
        Divisor from CRS units to display units (default 1000).
    location : str, optional
        Preset corner: ``"lower right"``, ``"lower left"``,
        ``"upper right"`` or ``"upper left"``.
    position : tuple or dict, optional
        Manual placement of the left end of the bar, overriding ``location``. Fractions
        ``(x, y)`` / ``{"x": 0.5, "y": 0.9}`` or percentages
        (``{"x": "50%", "y": "90%"}``) of the map content area, pixels
        (``{"px": 120, "py": 80}``), or geographic coordinates
        (``{"geo": (x, y)}`` in the map CRS, ``{"lon": 4.2, "lat": 42.6}``
        in WGS 84). See :mod:`mappyng.position`.
    color : str, optional
        Color of bar, ticks and label (default from style).
    bar_color, tick_color, label_color : str, optional
        Per-part colors (override ``color``).
    font_size : float, optional
        Label font size (default 8).
    font_weight : str, optional
        Label font weight (default ``"normal"``).
    font_family : str, optional
        Label font family (default sans-serif).
    bar_height : float, optional
        Bar thickness in pixels (default 3).
    tick_height : float, optional
        Tick height in pixels (default ``bar_height + 3``).
    tick_width : float, optional
        Tick stroke width (default 1).
    margin : float, optional
        Distance from the content edge in pixels (default 15).
    opacity : float, optional
        Opacity in ``[0, 1]`` (default 1).

    Examples
    --------
    >>> m = m + ScaleBar(length=100_000, position=(0.46, 0.9))
    """

    name = "scale_bar"

    def __init__(
        self,
        *,
        length: Any = _UNSET,
        label: Any = _UNSET,
        unit: Any = _UNSET,
        unit_factor: Any = _UNSET,
        location: Any = _UNSET,
        position: Any = _UNSET,
        color: Any = _UNSET,
        bar_color: Any = _UNSET,
        tick_color: Any = _UNSET,
        label_color: Any = _UNSET,
        font_size: Any = _UNSET,
        font_weight: Any = _UNSET,
        font_family: Any = _UNSET,
        bar_height: Any = _UNSET,
        tick_height: Any = _UNSET,
        tick_width: Any = _UNSET,
        margin: Any = _UNSET,
        opacity: Any = _UNSET,
    ) -> None:
        super().__init__(
            length=length, label=label, unit=unit, unit_factor=unit_factor,
            location=location, position=position, color=color,
            bar_color=bar_color, tick_color=tick_color,
            label_color=label_color, font_size=font_size,
            font_weight=font_weight, font_family=font_family,
            bar_height=bar_height, tick_height=tick_height,
            tick_width=tick_width, margin=margin, opacity=opacity,
        )


class NorthArrow(_Chrome):
    """North arrow.

    By convention the top of the map is north, so a north arrow is only
    needed to lift an ambiguity.

    Parameters
    ----------
    location : str, optional
        Preset corner: ``"upper right"`` (default), ``"upper left"``,
        ``"lower right"`` or ``"lower left"``.
    position : tuple or dict, optional
        Manual placement of the left end of the bar, overriding ``location``. Fractions
        ``(x, y)`` / ``{"x": 0.5, "y": 0.9}`` or percentages
        (``{"x": "50%", "y": "90%"}``) of the map content area, pixels
        (``{"px": 120, "py": 80}``), or geographic coordinates
        (``{"geo": (x, y)}`` in the map CRS, ``{"lon": 4.2, "lat": 42.6}``
        in WGS 84). See :mod:`mappyng.position`.
    size : float, optional
        Arrow height in pixels (default 24).
    color : str, optional
        Color of shaft, arrowhead and label.
    margin : float, optional
        Distance from the content edge in pixels (default 15).
    label : str, optional
        Text above the arrow (default ``"N"``; ``""`` hides it).
    font_size : float, optional
        Label font size (default 9).
    stroke_width : float, optional
        Shaft stroke width (default 1).
    rotation : float, optional
        Rotation in degrees (default 0, points up).

    Examples
    --------
    >>> m = m + NorthArrow(location="lower left")
    """

    name = "north_arrow"

    def __init__(
        self,
        *,
        location: Any = _UNSET,
        position: Any = _UNSET,
        size: Any = _UNSET,
        color: Any = _UNSET,
        margin: Any = _UNSET,
        label: Any = _UNSET,
        font_size: Any = _UNSET,
        stroke_width: Any = _UNSET,
        rotation: Any = _UNSET,
    ) -> None:
        super().__init__(
            location=location, position=position, size=size, color=color,
            margin=margin, label=label, font_size=font_size,
            stroke_width=stroke_width, rotation=rotation,
        )


class Legend:
    """Legend settings of a thematic layer.

    Passed as the ``legend`` parameter of a layer. The accepted options
    depend on the layer type (see :class:`ChoroplethLegendConfig`,
    :class:`ProportionalLegendConfig` and :class:`SituationLegendConfig`).

    Parameters
    ----------
    title : str, optional
        Legend title.
    **options
        Other legend options, e.g. ``orientation``, ``decimals``,
        ``nodata_label``, ``position``.

    Examples
    --------
    >>> Choropleth(gdf, column="rate",
    ...            legend=Legend("Rate", orientation="horizontal"))
    """

    def __init__(self, title: str | None = None, **options: Any) -> None:
        self.options: dict[str, Any] = dict(options)
        if title is not None:
            self.options["title"] = title

    def to_dict(self) -> dict[str, Any]:
        """Return the options as a plain dict."""
        return dict(self.options)

    def __repr__(self) -> str:
        return f"Legend({self.options!r})"


# Inset option name -> cartouche parameter key.
_INSET_KEYS = {
    "title": "cartouche_title",
    "title_size": "cartouche_title_size",
    "size": "size",
    "spacing": "spacing",
    "border_color": "border_color",
    "border_width": "border_width",
    "border_radius": "border_radius",
    "box_shadow": "box_shadow",
    "glow": "glow",
}


class Inset:
    """One cartouche: a small map of a separate area.

    Parameters
    ----------
    title : str, optional
        Title drawn above the cartouche.
    bbox : list of float
        Area shown, ``[minx, miny, maxx, maxy]`` in ``crs``.
    crs : int or str
        CRS of ``bbox``; the cartouche is drawn in this CRS.
    title_size : float, optional
        Title font size.
    size : float, optional
        Scale factor of the cartouche (default 1).
    spacing : float, optional
        Space above this cartouche in pixels.
    border_color : str, optional
        Border color.
    border_width : float, optional
        Border width.
    border_radius : float, optional
        Corner radius in pixels.
    box_shadow : bool or dict, optional
        Drop shadow behind the cartouche.
    glow : bool or dict, optional
        Outer glow.
    """

    def __init__(
        self,
        title: Any = _UNSET,
        *,
        bbox: Sequence[float],
        crs: Any,
        title_size: Any = _UNSET,
        size: Any = _UNSET,
        spacing: Any = _UNSET,
        border_color: Any = _UNSET,
        border_width: Any = _UNSET,
        border_radius: Any = _UNSET,
        box_shadow: Any = _UNSET,
        glow: Any = _UNSET,
    ) -> None:
        self.bbox = list(bbox)
        self.crs = crs
        self.options: dict[str, Any] = collect_set(
            title=title, title_size=title_size, size=size, spacing=spacing,
            border_color=border_color, border_width=border_width,
            border_radius=border_radius, box_shadow=box_shadow, glow=glow,
        )

    def to_params(self, defaults: dict[str, Any] | None = None
                  ) -> dict[str, Any]:
        """Return the cartouche parameters, *defaults* filling the gaps."""
        options = {**(defaults or {}), **self.options}
        params: dict[str, Any] = {"bbox": list(self.bbox), "crs": self.crs}
        for key, value in options.items():
            params[_INSET_KEYS[key]] = value
        return params

    def __repr__(self) -> str:
        return f"Inset(bbox={self.bbox!r}, crs={self.crs!r}, {self.options!r})"


class Insets(Element):
    """Group of cartouches, stacked on the left of the main map.

    Data layers are drawn in the cartouches by default; pass
    ``on_cartouches=False`` to a layer to keep it off them.

    Parameters
    ----------
    insets : list of Inset
        The cartouches, top to bottom.
    spacing : float, optional
        Vertical spacing between cartouches in pixels.
    **defaults
        Options applied to every inset that does not set them:
        ``title_size``, ``size``, ``border_color``, ``border_width``,
        ``border_radius``, ``box_shadow``, ``glow``.

    Examples
    --------
    >>> insets = Insets([
    ...     Inset("Guadeloupe", bbox=[-6890454, 1780151, -6799589, 1874186],
    ...           crs=3857),
    ...     Inset("Martinique", bbox=[-6826862, 1609607, -6759494, 1685367],
    ...           crs=3857),
    ... ], spacing=15, border_radius=6, box_shadow=True)
    """

    def __init__(self, insets: Sequence[Inset], *,
                 spacing: float | None = None, **defaults: Any) -> None:
        unknown = set(defaults) - (set(_INSET_KEYS) - {"title", "spacing"})
        if unknown:
            raise TypeError(
                f"Insets got unexpected options {sorted(unknown)}. Shared "
                f"options are: title_size, size, border_color, border_width, "
                f"border_radius, box_shadow, glow."
            )
        self.insets: list[Inset] = list(insets)
        self.spacing = spacing
        self.defaults = dict(defaults)

    def to_params(self) -> dict[int, dict[str, Any]]:
        """Return the cartouches as the ``cartouche_params`` mapping."""
        return {i: inset.to_params(self.defaults)
                for i, inset in enumerate(self.insets)}

    def _apply(self, m: Any) -> None:
        m._set_cartouches(self.to_params(), self.spacing)

    def __repr__(self) -> str:
        return f"Insets({self.insets!r}, spacing={self.spacing!r})"


class Zoom(Element):
    """Zoom window showing a magnified area inside the main map.

    Layers with ``on_zoom=True`` (the default for thematic layers) are
    redrawn in the window.

    Parameters
    ----------
    bbox : list of float
        Area shown, ``[minx, miny, maxx, maxy]`` in the map CRS.
    x, y : float, optional
        Top-left corner of the window in pixels.
    width, height : float, optional
        Window size in pixels.
    border_color : str, optional
        Border color.
    border_width : float, optional
        Border width.
    border_radius : float, optional
        Corner radius in pixels.
    box_shadow : bool or dict, optional
        Drop shadow behind the window.
    glow : bool or dict, optional
        Outer glow.

    Examples
    --------
    >>> m = m + Zoom([634000, 6841000, 674000, 6882000],
    ...              x=705, y=160, width=128, height=140)
    """

    def __init__(
        self,
        bbox: Sequence[float],
        *,
        x: Any = _UNSET,
        y: Any = _UNSET,
        width: Any = _UNSET,
        height: Any = _UNSET,
        border_color: Any = _UNSET,
        border_width: Any = _UNSET,
        border_radius: Any = _UNSET,
        box_shadow: Any = _UNSET,
        glow: Any = _UNSET,
    ) -> None:
        self.params: dict[str, Any] = {
            "bbox": list(bbox),
            **collect_set(
                x=x, y=y, width=width, height=height,
                border_color=border_color, border_width=border_width,
                border_radius=border_radius, box_shadow=box_shadow, glow=glow,
            ),
        }

    def _apply(self, m: Any) -> None:
        m._add_zoom_viewport(dict(self.params))


class Tooltip(Element):
    """Hover tooltips of the interactive export.

    Used by :meth:`Map.to_interactive` and by :meth:`Map.render` with a
    ``.html`` path.

    Parameters
    ----------
    columns : list of str, optional
        Columns shown in the tooltip. Detected automatically if omitted.
    aliases : dict, optional
        Display names of the columns.
    style : dict or TooltipStyle, optional
        Tooltip appearance (see :class:`TooltipStyle`).
    hover_opacity : float, optional
        Opacity of the hovered feature.

    Examples
    --------
    >>> m = m + Tooltip(["LIB_GEO", "rate"], aliases={"LIB_GEO": "Name"})
    """

    def __init__(self, columns: list[str] | None = None, *,
                 aliases: dict[str, str] | None = None,
                 style: Any = None,
                 hover_opacity: float | None = None) -> None:
        self.columns = list(columns) if columns is not None else None
        self.aliases = dict(aliases) if aliases else None
        self.style = style
        self.hover_opacity = hover_opacity

    def to_kwargs(self) -> dict[str, Any]:
        """Return the matching :meth:`Map.to_interactive` arguments."""
        style = self.style
        if isinstance(style, dict):
            style = dict(style)
        return {"columns": self.columns, "aliases": self.aliases,
                "tooltip": style, "hover_opacity": self.hover_opacity}

    def _apply(self, m: Any) -> None:
        m._tooltip = self

    def __repr__(self) -> str:
        return f"Tooltip(columns={self.columns!r}, aliases={self.aliases!r})"


class RadialGradient(Element):
    """Radial gradient usable as a fill.

    The gradient must be added to the map; layers reference it through
    :attr:`url`. Offsetting the focal point (``fx``, ``fy``) from the
    centre fakes a highlight, turning a flat disc into a lit sphere.

    Parameters
    ----------
    stops : list of tuple
        Colour stops from centre to edge: ``(offset, color)`` or
        ``(offset, color, opacity)``, ``offset`` in ``[0, 1]``.
    gradient_id : str, optional
        Element id. Derived from the parameters if omitted.
    cx, cy : float, default 0.5
        Centre of the gradient.
    r : float, default 0.5
        Radius of the gradient.
    fx, fy : float, optional
        Focal point. Defaults to ``(cx, cy)``.
    units : str, default ``"objectBoundingBox"``
        ``"objectBoundingBox"`` or ``"userSpaceOnUse"``.
    spread : str, default ``"pad"``
        ``"pad"``, ``"reflect"`` or ``"repeat"``.

    Examples
    --------
    >>> ocean = RadialGradient([(0.0, "#bfe6ff"), (1.0, "#0b3a57")],
    ...                        fx=0.35, fy=0.35)
    >>> m = m + ocean + Vector(disc, fill=ocean.url)
    """

    def __init__(
        self,
        stops: Sequence[tuple[Any, ...]],
        *,
        gradient_id: str | None = None,
        cx: float = 0.5,
        cy: float = 0.5,
        r: float = 0.5,
        fx: float | None = None,
        fy: float | None = None,
        units: str = "objectBoundingBox",
        spread: str = "pad",
    ) -> None:
        self.stops = [tuple(s) for s in stops]
        self.params: dict[str, Any] = dict(
            cx=cx, cy=cy, r=r, fx=fx, fy=fy, units=units, spread=spread)
        if gradient_id is None:
            digest = hashlib.sha1(
                repr((self.stops, sorted(self.params.items()))).encode()
            ).hexdigest()[:8]
            gradient_id = f"radial-{digest}"
        self.gradient_id = gradient_id

    @property
    def url(self) -> str:
        """Fill reference, ``"url(#<id>)"``."""
        return f"url(#{self.gradient_id})"

    def _apply(self, m: Any) -> None:
        m.svg.add_radial_gradient(self.stops, gradient_id=self.gradient_id,
                                  **self.params)
