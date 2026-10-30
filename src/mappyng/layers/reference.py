"""Reference (non data-driven) layers.

Basemap, tiles, raster, graticule, drop shadow and ocean gradient. Each
delegates rendering to the matching drawing helper on
:class:`~mappyng.Map`.
"""

from __future__ import annotations

from typing import Any

from .base import _UNSET, Layer, RenderContext, collect_set, register_layer


@register_layer
class Basemap(Layer):
    """Plain background drawn from the map's main GeoDataFrame.

    Parameters
    ----------
    fill : str, optional
        Fill colour as ``#RRGGBB`` (default from style or the map's
        basemap colour override).
    stroke : str, optional
        Outline colour (default from style).
    stroke_width : float, optional
        Outline width (default from style).
    detail : GeoDataFrame or dict, optional
        Finer geometry drawn instead of the map's GeoDataFrame on the zoom
        window and the cartouches. A GeoDataFrame applies to the zoom and
        every cartouche; a dict maps ``"zoom"``, ``"cartouches"`` or a
        cartouche index to a GeoDataFrame. See :mod:`mappyng.detail`.
    z_index : int, optional
        Render order (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m.add(Basemap(fill="#f2efe9", stroke="#999999"))
    >>> m.add(Basemap(detail=gdf_fine))  # finer geometry in zoom and cartouches
    """

    kind = "basemap"
    requires_gdf = False

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        fill: Any = _UNSET,
        stroke: Any = _UNSET,
        stroke_width: Any = _UNSET,
        detail: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(fill=fill, stroke=stroke, stroke_width=stroke_width,
                          detail=detail),
        )

    def render(self, ctx: RenderContext) -> None:
        ctx.map._render_basemap(**dict(self.params))
        self._rendered = True


@register_layer
class Tile(Layer):
    """XYZ raster tile backdrop.

    Parameters
    ----------
    source : str, optional
        Provider alias (e.g. ``"cartodb_positron"``, ``"osm"``,
        ``"satellite"``) or a URL template with ``{x}``, ``{y}``, ``{z}``
        placeholders.
    zoom : int or str, optional
        Zoom level, or ``"auto"`` (default) to derive it from the bbox.
    zoom_offset : int, optional
        Added to the auto-calculated zoom (e.g. ``-1`` for lighter tiles).
    opacity : float, optional
        Tile opacity in ``[0, 1]`` (default 1).
    z_order : int, optional
        SVG stacking order (default below the basemap).
    timeout : float, optional
        HTTP request timeout in seconds (default 10).
    cache : bool, optional
        Cache tiles on disk (default True).
    cache_dir : str, optional
        Cache directory (default ``~/.cache/mappyng/tiles``).
    on_cartouches : bool, optional
        Draw on cartouche viewports (default True).
    on_zoom : bool, optional
        Draw on the zoom viewport (default True).
    max_tiles : int, optional
        Safety cap on tiles downloaded per viewport (default 64).
    warp_scale : float, optional
        Output resolution relative to the content area (default 1.5).
    extra_zoom_levels : int, optional
        Number of coarser zoom levels to also fetch and blend (default 0).
    z_index : int, optional
        Render order among layers (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m.add(Tile())
    >>> m.add(Tile(source="satellite", opacity=0.7))
    """

    kind = "tile"
    requires_gdf = False

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        source: Any = _UNSET,
        zoom: Any = _UNSET,
        zoom_offset: Any = _UNSET,
        opacity: Any = _UNSET,
        z_order: Any = _UNSET,
        timeout: Any = _UNSET,
        cache: Any = _UNSET,
        cache_dir: Any = _UNSET,
        on_cartouches: Any = _UNSET,
        on_zoom: Any = _UNSET,
        max_tiles: Any = _UNSET,
        warp_scale: Any = _UNSET,
        extra_zoom_levels: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(
                source=source, zoom=zoom, zoom_offset=zoom_offset,
                opacity=opacity, z_order=z_order, timeout=timeout,
                cache=cache, cache_dir=cache_dir, on_cartouches=on_cartouches,
                on_zoom=on_zoom, max_tiles=max_tiles, warp_scale=warp_scale,
                extra_zoom_levels=extra_zoom_levels,
            ),
        )

    def render(self, ctx: RenderContext) -> None:
        ctx.map._render_tile(dict(self.params))
        self._rendered = True


@register_layer
class Raster(Layer):
    """Raster image overlay.

    Parameters
    ----------
    paths : dict
        Mapping of region name to GeoTIFF path (required). Each viewport
        picks the raster whose footprint overlaps its bbox.
    opacity : float, optional
        Raster opacity in ``[0, 1]`` (default 1).
    on_zoom : bool, optional
        Draw on the zoom viewport (default True).
    on_cartouches : bool, optional
        Draw on cartouche viewports (default True).
    z_index : int, optional
        Render order among layers (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m.add(Raster(paths={"metropole": "data/dem.tif"}, opacity=0.8))
    """

    kind = "raster"
    requires_gdf = False

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        paths: Any = _UNSET,
        opacity: Any = _UNSET,
        on_zoom: Any = _UNSET,
        on_cartouches: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(
                paths=paths, opacity=opacity, on_zoom=on_zoom,
                on_cartouches=on_cartouches,
            ),
        )

    def validate(self) -> None:
        if not self.params:
            raise ValueError(
                "Raster needs parameters describing the raster to "
                "draw (e.g. a path or array); none were given, so there "
                "is nothing to overlay."
            )

    def render(self, ctx: RenderContext) -> None:
        ctx.map._render_raster(dict(self.params))
        self._rendered = True


@register_layer
class Graticule(Layer):
    """Latitude/longitude grid.

    Parameters
    ----------
    step : float, optional
        Spacing between lines in degrees (default 10).
    stroke : str, optional
        Line colour as ``#RRGGBB`` (default ``"#aaaaaa"``).
    opacity : float, optional
        Stroke opacity in ``[0, 1]`` (default 0.5).
    stroke_width : float, optional
        Line width (default 0.5).
    dash : str, optional
        SVG dash pattern (default ``"4 2"``).
    position : str, optional
        ``"background"`` (default) draws the grid above the ocean but
        below the data; ``"top"`` draws it over everything, which suits
        globe-style maps.
    z : int, optional
        Explicit stacking order, overriding ``position``.
    z_index : int, optional
        Render order among layers (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m.add(Graticule(step=5.0, stroke="#888888", opacity=0.4))
    """

    kind = "graticule"
    requires_gdf = False

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        step: Any = _UNSET,
        stroke: Any = _UNSET,
        opacity: Any = _UNSET,
        stroke_width: Any = _UNSET,
        dash: Any = _UNSET,
        position: Any = _UNSET,
        z: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(
                step=step, stroke=stroke, opacity=opacity,
                stroke_width=stroke_width, dash=dash, position=position, z=z,
            ),
        )

    def render(self, ctx: RenderContext) -> None:
        ctx.map._render_graticule(dict(self.params))
        self._rendered = True


@register_layer
class DropShadow(Layer):
    """Blurred shadow cast by a set of geometries.

    The geometries are dissolved into one outline, drawn below the data
    with a drop-shadow filter.

    Parameters
    ----------
    gdf : GeoDataFrame
        Geometries casting the shadow.
    query : str, optional
        pandas query selecting the rows to shadow, e.g.
        ``"code_pays_iso3 == 'FRA'"``.
    dx, dy : float, optional
        Shadow offset in pixels.
    blur : float, optional
        Blur radius (SVG ``stdDeviation``).
    color : str, optional
        Shadow colour.
    opacity : float, optional
        Shadow opacity in ``[0, 1]``.
    fill : str, optional
        Fill of the shadow shape.
    on_cartouches : bool, optional
        Draw on cartouche viewports (default True).
    on_zoom : bool, optional
        Draw on the zoom viewport (default False).
    z_index : int, optional
        Render order among layers (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m.add(DropShadow(europe, query="code_pays_iso3 == 'FRA'"))
    """

    kind = "shadow"
    requires_gdf = True

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        query: Any = _UNSET,
        dx: Any = _UNSET,
        dy: Any = _UNSET,
        blur: Any = _UNSET,
        color: Any = _UNSET,
        opacity: Any = _UNSET,
        fill: Any = _UNSET,
        on_cartouches: Any = _UNSET,
        on_zoom: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(
                query=query, dx=dx, dy=dy, blur=blur, color=color,
                opacity=opacity, fill=fill, on_cartouches=on_cartouches,
                on_zoom=on_zoom,
            ),
        )

    def render(self, ctx: RenderContext) -> None:
        ctx.map._render_shadow(self.gdf, dict(self.params))
        self._rendered = True


@register_layer
class OceanGradient(Layer):
    """Gradient on the ocean, fading out from the coastline of a layer.

    Drawn above the ocean colour (``facecolor``) and below everything
    else. It is built from nested buffers rather than an SVG filter, so
    PNG and PDF exports match the SVG.

    Parameters
    ----------
    gdf : GeoDataFrame
        Land geometries the gradient starts from, e.g. European countries.
    query : str, optional
        pandas query selecting the rows to use.
    width : float, optional
        Distance in pixels over which the gradient fades out
        (default 24).
    color : str, optional
        Gradient colour along the coast (default ``"#ffffff"``, which
        lightens the ocean near the land).
    opacity : float, optional
        Opacity of the gradient along the coast, in ``[0, 1]``
        (default 0.45).
    steps : int, optional
        Number of bands drawn (default 8). More bands give a smoother
        gradient and a larger file.
    on_cartouches : bool, optional
        Draw on cartouche viewports (default True).
    on_zoom : bool, optional
        Draw on the zoom viewport (default True).
    z_index : int, optional
        Render order among layers (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m = m + OceanGradient(europe)
    >>> m = m + OceanGradient(europe, color="#0b3a57", opacity=0.3)
    """

    kind = "ocean_gradient"
    requires_gdf = True

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        query: Any = _UNSET,
        width: Any = _UNSET,
        color: Any = _UNSET,
        opacity: Any = _UNSET,
        steps: Any = _UNSET,
        on_cartouches: Any = _UNSET,
        on_zoom: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(
                query=query, width=width, color=color, opacity=opacity,
                steps=steps, on_cartouches=on_cartouches, on_zoom=on_zoom,
            ),
        )

    def validate(self) -> None:
        steps = self.params.get("steps")
        if steps is not None and (not isinstance(steps, int) or steps < 1):
            raise ValueError(
                f"OceanGradient: steps must be a positive integer, got "
                f"{steps!r}."
            )
        width = self.params.get("width")
        if width is not None and width <= 0:
            raise ValueError(
                f"OceanGradient: width must be a positive number of "
                f"pixels, got {width!r}."
            )

    def render(self, ctx: RenderContext) -> None:
        ctx.map._render_ocean_gradient(self.gdf, dict(self.params))
        self._rendered = True
