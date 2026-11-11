"""
Main Map class for mappyng.

Orchestrates SVG rendering of geographic data with support for:
- Main map with configurable bounding box
- Cartouches (inset maps) with independent CRS and bbox
- Zoom windows
- Title, scale bar, source text
- Layer system per viewport (basemap, choropleth, etc.)

Layout matches mappyng's positioning conventions:
- Cartouches stacked vertically on the left, top-aligned with main map
- Main map fills the remaining space
- Zoom window positioned inside the main map area
- Facecolor renders as "ocean" background inside each viewport


Example
-------
>>> from mappyng import Map, Basemap, Title
>>> m = (
...     Map(gdf, bbox=[90000, 6040000, 1280000, 7150000],
...         width=800, height=900, facecolor="#B9D9EB")
...     + Basemap()
...     + Title("France métropolitaine")
... )
>>> m.render("map.svg")
"""

import math
import os
import warnings
import weakref
from typing import TYPE_CHECKING, Any, cast

import geopandas as gpd
from shapely.geometry import box

from . import defaults as D
from ._map_background import BackgroundMixin
from ._map_chrome import ChromeMixin
from ._state import MapState
from .config import ConfigManager
from .detail import ZOOM, detail_for, join_detail, normalize_detail
from .errors import GEO_ERRORS
from .overflow import OverflowRegistry
from .renderer import SvgDocument, SvgViewport, ViewBox, make_bbox_square

if TYPE_CHECKING:  # resolve forward-ref annotations for docs/type-checkers
    from .interactive import InteractiveMap
    from .layers import Layer


class Map(BackgroundMixin, ChromeMixin):
    """SVG map builder with viewport-based architecture.

    Each distinct area (main map, cartouche, zoom) gets its own
    SvgViewport with independent geographic bounds and clip region.

    Layers and elements (title, scale bar, cartouches...) are added with
    ``m + item``, which returns a new map, or ``m.add(item)``, which adds
    in place and returns ``m``. The map is drawn when it is rendered.

    Parameters
    ----------
    gdf : geopandas.GeoDataFrame
        Base GeoDataFrame defining the map extent and basemap geometry.
    bbox : list, optional
        Bounding box [minx, miny, maxx, maxy]. If None, computed from gdf.
    width : float or "auto"
        SVG document width in pixels. ``"auto"`` derives the width from the
        data aspect ratio (the height is then the fixed reference).
    height : float or "auto"
        SVG document height in pixels. ``"auto"`` derives the height from the
        data aspect ratio so the map is not letterboxed (width stays fixed).
        See also :meth:`autosize`.
    padding : float
        Document-level padding in pixels.
    style : str or dict
        Style name (``"classic"``, ``"modern"``) or a dict with
        ``"base"`` key selecting the starting preset and other keys
        overriding specific style values (e.g. ``"title_color"``).
    facecolor : str, optional
        Ocean/background color drawn inside each viewport.
    background : str, optional
        Document background color (default white).
    basemap_color : str, optional
        Override fill color for basemap polygons.
    border_radius : float
        Corner radius in pixels for the main map viewport (0 = sharp).
    box_shadow : bool or dict, optional
        Drop-shadow effect on the main map viewport.
        ``True`` for defaults, dict for custom (dx, dy, blur, color, opacity).
    glow : bool or dict, optional
        Outer glow effect on the main map viewport.
    cartouche_params : dict, optional
        Cartouche definitions. Keys are integer indices, values are dicts
        with required keys 'bbox' and 'crs', plus optional
        'cartouche_title', 'cartouche_title_size', 'size',
        'border_radius', 'box_shadow', 'glow'.
    cartouche_spacing : float, optional
        Vertical spacing between cartouches in pixels. If None, uses
        the default figure-fraction layout (mappyng convention).
    font_scale : float or ``"auto"``, default ``"auto"``
        Global font size multiplier applied to titles, scale bar, and
        legends.  ``"auto"`` computes the scale from the document area
        so that fonts look consistent across different map sizes.
    coordinate_precision : int, default 2
        Decimal places kept for geometry path coordinates in the SVG
        output. Lower values shrink the file and speed up parsing at the
        cost of sub-pixel accuracy. Points that round to the same position
        are merged, which also reduces dense geometries.
    seed : int or None, optional
        Random seed for reproducible stochastic components (currently
        automatic label placement). Defaults to 42, which keeps maps
        reproducible across runs. Pass ``None`` for non-deterministic
        behaviour. A ``seed=`` passed directly to ``Label`` takes
        precedence over this map-level seed.
    """

    def __init__(self, gdf: gpd.GeoDataFrame, bbox: list[float] | None = None,
                 width: float | str = D.DOCUMENT_WIDTH,
                 height: float | str = D.DOCUMENT_HEIGHT,
                 padding: float = D.DOCUMENT_PADDING,
                 style: str | dict[str, Any] = "classic",
                 facecolor: str | None = None,
                 background: str | None = None,
                 basemap_color: str | None = None,
                 border_radius: float = D.BORDER_RADIUS,
                 box_shadow=None,
                 glow=None,
                 cartouche_params: dict[int, Any] | None = None,
                 cartouche_spacing: float | None = None,
                 font_scale: float | str = "auto",
                 coordinate_precision: int = D.DEFAULT_COORDINATE_PRECISION,
                 seed: int | None = 42):
        self._init_kwargs: dict[str, Any] = dict(
            gdf=gdf, bbox=bbox, width=width, height=height, padding=padding,
            style=style, facecolor=facecolor, background=background,
            basemap_color=basemap_color, border_radius=border_radius,
            box_shadow=box_shadow, glow=glow,
            cartouche_params=cartouche_params,
            cartouche_spacing=cartouche_spacing, font_scale=font_scale,
            coordinate_precision=coordinate_precision, seed=seed,
        )
        self._require_data(gdf)

        self.gdf = gdf
        self._style_arg = style  # original style argument, for serialisation
        self.style = ConfigManager.get_style(style)

        self.padding = padding
        self.facecolor = facecolor
        self.basemap_color = basemap_color
        self.cartouche_params = cartouche_params or {}
        self._cartouche_spacing_override = cartouche_spacing
        self._coordinate_precision: int = coordinate_precision
        self._seed: int | None = seed

        # Main viewport effects
        self._main_border_radius = border_radius
        self._main_box_shadow = box_shadow
        self._main_glow = glow

        # Geographic bounds
        self._bbox_arg = list(bbox) if bbox is not None else None  # for serialisation
        if bbox is not None:
            self.bbox = list(bbox)
        else:
            self.bbox = list(gdf.total_bounds)

        # Document dimensions: "auto" derives the missing dimension from
        # the data aspect ratio so the content area is not letterboxed.
        # Resolution needs the bbox, hence it happens here.
        self._auto_width = (width == "auto")
        self._auto_height = (height == "auto")
        width, height = self._resolve_auto_dimensions(width, height)
        self.width = width
        self.height = height

        self.font_scale = self._resolve_font_scale(font_scale, width, height)
        self._font_scale_auto = (font_scale == "auto")

        self._init_build_state()

        # Create SVG document
        self.svg = SvgDocument(width=width, height=height)

        # Document background
        self._background = background or D.DOCUMENT_BACKGROUND
        bg = self._background
        self.svg.add_overlay_rect(
            "background", 0, 0, width, height,
            z_order=D.Z_BACKGROUND, fill=bg,
        )

        # Build main first (cartouches align to its content_y)
        self._build_main_viewport()
        if self.cartouche_params:
            self._build_cartouches()

    @staticmethod
    def _require_data(gdf: Any) -> None:
        """Raise a plain-language error when *gdf* is missing or empty."""
        if gdf is None or gdf.empty:
            raise ValueError(
                "Map requires a non-empty GeoDataFrame: the map bounds and "
                "geometries are derived from it. Received "
                f"{'None' if gdf is None else 'an empty GeoDataFrame'}. "
                "Load your data (e.g. geopandas.read_file(...)) before "
                "creating the Map."
            )

    @staticmethod
    def _resolve_font_scale(font_scale: float | str, width: float,
                            height: float) -> float:
        """Font scale factor: ``"auto"`` scales with the document area."""
        if font_scale == "auto":
            return D.FONT_SCALE_AUTO_COEFF * math.sqrt(
                (width * height) / (D.FONT_SCALE_REFERENCE_WIDTH * D.FONT_SCALE_REFERENCE_HEIGHT)
            )
        return float(font_scale)

    def _init_build_state(self) -> None:
        """Initialise the state accumulated by ``add`` and filled at build."""
        # Accumulated state (grouped, see _state.MapState)
        self._state = MapState()

        # Layers and elements in the order they were added, replayed by
        # copy() and the + operator.
        self._items: list[Any] = []
        self._tooltip = None

        # Build state
        self._built: bool = False

        # Structural state (initialised at construction, frozen after build)
        self._cartouche_viewports: dict[int, SvgViewport] = {}
        self._zoom_viewport: SvgViewport | None = None
        self._zoom_bbox: list[float] | None = None
        self._zoom_params: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    # ------------------------------------------------------------------
    # Internal: build viewports
    # ------------------------------------------------------------------

    def _add_ocean(self, viewport: SvgViewport) -> None:
        """Add an ocean/facecolor background rect inside a viewport.

        Uses the content area (after aspect-ratio fitting) so the ocean
        matches the geographic bbox exactly, without spilling into padding.
        """
        if not self.facecolor:
            return
        vb = viewport.viewbox
        viewport.add_rect("ocean", vb.content_x, vb.content_y,
                          vb.content_width, vb.content_height,
                          z_order=D.Z_OCEAN, fill=self.facecolor)

    # ------------------------------------------------------------------
    # Figure-fraction to SVG pixel helpers
    # ------------------------------------------------------------------

    def _fig_x(self, fx: float) -> float:
        """Convert figure-fraction x to SVG pixel x."""
        return fx * self.width

    def _fig_y(self, fy: float) -> float:
        """Convert figure-fraction y (bottom=0) to SVG pixel y (top=0)."""
        return (1 - fy) * self.height

    def _fig_w(self, fw: float) -> float:
        """Convert figure-fraction width to SVG pixel width."""
        return fw * self.width

    def _fig_h(self, fh: float) -> float:
        """Convert figure-fraction height to SVG pixel height."""
        return fh * self.height

    # ------------------------------------------------------------------
    # Dynamic canvas
    # ------------------------------------------------------------------

    def _resolve_auto_dimensions(self, width: float | str,
                                 height: float | str) -> tuple[float, float]:
        """Resolve ``"auto"`` document dimensions from the data aspect ratio.

        The missing dimension is computed so the main content area matches
        the geographic bounds exactly, leaving only the intentional layout
        margins (chrome) instead of aspect-ratio letterboxing.

        Strategy: width is the fixed reference; height follows the data.
        If only ``height="auto"`` the width is kept; if only ``width="auto"``
        the height is kept and the width is derived; if both are ``"auto"``
        the default document width is used as the fixed reference.
        """
        w_auto = (width == "auto")
        h_auto = (height == "auto")
        if not w_auto and not h_auto:
            # Numeric dimensions are passed through unchanged (preserving int
            # vs float) so explicitly-sized maps render byte-identically.
            return cast(float, width), cast(float, height)

        minx, miny, maxx, maxy = self.bbox
        geo_w = maxx - minx
        geo_h = maxy - miny
        if geo_w <= 0 or geo_h <= 0:
            # Degenerate bbox: fall back to defaults for any auto dimension.
            w = D.DOCUMENT_WIDTH if w_auto else cast(float, width)
            h = D.DOCUMENT_HEIGHT if h_auto else cast(float, height)
            return w, h
        geo_aspect = geo_h / geo_w  # data height / width

        pad = D.VIEWPORT_PADDING_MAIN

        if h_auto:
            # Width fixed, derive height so content area matches data aspect.
            w = D.DOCUMENT_WIDTH if w_auto else cast(float, width)
            draw_w = D.LAYOUT_BASEMAP_WIDTH * w - 2 * pad
            draw_h = draw_w * geo_aspect
            mh = draw_h + 2 * pad
            h = mh / D.LAYOUT_BASEMAP_HEIGHT
            return w, h

        # Only width is auto: keep height, derive width.
        h = cast(float, height)
        draw_h = D.LAYOUT_BASEMAP_HEIGHT * h - 2 * pad
        draw_w = draw_h / geo_aspect
        mw = draw_w + 2 * pad
        w = mw / D.LAYOUT_BASEMAP_WIDTH
        return w, h

    def autosize(self):
        """Recompute the document so the content area fits the data exactly.

        Snaps the height to the current data aspect ratio (width fixed),
        removing aspect-ratio letterboxing.  Must be called before
        :meth:`add`-ing layers (it rebuilds the canvas and would discard
        already-rendered content).  Returns ``self`` for chaining.
        """
        from .layers import LayerStateError
        if self._built:
            raise LayerStateError(
                "autosize() must be called before the map is built / rendered"
            )
        # The width stays as-is; only the height snaps to the data.
        _, height = self._resolve_auto_dimensions(self.width, "auto")
        self.height = height
        self._auto_height = True
        self._init_kwargs["height"] = "auto"
        if self._font_scale_auto:
            import math as _math
            self.font_scale = D.FONT_SCALE_AUTO_COEFF * _math.sqrt(
                (self.width * self.height)
                / (D.FONT_SCALE_REFERENCE_WIDTH * D.FONT_SCALE_REFERENCE_HEIGHT)
            )
        self._rebuild_canvas()
        return self

    def _rebuild_canvas(self):
        """Recreate the SVG document and viewports for the current size."""
        self.svg = SvgDocument(width=self.width, height=self.height)
        self.svg.add_overlay_rect(
            "background", 0, 0, self.width, self.height,
            z_order=D.Z_BACKGROUND, fill=self._background,
        )
        self._cartouche_viewports = {}
        # Bounds registered so far belong to the previous canvas.
        self.overflow.clear()
        self._state.legend_bottom = None
        self._build_main_viewport()
        if self.cartouche_params:
            self._build_cartouches()
        # The zoom window and the gradients live in the document that was
        # just replaced: create them again on the new one.
        if self._zoom_params is not None:
            zoom_params = self._zoom_params
            self._zoom_viewport = None
            self._add_zoom_viewport(zoom_params)
        from .elements import RadialGradient
        for item in self._items:
            if isinstance(item, RadialGradient):
                item._apply(self)

    # ------------------------------------------------------------------
    # Public accessors for accumulated state
    # ------------------------------------------------------------------

    @property
    def overflow(self) -> OverflowRegistry:
        """Overflow registry (delegates to internal MapState)."""
        return self._state.overflow

    # ------------------------------------------------------------------
    # Layer id generation
    # ------------------------------------------------------------------

    def _next_layer_id(self, kind: str) -> int:
        """Return a unique, per-instance layer id for the given kind.

        Used internally by the ``Layer`` render paths (choropleth,
        proportional, situation, shadow...). The counter
        starts at 1 per kind and per ``Map`` instance,
        so two distinct maps never share ids and test order has no effect
        on generated SVG ids.

        Conventional kinds are ``"choropleth"``, ``"proportional"``,
        ``"situation"`` and ``"shadow"``. An unknown kind is accepted
        without warning: the helper creates the entry at 0 then increments.

        Parameters
        ----------
        kind : str
            Layer kind (e.g. ``"choropleth"``, ``"proportional"``,
            ``"situation"``).

        Returns
        -------
        int
            Next available id for this kind.
        """
        self._state.layer_counters[kind] = self._state.layer_counters.get(kind, 0) + 1
        return self._state.layer_counters[kind]

    # ------------------------------------------------------------------
    # First-class Layer API
    # ------------------------------------------------------------------

    def add(self, *items: Any) -> "Map":
        """Add layers and elements to the map, in place.

        Parameters
        ----------
        *items : Layer, Element, or list of them
            Layers (:class:`~mappyng.Choropleth`, :class:`~mappyng.Basemap`
            ...) and elements (:class:`~mappyng.Title`,
            :class:`~mappyng.ScaleBar`, :class:`~mappyng.Insets` ...).
            Each layer is assigned a unique ``id``. A layer already added
            to another map is copied (its data is shared), so the same
            layer object can be passed to several maps.

        Returns
        -------
        Map
            ``self``, to allow chaining.

        Raises
        ------
        RuntimeError
            If the map has already been built (its SVG is final, so a new
            item would not appear).
        TypeError
            If an item is neither a layer nor an element.

        Examples
        --------
        >>> m.add(Basemap()).add(Title("Population"))
        >>> m.add(Basemap(), Choropleth(gdf, column="density"), ScaleBar())
        """
        from .elements import Element as _Element
        from .layers import Layer as _Layer
        for item in items:
            if isinstance(item, (list, tuple)):
                self.add(*item)
                continue
            if not isinstance(item, (_Layer, _Element)):
                raise TypeError(
                    f"Map.add expects a layer or a map element, got "
                    f"{type(item).__name__}. Build one first, e.g. "
                    f"m.add(Choropleth(gdf, column='density')) or "
                    f"m.add(Title('...'))."
                )
            if self._built:
                raise RuntimeError(
                    "This map has already been built; its SVG is final, so a "
                    "new layer or element would not appear. Add everything "
                    "before m.render(...) / m.to_string(), or derive a new "
                    "map with m + item."
                )
            if isinstance(item, _Layer):
                # A layer belongs to one map: it is drawn once and carries
                # that map's id. Added to a second map, it is copied (the
                # data is shared), so both maps draw it.
                owner = getattr(item, "_owner", None)
                if owner is not None and owner() is not self:
                    item = item.copy()
                item._owner = weakref.ref(self)
                # Public Layer.id uses a separate counter namespace so it
                # never consumes the per-kind counter the render path uses
                # for internal SVG element ids.
                n = self._next_layer_id(f"_public:{item.kind}")
                item.id = f"{item.kind}-{n}"
                self._state.layers.append(item)
            else:
                item._apply(self)
            self._items.append(item)
        return self

    def copy(self) -> "Map":
        """Return an unbuilt copy of the map.

        The copy is rebuilt from the constructor arguments and the layers
        and elements added so far. Layers are copied; their data is
        shared.
        """
        new = Map(**self._init_kwargs)
        for item in self._items:
            new.add(item.copy())
        return new

    def __add__(self, other: Any) -> "Map":
        """Return a new map with *other* added; ``self`` is unchanged.

        Examples
        --------
        >>> base = Map(gdf) + Basemap() + Source("INSEE")
        >>> a = base + Choropleth(gdf, column="rate") + Title("Rate")
        >>> b = base + Proportional(pts, column="pop") + Title("Population")
        """
        from .elements import Element as _Element
        from .layers import Layer as _Layer
        if not isinstance(other, (_Layer, _Element, list, tuple)):
            return NotImplemented
        return self.copy().add(other)

    def remove(self, layer_or_id: "Layer | str") -> None:
        """Remove a registered layer, by object or by id.

        Parameters
        ----------
        layer_or_id : Layer or str
            The layer instance or its ``id``.

        Raises
        ------
        KeyError
            If no matching layer is registered.
        RuntimeError
            If the map has already been built.
        """
        if self._built:
            raise RuntimeError(
                "This map has already been built; layers can no longer be "
                "removed because the SVG is final."
            )
        layers = self._state.layers
        for i, lyr in enumerate(layers):
            if lyr is layer_or_id or lyr.id == layer_or_id:
                del layers[i]
                self._items = [it for it in self._items if it is not lyr]
                return
        raise KeyError(
            f"No layer matching {layer_or_id!r} is registered. Current "
            f"layer ids: {[lyr.id for lyr in layers]}."
        )

    @property
    def classification_reports(self) -> dict:
        """Classification report of each Choropleth, keyed by layer id.

        Filled when the map is built (``render``, ``svg`` ...). Each report
        gives the method really applied, the bounds, the number of features
        per class, the excluded values and any automatic adjustment.
        """
        return self._state.classification_reports

    @property
    def layers(self) -> "list[Layer]":
        """The registered first-class layers, in insertion order (copy)."""
        return list(self._state.layers)

    def get_layer(self, layer_id: str) -> "Layer":
        """Return a registered layer by its ``id``.

        Raises
        ------
        KeyError
            If no layer has that id.
        """
        for lyr in self._state.layers:
            if lyr.id == layer_id:
                return lyr
        raise KeyError(
            f"No layer with id {layer_id!r}. Current layer ids: "
            f"{[lyr.id for lyr in self._state.layers]}."
        )

    def _render_layers(self) -> None:
        """Render registered layers into the SVG.

        Called once by :meth:`_build`. Layers are drawn in ``z_index``
        order; ties keep insertion order (stable sort). Label layers come
        last, so their placement knows every symbol drawn. Invisible
        layers and already-rendered layers are skipped.
        """
        from .layers import Label, RenderContext
        ctx = RenderContext(self)
        ordered = sorted(
            self._state.layers,
            key=lambda lyr: (isinstance(lyr, Label), lyr.z_index),
        )
        for lyr in ordered:
            if lyr.visible and not lyr._rendered:
                lyr.render(ctx)

    # ------------------------------------------------------------------
    # Chrome convenience methods
    # ------------------------------------------------------------------

    def title(self, text: str, **kwargs: Any) -> "Map":
        """Add a title. Same as ``m.add(Title(text, **kwargs))``.

        See :class:`~mappyng.Title` for the parameters.
        """
        from .elements import Title
        return self.add(Title(text, **kwargs))

    def source(self, text: str, **kwargs: Any) -> "Map":
        """Add a source line. Same as ``m.add(Source(text, **kwargs))``.

        See :class:`~mappyng.Source` for the parameters.
        """
        from .elements import Source
        return self.add(Source(text, **kwargs))

    def scale_bar(self, **kwargs: Any) -> "Map":
        """Add a scale bar. Same as ``m.add(ScaleBar(**kwargs))``.

        See :class:`~mappyng.ScaleBar` for the parameters.
        """
        from .elements import ScaleBar
        return self.add(ScaleBar(**kwargs))

    def north_arrow(self, **kwargs: Any) -> "Map":
        """Add a north arrow. Same as ``m.add(NorthArrow(**kwargs))``.

        See :class:`~mappyng.NorthArrow` for the parameters.
        """
        from .elements import NorthArrow
        return self.add(NorthArrow(**kwargs))

    def _render_chrome(self) -> None:
        """Draw the chrome elements, in the order they were first added."""
        for name, params in self._state.chrome.items():
            if name == "title":
                self._render_title(params)
            elif name == "source":
                self._render_source(params)
            elif name == "scale_bar":
                self._render_scale_bar(params)
            elif name == "north_arrow":
                self._render_north_arrow(params or None)

    # ------------------------------------------------------------------
    # Build viewports
    # ------------------------------------------------------------------

    def _build_main_viewport(self) -> None:
        """Create the main map viewport using figure-fraction layout."""
        mx = self._fig_x(D.LAYOUT_BASEMAP_X0)
        my = self._fig_y(D.LAYOUT_BASEMAP_Y0 + D.LAYOUT_BASEMAP_HEIGHT)
        mw = self._fig_w(D.LAYOUT_BASEMAP_WIDTH)
        mh = self._fig_h(D.LAYOUT_BASEMAP_HEIGHT)

        vb = ViewBox(
            geo_bounds=tuple(self.bbox),
            svg_x=mx, svg_y=my,
            svg_width=max(mw, 1), svg_height=max(mh, 1),
            padding=D.VIEWPORT_PADDING_MAIN,
            precision=self._coordinate_precision,
            crs=self.gdf.crs,
        )
        self.main = SvgViewport(
            "main", vb,
            border_radius=self._main_border_radius,
            box_shadow=self._main_box_shadow,
            glow=self._main_glow,
        )
        self._add_ocean(self.main)
        self.svg.add_viewport(self.main)

    def _add_cartouche_viewport(self, index: int, params: dict[str, Any],
                                x: float, y: float, w: float, h: float) -> None:
        """Create the cartouche viewport *index* at the given SVG box."""
        vb = ViewBox(
            geo_bounds=tuple(make_bbox_square(params['bbox'])),
            svg_x=x,
            svg_y=y,
            svg_width=w,
            svg_height=h,
            padding=D.VIEWPORT_PADDING_CARTOUCHE,
            precision=self._coordinate_precision,
            crs=params.get('crs') or self.gdf.crs,
        )
        vp = SvgViewport(
            f"cartouche_{index}", vb,
            border=True,
            border_color=params.get('border_color',
                                    self.style.config.layout_edge_color),
            border_width=params.get('border_width',
                                    D.CARTOUCHE_BORDER_WIDTH),
            border_radius=params.get('border_radius', D.BORDER_RADIUS),
            box_shadow=params.get('box_shadow', None),
            glow=params.get('glow', None),
        )
        self._add_ocean(vp)
        self._cartouche_viewports[index] = vp
        self.svg.add_viewport(vp)

    def _draw_cartouche_title(self, title: str, size: float,
                              x: float, y: float) -> None:
        """Draw a cartouche title, centred on *x* with its baseline at *y*."""
        self.svg.add_overlay_text(
            "cartouche_titles", x, y, title,
            z_order=D.Z_CARTOUCHE_TITLE,
            text_anchor="middle",
            font_size=size,
            fill=self.style["title_color"],
            font_family=D.FONT_FAMILY,
        )

    def _build_cartouches(self) -> None:
        """Create cartouche viewports to the left of the basemap.

        Aligned to main.viewbox.content_y (the actual top of the
        geographic content after aspect-ratio fitting), not the
        viewport top. This ensures cartouches start at the same
        visual level as the map content.

        Per-cartouche keys in ``cartouche_params[i]``:

        - ``bbox``, ``crs`` (required)
        - ``cartouche_title``, ``cartouche_title_size``
        - ``size`` (float): scale factor relative to the default
          cartouche size (default 1.0). E.g. 1.5 = 50 % larger.
        - ``spacing`` (float): vertical spacing **above** this
          cartouche, in pixels. Overrides the global default for
          this cartouche only.
        - ``border_radius`` (float): corner radius in pixels (0 = sharp).
        - ``border_color`` (str): override border stroke color.
        - ``border_width`` (float): override border stroke width.
        - ``box_shadow`` (bool or dict): drop shadow behind the cartouche.
          ``True`` for defaults; dict to override keys (dx, dy, blur, color,
          opacity).
        - ``glow`` (bool or dict): outer glow effect.
        """
        if not self.cartouche_params:
            return

        # Default cartouche size in figure fraction (square)
        cart_frac = D.LAYOUT_CARTOUCHE_SIZE * D.LAYOUT_BASEMAP_HEIGHT
        default_w_px = self._fig_w(cart_frac)
        default_h_px = self._fig_h(cart_frac)

        # Default vertical spacing between cartouches (in pixels)
        if self._cartouche_spacing_override is not None:
            default_v_spacing = self._cartouche_spacing_override
            default_title_gap = 0.0
        else:
            default_v_spacing = D.LAYOUT_CARTOUCHE_VSPACING * self.height
            default_title_gap = D.LAYOUT_CARTOUCHE_TITLE_GAP * self.height

        # Vertical: align to main content top + small title offset
        title_offset_px = D.LAYOUT_CARTOUCHE_TITLE_OFFSET * self.height
        y_cursor = self.main.viewbox.content_y + title_offset_px

        sorted_keys = sorted(self.cartouche_params.keys())

        for i, index in enumerate(sorted_keys):
            params = self.cartouche_params[index]
            if 'bbox' not in params or 'crs' not in params:
                warnings.warn(f"Cartouche {index}: missing 'bbox' or 'crs', skipping")
                continue

            title = params.get('cartouche_title', '')
            title_size = params.get('cartouche_title_size',
                                    D.CARTOUCHE_TITLE_SIZE) * self.font_scale

            # Per-cartouche size (scale factor, default 1.0)
            scale = params.get('size', 1.0)
            cart_w_px = default_w_px * scale
            cart_h_px = default_h_px * scale

            # Horizontal position: left of basemap content
            cart_x_px = (self.main.viewbox.content_x
                         - cart_w_px
                         - D.LAYOUT_CARTOUCHE_HSPACING * self.width)

            # Per-cartouche spacing above (pixels)
            if i > 0:
                spacing = params.get('spacing', default_v_spacing)
                y_cursor += spacing
                # Extra gap if this cartouche has a title
                if title and 'spacing' not in params:
                    y_cursor += default_title_gap

            # Title space above cartouche
            title_h = (title_size + D.CARTOUCHE_TITLE_PADDING) if title else 0
            cart_y_px = y_cursor + title_h

            self._add_cartouche_viewport(
                index, params, cart_x_px, cart_y_px, cart_w_px, cart_h_px)

            if title:
                self._draw_cartouche_title(
                    title, title_size, cart_x_px + cart_w_px / 2,
                    cart_y_px - D.CARTOUCHE_TITLE_MARGIN_ABOVE)

            # Advance cursor past this cartouche
            y_cursor = cart_y_px + cart_h_px

        self._fix_cartouche_overflow()

    def _set_cartouches(self, params: dict[int, Any],
                        spacing: float | None = None) -> None:
        """Define the cartouches and build their viewports."""
        if self.cartouche_params:
            raise ValueError(
                "This map already has cartouches (from cartouche_params or "
                "an earlier Insets). Declare all cartouches in a single "
                "Insets."
            )
        self.cartouche_params = params
        self._cartouche_spacing_override = spacing
        self._build_cartouches()

    def _fix_cartouche_overflow(self) -> None:
        """Register cartouche viewport bounds into the overflow registry."""
        for vp in self._cartouche_viewports.values():
            self.overflow.register(
                vp.viewbox.svg_x, vp.viewbox.svg_y,
                vp.viewbox.svg_x + vp.viewbox.svg_width,
                vp.viewbox.svg_y + vp.viewbox.svg_height,
            )

    # ------------------------------------------------------------------
    # Zoom
    # ------------------------------------------------------------------

    def add_zoom(self, params: dict[str, Any]) -> SvgViewport:
        """Add a zoom window. Same as ``m.add(Zoom(**params))``.

        See :class:`~mappyng.Zoom` for the parameters. Returns the zoom
        viewport.
        """
        from .elements import Zoom
        self.add(Zoom(**params))
        assert self._zoom_viewport is not None  # created by Zoom._apply
        return self._zoom_viewport

    def _add_zoom_viewport(self, params: dict[str, Any]) -> SvgViewport:
        """Create the zoom window viewport.

        Parameters (dict keys)
        ----------------------
        bbox : list
            Geographic bounding box [minx, miny, maxx, maxy] (required).
        x, y : float, optional
            Position in SVG pixels (defaults to mappyng figure-fraction).
        width, height : float, optional
            Zoom window size in pixels.
        border_color : str, optional
            Border color.
        border_width : float
            Border stroke width.
        border_radius : float
            Corner radius in pixels (0 = sharp corners).
        box_shadow : bool or dict
            Drop shadow behind the zoom window. ``True`` for defaults;
            dict to override keys (dx, dy, blur, color, opacity).
        glow : bool or dict
            Outer glow effect.

        Returns
        -------
        SvgViewport
        """
        if self._zoom_viewport is not None:
            raise ValueError(
                "This map already has a zoom window; a map holds at most one."
            )
        self._zoom_params = dict(params)  # for serialisation
        cfg = dict(params)
        bbox = cfg.pop("bbox")
        x = cfg.pop("x", None)
        y = cfg.pop("y", None)
        width = cfg.pop("width", None)
        height = cfg.pop("height", None)
        border_color = cfg.pop("border_color", None)
        border_width = cfg.pop("border_width", D.ZOOM_BORDER_WIDTH)
        border_radius = cfg.pop("border_radius", D.BORDER_RADIUS)
        box_shadow = cfg.pop("box_shadow", None)
        glow = cfg.pop("glow", None)

        self._zoom_bbox = list(bbox)

        zw = width if width is not None else self._fig_w(D.LAYOUT_ZOOM_WIDTH)
        zh = height if height is not None else self._fig_h(D.LAYOUT_ZOOM_HEIGHT)
        zx = x if x is not None else self._fig_x(D.LAYOUT_ZOOM_LEFT)
        zy = y if y is not None else self._fig_y(
            D.LAYOUT_ZOOM_BOTTOM + D.LAYOUT_ZOOM_HEIGHT)
        bc = border_color or self.style.config.layout_edge_color

        vb = ViewBox(
            geo_bounds=tuple(bbox),
            svg_x=zx, svg_y=zy,
            svg_width=zw, svg_height=zh,
            padding=D.VIEWPORT_PADDING_ZOOM,
            precision=self._coordinate_precision,
            crs=self.gdf.crs,
        )
        self._zoom_viewport = SvgViewport(
            "zoom", vb,
            border=True, border_color=bc, border_width=border_width,
            border_radius=border_radius,
            box_shadow=box_shadow, glow=glow,
        )
        self._add_ocean(self._zoom_viewport)
        self.svg.add_viewport(self._zoom_viewport)
        return self._zoom_viewport

    # ------------------------------------------------------------------
    # Labels (toponyms)
    # ------------------------------------------------------------------

    def _label_viewport(self, target: str) -> tuple[SvgViewport, Any]:
        """Resolve a label *target* to ``(viewport, crs of its coordinates)``."""
        if target == "main":
            return self.main, self.gdf.crs
        if target == "zoom":
            if self._zoom_viewport is None:
                raise ValueError(
                    "Label(target='zoom'): no zoom viewport exists yet. "
                    "Call m.add_zoom(...) before adding labels on the zoom."
                )
            return self._zoom_viewport, self.gdf.crs
        if target.startswith("cartouche:"):
            idx = int(target.split(":")[1])
            if idx not in self._cartouche_viewports:
                raise ValueError(
                    f"Label(target='cartouche:{idx}'): cartouche {idx} "
                    f"is not defined. Pass cartouche_params for index {idx} "
                    f"when creating the Map."
                )
            return (self._cartouche_viewports[idx],
                    self.cartouche_params[idx].get("crs", self.gdf.crs))
        raise ValueError(
            f"Label: unknown target '{target}'. Use 'main', "
            f"'zoom', or 'cartouche:<index>'."
        )

    @staticmethod
    def _label_detail(gdf: gpd.GeoDataFrame, target: str, detail: Any,
                      detail_join: Any) -> gpd.GeoDataFrame:
        """Swap in the finer geometry of a zoom or cartouche *target*."""
        if target == "main":
            return gdf
        finer = detail_for(
            normalize_detail(detail),
            ZOOM if target == "zoom" else int(target.split(":")[1]))
        if finer is None:
            return gdf
        joined = join_detail(gdf, finer, detail_join, what="label")
        if joined.index.has_duplicates:
            # several finer parts of one unit (islands): label the unit once
            joined = joined.dissolve(level=0, aggfunc="first")
        return joined

    def _numbered_legend_xy(self, cfg: Any, n_labels: int) -> tuple[float, float]:
        """Top-left SVG position of the numbered legend of a non-main target."""
        from .toponyme import _numbered_ranked, numbered_legend_size

        if cfg.numbered_legend_position is not None:
            # Manual placement via figure fractions {"x": ..., "y": ...}
            # Convention: (0,0) = bottom-left, (1,1) = top-right (same as
            # other mappyng legend positions).  _fig_y flips to SVG coords.
            fx = cfg.numbered_legend_position.get("x", 0.75)
            fy = cfg.numbered_legend_position.get("y", 0.10)
            # Estimate legend height to anchor bottom edge at fy
            ranked_est = _numbered_ranked(
                [type("L", (), {"priority": 0, "text": ""})()]
                * min(n_labels, 10)
            )
            _, leg_h = numbered_legend_size(ranked_est, cfg)
            # fy is the bottom edge to SVG y of top = _fig_y(fy) - leg_h
            return self._fig_x(fx), self._fig_y(fy) - leg_h

        # Auto default: bottom-right, aligned with the legend column.
        # Estimate legend dimensions with max 10 items.
        n_est = min(n_labels, 10)
        dummy = type("L", (), {"priority": 0, "text": "ABCDEFGHIJ"})
        ranked_est = [dummy() for _ in range(n_est)]
        leg_w, leg_h = numbered_legend_size(ranked_est, cfg)
        pad = self.padding
        return self.width - pad - leg_w, self.height - pad - leg_h

    def _render_labels(self, gdf: gpd.GeoDataFrame,
                       column: str, detail: Any = None,
                       detail_join: Any = None, **kwargs) -> None:
        """Place automatic labels on map features using simulated annealing.

        Parameters
        ----------
        gdf : GeoDataFrame
            Features to label. Any CRS is accepted (auto-reprojected).
        column : str
            Column containing the label text.
        detail, detail_join
            Finer geometry for a zoom or cartouche target, see
            :mod:`mappyng.detail`. A unit made of several finer parts is
            labelled once.
        **kwargs
            Any field of :class:`~mappyng.toponyme.LabelConfig`:
            ``font_size``, ``font_weight``, ``color``, ``halo_color``,
            ``halo_width``, ``priority_col``, ``max_labels``,
            ``initial_position``, ``label_offset``, ``max_displacement``,
            ``avoid_overlap``, ``allow_hide``, ``leader_lines``,
            ``leader_threshold``, ``n_sweeps``, ``seed``, ``target``, etc.

        Example::

            m.add(Label(gdf_villes, column="nom",
                             priority_col="population",
                             max_labels=20,
                             font_size=9,
                             n_sweeps=50))
        """
        from . import defaults as D
        from .toponyme import LabelConfig, place_labels

        # Build config
        target = kwargs.pop("target", "main")
        # Propagate the Map-level seed unless this call sets one explicitly.
        if "seed" not in kwargs:
            kwargs["seed"] = self._seed
        cfg = LabelConfig(target=target, **kwargs)

        viewport, crs = self._label_viewport(target)
        gdf = self._label_detail(gdf, target, detail, detail_join)

        # Reproject to viewport CRS
        if gdf.crs is not None and crs is not None:
            try:
                gdf_proj = gdf.to_crs(crs)
            except GEO_ERRORS as e:
                warnings.warn(
                    f"Label: could not reproject the data to the viewport "
                    f"CRS ({e}); labels are placed using the original "
                    f"coordinates and may be misplaced."
                )
                gdf_proj = gdf
        else:
            gdf_proj = gdf

        # For non-main viewports in numbered mode: emit legend on main layer.
        legend_layer = None
        legend_xy = None
        if cfg.numbered_above is not None and target != "main":
            legend_layer = self.main.get_layer("labels_legend", z_order=D.Z_TOPONYME + 1)
            legend_xy = self._numbered_legend_xy(cfg, len(gdf_proj))

        place_labels(
            gdf=gdf_proj,
            column=column,
            viewbox=viewport.viewbox,
            viewport=viewport,
            symbols=viewport.symbols,
            chrome_bboxes_svg=self._state.chrome_bboxes,
            config=cfg,
            z_order=D.Z_TOPONYME,
            legend_layer=legend_layer,
            legend_xy=legend_xy,
        )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def zoom_viewport(self) -> SvgViewport | None:
        """The zoom viewport, if created."""
        return self._zoom_viewport

    def get_cartouche_viewport(self, index: int) -> SvgViewport | None:
        """Get a cartouche viewport by index."""
        return self._cartouche_viewports.get(index)

    @property
    def cartouche_viewports(self) -> dict[int, SvgViewport]:
        """All cartouche viewports."""
        return self._cartouche_viewports

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _in_map_crs(self, gdf: Any) -> Any:
        """Return *gdf* in the CRS of the map, reprojecting it if needed.

        A layer may come in another CRS than the map's GeoDataFrame; drawn
        as is, its coordinates would fall outside the map and nothing would
        appear. Data without a CRS (or a map without one) is left untouched.
        """
        map_crs = self.gdf.crs
        crs = getattr(gdf, "crs", None)
        if gdf is None or map_crs is None or crs is None or crs == map_crs:
            return gdf
        try:
            return gdf.to_crs(map_crs)
        except GEO_ERRORS as e:
            warnings.warn(
                f"A layer is in CRS {crs.to_string()} and could not be "
                f"reprojected to the map CRS ({e}); it is drawn with its "
                f"original coordinates and may be misplaced or missing."
            )
            return gdf

    def _clip_gdf(self, gdf: gpd.GeoDataFrame,
                  bbox: list[float]) -> gpd.GeoDataFrame:
        """Clip a GeoDataFrame to a bounding box."""
        try:
            clip_geom = box(*bbox)
            clipped = gdf.clip(mask=clip_geom)
            return clipped[~clipped.is_empty]
        except GEO_ERRORS as e:
            warnings.warn(f"Clip failed ({e}), returning unclipped data")
            return gdf

    def _prepare_cartouche_data(self, gdf: gpd.GeoDataFrame,
                                params: dict[str, Any]) -> gpd.GeoDataFrame:
        """Reproject and clip data for a cartouche."""
        if gdf is None or gdf.empty:
            return gdf
        try:
            local = gdf
            if 'crs' in params and gdf.crs:
                local = gdf.to_crs(params['crs'])
            if 'bbox' in params:
                clip_geom = box(*params['bbox'])
                local = local.clip(mask=clip_geom)
                local = local[~local.is_empty]
            return local
        except GEO_ERRORS as e:
            warnings.warn(f"Error preparing cartouche data: {e}")
            return gdf.iloc[0:0]

    # ------------------------------------------------------------------
    # Interactive export
    # ------------------------------------------------------------------

    def to_interactive(
        self,
        columns: list[str] | None = None,
        aliases: dict[str, str] | None = None,
        tooltip: dict[str, Any] | None = None,
    ) -> "InteractiveMap":
        """Export the map as an interactive SVG with hover tooltips.

        Returns an :class:`~mappyng.interactive.InteractiveMap` that
        auto-renders in Jupyter and can be saved as standalone HTML.
        Arguments left to None take their value from the
        :class:`~mappyng.Tooltip` added to the map, if any.

        Parameters
        ----------
        columns : list of str, optional
            Restrict tooltip to these columns.  If *None*, all
            non-internal columns are shown.
        aliases : dict, optional
            Column name to display label mapping, e.g.
            ``{"LIB_GEO": "Département"}``.
        tooltip : dict, optional
            Tooltip appearance, any field of
            :class:`~mappyng.interactive.TooltipStyle`:
            ``background``, ``text_color``, ``font_size``,
            ``font_family``, ``border_radius``, ``key_weight``,
            ``highlight_opacity``.

        Returns
        -------
        InteractiveMap
            Object with ``_repr_html_()`` and ``.save(path)``
            methods.

        Examples
        --------
        >>> m.to_interactive(
        ...     columns=["LIB_GEO", "population"],
        ...     aliases={"LIB_GEO": "Département"},
        ...     tooltip={"background": "#1a1a2e", "font_size": 13},
        ... )
        """
        from .interactive import (
            InteractiveMap,
            _build_tooltip_map,
            _ensure_tooltip_style,
            auto_detect_columns,
            inject_tooltips,
        )

        hover_opacity = None
        if self._tooltip is not None:
            stored = self._tooltip.to_kwargs()
            columns = stored["columns"] if columns is None else columns
            aliases = stored["aliases"] if aliases is None else aliases
            tooltip = stored["tooltip"] if tooltip is None else tooltip
            hover_opacity = stored["hover_opacity"]

        # Render layers first: interactive metadata is recorded when each
        # layer renders (deferred).
        self._build()

        # Tooltip(hover_opacity=...) is a shorthand for
        # tooltip={"hover": {"opacity": <value>}}
        if hover_opacity is not None:
            tooltip = dict(tooltip or {})
            hover_raw = tooltip.get("hover", {})
            if isinstance(hover_raw, dict):
                hover_raw = dict(hover_raw)
            else:
                hover_raw = {}
            hover_raw["opacity"] = float(hover_opacity)
            tooltip["hover"] = hover_raw

        style = _ensure_tooltip_style(tooltip)

        tooltip_maps = []
        for layer in self._state.interactive_layers:
            gdf = layer["gdf"]
            cols = columns or auto_detect_columns(gdf)
            tm = _build_tooltip_map(
                gdf, cols,
                aliases=aliases,
                id_prefix=layer["id_prefix"],
            )
            tooltip_maps.append(tm)

        svg_str = self.to_string()
        interactive_svg = inject_tooltips(svg_str, tooltip_maps, style)
        return InteractiveMap(interactive_svg)

    def save_interactive(
        self,
        path: str,
        columns: list[str] | None = None,
        aliases: dict[str, str] | None = None,
        tooltip: dict[str, Any] | None = None,
        title: str = "Interactive Map",
    ) -> None:
        """Save the map as an interactive HTML file.

        Convenience wrapper around :meth:`to_interactive` +
        :meth:`InteractiveMap.save`.

        Parameters
        ----------
        path : str
            Output file path.
        columns, aliases, tooltip
            See :meth:`to_interactive`.
        title : str
            HTML page title.
        """
        self.to_interactive(
            columns=columns, aliases=aliases, tooltip=tooltip,
        ).save(path, title=title)

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------

    def _resolve_overflow(self) -> None:
        """Expand SVG viewBox to contain all registered bounding boxes (once)."""
        if getattr(self, "_overflow_resolved", False):
            return
        self._overflow_resolved = True
        self.overflow.resolve(self)

    def _build(self) -> None:
        """Finalise the map in memory (idempotent).

        Resolves overflow (mutating viewports) and builds viewport XML
        elements. Does NOT serialise to string or write any file, those
        remain the responsibility of to_string() / save().

        Safe to call multiple times: subsequent calls are no-ops.

        Notes
        -----
        This is the single finalisation entry point used by all output
        methods (save, to_string, _repr_svg_, to_interactive).
        """
        if self._built:
            return
        self._render_chrome()
        self._render_layers()
        self._resolve_overflow()
        self.svg._build_viewports()
        self._built = True

    def render(self, path: str, dpi: int = D.EXPORT_DEFAULT_DPI) -> "Map":
        """Render the map to a file. Format inferred from the extension.

        ``.svg`` (or no extension) is written natively. ``.html`` writes
        the interactive export (see :meth:`to_interactive`). ``.png`` and
        ``.pdf`` are rendered from the SVG via the optional ``cairosvg``
        dependency (``pip install mappyng[export]``); the SVG remains the
        canonical source.

        Parameters
        ----------
        path : str
            Destination file path. The extension selects the format:
            ``.svg`` (default), ``.html``, ``.png`` or ``.pdf``.
        dpi : int
            Resolution for PNG export (ignored for SVG and PDF).
            Defaults to :data:`~mappyng.defaults.EXPORT_DEFAULT_DPI`.

        Returns
        -------
        Map
            ``self``, to allow chaining.

        Raises
        ------
        ValueError
            If the extension is none of ``.svg``, ``.html``, ``.png``,
            ``.pdf``.
        ImportError
            If a PNG/PDF export is requested but ``cairosvg`` is not
            installed.
        """
        self._build()
        ext = os.path.splitext(path)[1].lower()
        if ext in ("", ".svg"):
            self.svg.save(path)
            return self
        if ext == ".html":
            self.to_interactive().save(path)
            return self
        if ext not in (".png", ".pdf"):
            raise ValueError(
                f"Unsupported export format '{ext}'. mappyng writes .svg "
                f"and .html natively and .png/.pdf via cairosvg. Use one of "
                f"these."
            )
        try:
            import cairosvg
        except ImportError as e:
            raise ImportError(
                f"Exporting to {ext} requires the optional 'cairosvg' "
                f"dependency, which is not installed. Install it with:\n"
                f"    pip install mappyng[export]\n"
                f"Native SVG export (.svg) works without it."
            ) from e
        svg_bytes = self.to_string().encode("utf-8")
        if ext == ".png":
            # The SVG is sized in pixels, which cairosvg maps to 96 dpi
            # whatever its own dpi argument: the resolution is a scale.
            cairosvg.svg2png(bytestring=svg_bytes, write_to=path,
                             scale=dpi / D.SVG_REFERENCE_DPI)
        else:  # .pdf
            cairosvg.svg2pdf(bytestring=svg_bytes, write_to=path)
        return self

    def to_string(self) -> str:
        """Render the map and return the SVG markup as a string.

        Returns
        -------
        str
            Self-contained SVG string, ready for embedding or saving.
        """
        self._build()
        return self.svg.to_string()

    # ------------------------------------------------------------------
    # YAML serialisation
    # ------------------------------------------------------------------

    def to_yaml(self, path: str | None = None) -> str:
        """Serialise the map's intent to YAML.

        The output captures the configuration, the ordered layers with
        their parameters, and the chrome. It does not store the SVG nor
        the geometry. Geometry is reattached at load time (see
        :meth:`from_yaml`).

        Parameters
        ----------
        path : str, optional
            If given, the YAML is also written to this file.

        Returns
        -------
        str
            The YAML document.
        """
        from .serialize import to_yaml as _to_yaml
        return _to_yaml(self, path)

    def recipe(self, path: str | None = None) -> dict:
        """Reproducibility recipe: parameters, data fingerprints, versions.

        Returns a plain dict with the mappyng/Python/library versions, the
        seed, the map document (as in :meth:`to_yaml`), a SHA-256 fingerprint
        of the main geometry and of each layer's data, and the classification
        reports of the thematic layers already built (call it after
        ``render``). Written to *path* (YAML for ``.yaml``/``.yml``, JSON
        otherwise) when given.
        """
        from .serialize import recipe as _recipe
        return _recipe(self, path)

    @classmethod
    def from_yaml(cls, source: str, gdf: "gpd.GeoDataFrame" = None,
                  data: dict[str, Any] | None = None,
                  base_dir: str | None = None) -> "Map":
        """Rebuild a map from a YAML file path or string.

        The serialised form stores layers by reference, not geometry, so
        the geometry has to come from somewhere. Either supply it with
        *gdf* (and optionally per-layer *data*), or let the document carry
        its own sources: a ``data:`` block with a ``dataset:`` (a built-in
        dataset) or a ``path:`` (a vector file), with optional ``crs``,
        ``filter``, and CSV ``join``, on the map or on each layer. A
        fully source-bearing document builds with no Python at all.

        Parameters
        ----------
        source : str
            A YAML file path or a YAML string.
        gdf : GeoDataFrame, optional
            Base geometry. When given, declared sources are ignored.
        data : dict, optional
            Per-layer geometry override, keyed by layer ``id``.
        base_dir : str, optional
            Directory that relative ``path:`` entries resolve against.
            Defaults to the YAML file's directory (or the cwd for a string).

        Returns
        -------
        Map
        """
        from .serialize import from_yaml as _from_yaml
        return _from_yaml(source, gdf=gdf, data=data, base_dir=base_dir)

    def _repr_svg_(self) -> str:
        """Jupyter notebook SVG display."""
        self._build()
        return self.svg.to_string()

    def _repr_html_(self) -> str | None:
        """Jupyter notebook display with tooltips, when a Tooltip is set."""
        if self._tooltip is None:
            return None
        return self.to_interactive()._repr_html_()
