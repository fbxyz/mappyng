"""
SVG renderer for mappyng.

Core concepts:
- ViewBox: transforms geographic coordinates to SVG pixel coordinates
- SvgViewport: a rectangular area of the SVG with its own ViewBox and clip region
  (used for the main map, each cartouche, and zoom windows)
- SvgDocument: the root SVG document managing viewports, defs, and serialization
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import geopandas as gpd
import numpy as np
from shapely.geometry import (
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)

from . import defaults as D

# ============================================================================
# Coordinate Transform
# ============================================================================

@dataclass
class ViewBox:
    """Maps geographic coordinates to SVG pixel coordinates.

    Parameters
    ----------
    geo_bounds : tuple
        Geographic bounds (minx, miny, maxx, maxy).
    svg_x : float
        Left edge of the drawing area in SVG pixels.
    svg_y : float
        Top edge of the drawing area in SVG pixels.
    svg_width : float
        Width of the drawing area in SVG pixels.
    svg_height : float
        Height of the drawing area in SVG pixels.
    padding : float
        Padding in pixels inside the drawing area.
    """
    geo_bounds: tuple[float, ...]
    svg_x: float = 0
    svg_y: float = 0
    svg_width: float = D.DOCUMENT_WIDTH
    svg_height: float = D.DOCUMENT_HEIGHT
    padding: float = D.VIEWPORT_PADDING_MAIN
    precision: int = D.DEFAULT_COORDINATE_PRECISION
    #: CRS of ``geo_bounds`` (used to place elements from geographic coordinates).
    crs: Any = None

    def __post_init__(self):
        minx, miny, maxx, maxy = self.geo_bounds
        geo_w = maxx - minx
        geo_h = maxy - miny

        # Available drawing area inside padding
        draw_w = self.svg_width - 2 * self.padding
        draw_h = self.svg_height - 2 * self.padding

        # Scale to fit while preserving aspect ratio
        scale_x = draw_w / geo_w if geo_w > 0 else 1
        scale_y = draw_h / geo_h if geo_h > 0 else 1
        self.scale = min(scale_x, scale_y)

        # Center the map in the available area
        actual_w = geo_w * self.scale
        actual_h = geo_h * self.scale
        self.offset_x = self.svg_x + self.padding + (draw_w - actual_w) / 2
        self.offset_y = self.svg_y + self.padding + (draw_h - actual_h) / 2

        # Store geo origin
        self._geo_minx = minx
        self._geo_maxy = maxy

        # Computed content bounds (for layout positioning)
        self.content_x = self.offset_x
        self.content_y = self.offset_y
        self.content_width = actual_w
        self.content_height = actual_h

    def geo_to_svg(self, x: float, y: float) -> tuple[float, float]:
        """Convert geographic (x, y) to SVG pixel (px, py).

        Y axis is flipped: geo-y increases upward, SVG-y increases downward.
        """
        px = self.offset_x + (x - self._geo_minx) * self.scale
        py = self.offset_y + (self._geo_maxy - y) * self.scale
        return px, py

    def geo_to_svg_array(self, xs: np.ndarray, ys: np.ndarray):
        """Convert arrays of geographic coordinates to SVG pixel arrays.

        Vectorized form of :meth:`geo_to_svg`. The arithmetic is the same
        per element, so a single point gives the same value either way.

        Parameters
        ----------
        xs, ys : numpy.ndarray
            Geographic x and y coordinates.

        Returns
        -------
        tuple of numpy.ndarray
            The ``(px, py)`` SVG pixel coordinates.
        """
        px = self.offset_x + (xs - self._geo_minx) * self.scale
        py = self.offset_y + (self._geo_maxy - ys) * self.scale
        return px, py

    def geo_length_to_svg(self, length: float) -> float:
        """Convert a geographic distance to SVG pixels."""
        return abs(length * self.scale)


# ============================================================================
# Geometry to SVG path conversion
# ============================================================================

def _coords_to_path(coords, viewbox: ViewBox, *, close: bool) -> str:
    """Convert a coordinate sequence to an SVG path 'd' fragment.

    The transform is vectorized with numpy: coordinates are extracted in a
    single pass and projected in one array operation. Coordinates are
    formatted to ``viewbox.precision`` decimal places. Consecutive points
    that share the same formatted position are dropped, since they land on
    the same pixel and add nothing to the drawn shape.

    Parameters
    ----------
    coords : sequence
        Coordinate pairs (a Shapely coordinate sequence or array-like). A
        Z component, if present, is ignored.
    viewbox : ViewBox
        Coordinate transform. Its ``precision`` sets the decimal places.
    close : bool
        Append a ``Z`` command to close the path (rings) or not (open
        lines).
    """
    arr = np.asarray(coords, dtype=float)
    if arr.shape[0] == 0:
        return ""
    px, py = viewbox.geo_to_svg_array(arr[:, 0], arr[:, 1])
    p = viewbox.precision
    tokens = [f"{px[i]:.{p}f} {py[i]:.{p}f}" for i in range(px.shape[0])]
    parts = [f"M{tokens[0]}"]
    prev = tokens[0]
    for tok in tokens[1:]:
        if tok != prev:
            parts.append(f"L{tok}")
            prev = tok
    if close:
        parts.append("Z")
    return " ".join(parts)


def _ring_to_path(coords, viewbox: ViewBox) -> str:
    """Convert a closed ring coordinate sequence to an SVG path fragment."""
    return _coords_to_path(coords, viewbox, close=True)


def polygon_to_path(polygon: Polygon, viewbox: ViewBox) -> str:
    """Convert a Shapely Polygon to an SVG path 'd' string."""
    d = _ring_to_path(polygon.exterior.coords, viewbox)
    for interior in polygon.interiors:
        d += " " + _ring_to_path(interior.coords, viewbox)
    return d


def geometry_to_paths(geom, viewbox: ViewBox) -> list[str]:
    """Convert any Shapely geometry to a list of SVG path 'd' strings."""
    if isinstance(geom, Polygon):
        return [polygon_to_path(geom, viewbox)]
    elif isinstance(geom, MultiPolygon):
        return [polygon_to_path(p, viewbox) for p in geom.geoms]
    elif isinstance(geom, LineString):
        return [_coords_to_path(geom.coords, viewbox, close=False)]
    elif isinstance(geom, MultiLineString):
        paths = []
        for line in geom.geoms:
            paths.extend(geometry_to_paths(line, viewbox))
        return paths
    elif isinstance(geom, (Point, MultiPoint)):
        return []  # Points are handled as <circle> elements
    elif isinstance(geom, GeometryCollection):
        paths = []
        for g in geom.geoms:
            paths.extend(geometry_to_paths(g, viewbox))
        return paths
    return []


# ============================================================================
# SVG Viewport, a sub-region of the SVG with its own coordinate system
# ============================================================================

@dataclass
class SvgLayer:
    """A named SVG group with a z-order for stacking."""
    name: str
    z_order: int
    element: ET.Element = field(default=None)  # type: ignore[arg-type]  # set in __post_init__

    def __post_init__(self):
        if self.element is None:
            self.element = ET.Element("g", id=self.name)


class SvgViewport:
    """A rectangular region of the SVG document with its own geo to pixel transform.

    Used for the main map, cartouches (insets), and zoom windows.
    Each viewport has:
    - Its own ViewBox (coordinate transform)
    - A <clipPath> to constrain rendering
    - Its own set of named layers (SVG <g> groups)

    Parameters
    ----------
    name : str
        Identifier for this viewport (e.g. "main", "cartouche_0", "zoom").
    viewbox : ViewBox
        Coordinate transform for this viewport.
    border : bool
        Whether to draw a border around the viewport.
    border_color : str
        Border stroke color.
    border_width : float
        Border stroke width.
    """

    def __init__(self, name: str, viewbox: ViewBox, *,
                 border: bool = False,
                 border_color: str = D.VIEWPORT_BORDER_COLOR,
                 border_width: float = D.VIEWPORT_BORDER_WIDTH,
                 border_radius: float = D.BORDER_RADIUS,
                 box_shadow=None,
                 glow=None):
        self.name = name
        self.viewbox = viewbox
        self.border = border
        self.border_color = border_color
        self.border_width = border_width
        self.border_radius = border_radius
        self._box_shadow = box_shadow   # raw param, resolved at build time
        self._glow = glow               # raw param, resolved at build time
        self._layers: dict[str, SvgLayer] = {}
        # Point symbols drawn in this viewport, as (cx, cy, r) in SVG px.
        # Label placement avoids them.
        self.symbols: list[tuple[float, float, float]] = []

    def add_symbol_footprint(self, cx: float, cy: float, r: float) -> None:
        """Record a point symbol (disc of radius *r*) for label avoidance."""
        self.symbols.append((cx, cy, r))

    # ------------------------------------------------------------------
    # Layer management
    # ------------------------------------------------------------------

    def get_layer(self, name: str, z_order: int = 0) -> ET.Element:
        """Get or create a named layer (SVG <g> group) within this viewport."""
        full_name = f"{self.name}_{name}"
        if full_name not in self._layers:
            self._layers[full_name] = SvgLayer(name=full_name, z_order=z_order)
        return self._layers[full_name].element

    # ------------------------------------------------------------------
    # Drawing primitives
    # ------------------------------------------------------------------

    def add_rect(self, layer: str, x: float, y: float, w: float, h: float,
                 z_order: int = 0, **attrs) -> ET.Element:
        group = self.get_layer(layer, z_order)
        elem = ET.SubElement(group, "rect", x=f"{x:.2f}", y=f"{y:.2f}",
                             width=f"{w:.2f}", height=f"{h:.2f}")
        _apply_attrs(elem, attrs)
        return elem

    def add_path(self, layer: str, d: str, z_order: int = 0, **attrs) -> ET.Element:
        group = self.get_layer(layer, z_order)
        elem = ET.SubElement(group, "path", d=d)
        _apply_attrs(elem, attrs)
        return elem

    def add_circle(self, layer: str, cx: float, cy: float, r: float,
                   z_order: int = 0, **attrs) -> ET.Element:
        group = self.get_layer(layer, z_order)
        elem = ET.SubElement(group, "circle",
                             cx=f"{cx:.2f}", cy=f"{cy:.2f}", r=f"{r:.2f}")
        _apply_attrs(elem, attrs)
        return elem

    def add_text(self, layer: str, x: float, y: float, text: str,
                 z_order: int = 0, **attrs) -> ET.Element:
        group = self.get_layer(layer, z_order)
        elem = ET.SubElement(group, "text", x=f"{x:.2f}", y=f"{y:.2f}")
        elem.text = text
        _apply_attrs(elem, attrs)
        return elem

    def add_line(self, layer: str, x1: float, y1: float, x2: float, y2: float,
                 z_order: int = 0, **attrs) -> ET.Element:
        group = self.get_layer(layer, z_order)
        elem = ET.SubElement(group, "line",
                             x1=f"{x1:.2f}", y1=f"{y1:.2f}",
                             x2=f"{x2:.2f}", y2=f"{y2:.2f}")
        _apply_attrs(elem, attrs)
        return elem

    def add_image(self, layer: str, x: float, y: float,
                  width: float, height: float, href: str,
                  z_order: int = 0, **attrs) -> ET.Element:
        """Add a raster image (base64 or URL) to a layer."""
        group = self.get_layer(layer, z_order)
        elem = ET.SubElement(group, "image",
                             x=f"{x:.2f}", y=f"{y:.2f}",
                             width=f"{width:.2f}", height=f"{height:.2f}")
        elem.set("href", href)
        _apply_attrs(elem, attrs)
        return elem

    def add_group(self, layer: str, z_order: int = 0, **attrs) -> ET.Element:
        group = self.get_layer(layer, z_order)
        sub = ET.SubElement(group, "g")
        _apply_attrs(sub, attrs)
        return sub

    # ------------------------------------------------------------------
    # GeoDataFrame rendering helpers
    # ------------------------------------------------------------------

    def draw_geodataframe(self, layer: str, gdf: gpd.GeoDataFrame,
                          z_order: int = 0, **attrs) -> None:
        """Draw all geometries from a GeoDataFrame as SVG paths."""
        for geom in gdf.geometry:
            if geom is None or geom.is_empty:
                continue
            for d in geometry_to_paths(geom, self.viewbox):
                self.add_path(layer, d, z_order=z_order, **attrs)

    def draw_points(self, layer: str, gdf: gpd.GeoDataFrame, r: float = 3,
                    z_order: int = 0, **attrs) -> None:
        """Draw point geometries as SVG circles."""
        for geom in gdf.geometry:
            if geom is None or geom.is_empty:
                continue
            if isinstance(geom, Point):
                cx, cy = self.viewbox.geo_to_svg(geom.x, geom.y)
                self.add_circle(layer, cx, cy, r, z_order=z_order, **attrs)
            elif isinstance(geom, MultiPoint):
                for pt in geom.geoms:
                    cx, cy = self.viewbox.geo_to_svg(pt.x, pt.y)
                    self.add_circle(layer, cx, cy, r, z_order=z_order, **attrs)

    # ------------------------------------------------------------------
    # Build the <g> element for this viewport
    # ------------------------------------------------------------------

    def build(self, defs: ET.Element) -> ET.Element:
        """Build the viewport's <g> element with clip path and effects.

        Supports:
        - ``border_radius``: rounded corners on clip path and border
        - ``box_shadow``: drop-shadow filter behind the viewport
        - ``glow``: outer-glow filter behind the viewport

        Parameters
        ----------
        defs : ET.Element
            The document's <defs> element (clip paths are added here).

        Returns
        -------
        ET.Element
            The root <g> for this viewport.
        """
        from .effects import (
            BoxShadowConfig,
            GlowConfig,
            build_box_shadow_filter,
            build_glow_filter,
        )

        vb = self.viewbox
        clip_id = f"clip-{self.name}"

        # Clip and border use the content area (after aspect-ratio fitting)
        # so they match the geographic extent exactly
        cx, cy = vb.content_x, vb.content_y
        cw, ch = vb.content_width, vb.content_height
        rx = self.border_radius

        # Create clip path on content bounds (with optional rounding)
        clip = ET.SubElement(defs, "clipPath", id=clip_id)
        clip_rect = ET.SubElement(clip, "rect",
                                  x=f"{cx:.2f}", y=f"{cy:.2f}",
                                  width=f"{cw:.2f}", height=f"{ch:.2f}")
        if rx > 0:
            clip_rect.set("rx", f"{rx:.2f}")
            clip_rect.set("ry", f"{rx:.2f}")

        # Wrapper group (holds shadow/glow rect + clipped content)
        wrapper = ET.Element("g", id=f"{self.name}-wrapper")

        # ---- Box shadow (rendered behind the clipped content) ----
        shadow_cfg = BoxShadowConfig.from_param(self._box_shadow)
        if shadow_cfg is not None:
            fid = f"fx-shadow-{self.name}"
            build_box_shadow_filter(defs, fid, shadow_cfg)
            shadow_rect = ET.SubElement(wrapper, "rect",
                                        x=f"{cx:.2f}", y=f"{cy:.2f}",
                                        width=f"{cw:.2f}", height=f"{ch:.2f}",
                                        fill=D.DOCUMENT_BACKGROUND)
            shadow_rect.set("filter", f"url(#{fid})")
            if rx > 0:
                shadow_rect.set("rx", f"{rx:.2f}")
                shadow_rect.set("ry", f"{rx:.2f}")

        # ---- Glow (rendered behind the clipped content) ----
        glow_cfg = GlowConfig.from_param(self._glow)
        if glow_cfg is not None:
            fid = f"fx-glow-{self.name}"
            build_glow_filter(defs, fid, glow_cfg)
            glow_rect = ET.SubElement(wrapper, "rect",
                                      x=f"{cx:.2f}", y=f"{cy:.2f}",
                                      width=f"{cw:.2f}", height=f"{ch:.2f}",
                                      fill=D.DOCUMENT_BACKGROUND)
            glow_rect.set("filter", f"url(#{fid})")
            if rx > 0:
                glow_rect.set("rx", f"{rx:.2f}")
                glow_rect.set("ry", f"{rx:.2f}")

        # ---- Clipped content group ----
        root = ET.SubElement(wrapper, "g", id=self.name)
        root.set("clip-path", f"url(#{clip_id})")

        # Layers sorted by z-order
        for layer in sorted(self._layers.values(), key=lambda l: l.z_order):
            root.append(layer.element)

        # Optional border on content bounds
        if self.border:
            border_rect = ET.SubElement(root, "rect",
                                        x=f"{cx:.2f}", y=f"{cy:.2f}",
                                        width=f"{cw:.2f}", height=f"{ch:.2f}",
                                        fill="none", stroke=self.border_color)
            border_rect.set("stroke-width", str(self.border_width))
            if rx > 0:
                border_rect.set("rx", f"{rx:.2f}")
                border_rect.set("ry", f"{rx:.2f}")

        return wrapper


# ============================================================================
# SVG Document Builder
# ============================================================================

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


class SvgDocument:
    """Top-level SVG document managing viewports, layout, and serialization.

    Parameters
    ----------
    width : float
        Document width in pixels.
    height : float
        Document height in pixels.
    """

    def __init__(self, width: float, height: float):
        self.width = width
        self.height = height
        self._defs = ET.Element("defs")
        self._viewports: list[SvgViewport] = []
        self._overlay_layers: dict[str, SvgLayer] = {}  # for layout elements on top

    def add_viewport(self, viewport: SvgViewport) -> None:
        """Register a viewport."""
        self._viewports.append(viewport)
        # Invalidate build cache, viewport list changed
        if hasattr(self, "_built_viewports"):
            del self._built_viewports

    def add_def(self, element: ET.Element) -> None:
        """Add an element to the <defs> section."""
        self._defs.append(element)

    def add_radial_gradient(
        self,
        stops: list[tuple[float, str]],
        *,
        gradient_id: str | None = None,
        cx: float = 0.5,
        cy: float = 0.5,
        r: float = 0.5,
        fx: float | None = None,
        fy: float | None = None,
        units: str = "objectBoundingBox",
        spread: str = "pad",
    ) -> str:
        """Define a radial gradient in <defs> and return its element id.

        Parameters
        ----------
        stops : list of tuple
            Colour stops ordered from centre to edge. Each stop is
            ``(offset, color)`` or ``(offset, color, opacity)``. ``offset``
            is a fraction in ``[0, 1]``; ``opacity`` defaults to 1.0.
        gradient_id : str, optional
            Explicit element id. If omitted, a unique id is generated.
        cx, cy : float, default 0.5
            Centre of the gradient. In the default
            ``"objectBoundingBox"`` units these are fractions of the
            filled shape's bounding box.
        r : float, default 0.5
            Radius of the gradient.
        fx, fy : float, optional
            Focal point. Offsetting it from the centre fakes a lit
            surface (a highlight), which is what gives a flat disc the
            look of a sphere. Defaults to ``(cx, cy)``.
        units : str, default ``"objectBoundingBox"``
            ``"objectBoundingBox"`` (fractions of the shape) or
            ``"userSpaceOnUse"`` (absolute SVG coordinates).
        spread : str, default ``"pad"``
            ``spreadMethod``: ``"pad"``, ``"reflect"`` or ``"repeat"``.

        Returns
        -------
        str
            A ``"url(#id)"`` string to pass as a ``fill``.

        Examples
        --------
        .. code-block:: python

            url = doc.add_radial_gradient(
                [(0.0, "#bfe6ff"), (1.0, "#0b3a57")], fx=0.35, fy=0.35)
            # use url as a fill: fill=url
        """
        if gradient_id is None:
            self._gradient_counter = getattr(self, "_gradient_counter", 0) + 1
            gradient_id = f"radial-{self._gradient_counter}"

        grad = ET.SubElement(self._defs, "radialGradient", id=gradient_id)
        grad.set("cx", f"{cx}")
        grad.set("cy", f"{cy}")
        grad.set("r", f"{r}")
        grad.set("fx", f"{fx if fx is not None else cx}")
        grad.set("fy", f"{fy if fy is not None else cy}")
        grad.set("gradientUnits", units)
        grad.set("spreadMethod", spread)

        for stop in stops:
            offset, color = stop[0], stop[1]
            opacity = stop[2] if len(stop) > 2 else 1.0
            s = ET.SubElement(grad, "stop")
            s.set("offset", f"{offset}")
            s.set("stop-color", color)
            if opacity != 1.0:
                s.set("stop-opacity", f"{opacity}")

        return f"url(#{gradient_id})"

    # ------------------------------------------------------------------
    # Overlay layers (for elements that sit above all viewports: title, etc.)
    # ------------------------------------------------------------------

    def get_overlay_layer(self, name: str, z_order: int = 0) -> ET.Element:
        """Get or create a named overlay layer."""
        if name not in self._overlay_layers:
            self._overlay_layers[name] = SvgLayer(name=name, z_order=z_order)
        return self._overlay_layers[name].element

    def add_overlay_rect(self, layer: str, x: float, y: float, w: float, h: float,
                         z_order: int = 0, **attrs) -> ET.Element:
        group = self.get_overlay_layer(layer, z_order)
        elem = ET.SubElement(group, "rect", x=f"{x:.2f}", y=f"{y:.2f}",
                             width=f"{w:.2f}", height=f"{h:.2f}")
        _apply_attrs(elem, attrs)
        return elem

    def add_overlay_text(self, layer: str, x: float, y: float, text: str,
                         z_order: int = 0, **attrs) -> ET.Element:
        group = self.get_overlay_layer(layer, z_order)
        elem = ET.SubElement(group, "text", x=f"{x:.2f}", y=f"{y:.2f}")
        elem.text = text
        _apply_attrs(elem, attrs)
        return elem

    def add_overlay_line(self, layer: str, x1: float, y1: float,
                         x2: float, y2: float, z_order: int = 0,
                         **attrs) -> ET.Element:
        group = self.get_overlay_layer(layer, z_order)
        elem = ET.SubElement(group, "line",
                             x1=f"{x1:.2f}", y1=f"{y1:.2f}",
                             x2=f"{x2:.2f}", y2=f"{y2:.2f}")
        _apply_attrs(elem, attrs)
        return elem

    def add_overlay_group(self, layer: str, z_order: int = 0,
                          **attrs) -> ET.Element:
        group = self.get_overlay_layer(layer, z_order)
        sub = ET.SubElement(group, "g")
        _apply_attrs(sub, attrs)
        return sub

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _build_viewports(self) -> None:
        """Build all viewports once, caching the result.

        Subsequent calls to ``to_string()`` reuse the cached elements
        to avoid duplicating clip-paths and filters in ``<defs>``.
        """
        if not hasattr(self, "_built_viewports"):
            self._built_viewports = [
                vp.build(self._defs) for vp in self._viewports
            ]

    def expand_viewbox(self, left: float = 0, top: float = 0,
                       right: float = 0, bottom: float = 0) -> None:
        """Expand the SVG coordinate window to show content beyond initial bounds.

        Useful when cartouche viewports are positioned at negative SVG coordinates
        (left of the main map). Updates width/height/viewBox at serialization time.
        """
        self._vb_min_x = getattr(self, "_vb_min_x", 0) - left
        self._vb_min_y = getattr(self, "_vb_min_y", 0) - top
        self._vb_extra_w = getattr(self, "_vb_extra_w", 0) + left + right
        self._vb_extra_h = getattr(self, "_vb_extra_h", 0) + top + bottom

    def to_string(self) -> str:
        """Serialize the complete SVG document to a string.

        Overlay layers with negative z-order render BEFORE viewports
        (e.g. document background), positive z-order render AFTER
        (e.g. title, scale bar, source).
        """
        self._build_viewports()

        vb_x = getattr(self, "_vb_min_x", 0)
        vb_y = getattr(self, "_vb_min_y", 0)
        total_w = self.width + getattr(self, "_vb_extra_w", 0)
        total_h = self.height + getattr(self, "_vb_extra_h", 0)

        root = ET.Element("svg", xmlns=SVG_NS)
        root.set("xmlns:xlink", XLINK_NS)
        root.set("width", str(total_w))
        root.set("height", str(total_h))
        root.set("viewBox", f"{vb_x} {vb_y} {total_w} {total_h}")

        # Defs (clip paths, patterns, etc.)
        if len(self._defs):
            root.append(self._defs)

        # Background overlays (negative z-order), before viewports
        bg_layers = sorted(
            [l for l in self._overlay_layers.values() if l.z_order < 0],
            key=lambda l: l.z_order,
        )
        for layer in bg_layers:
            root.append(layer.element)

        # Viewports (cached from _build_viewports)
        for vp_element in self._built_viewports:
            root.append(vp_element)

        # Foreground overlays (non-negative z-order), title, scale bar, source
        fg_layers = sorted(
            [l for l in self._overlay_layers.values() if l.z_order >= 0],
            key=lambda l: l.z_order,
        )
        for layer in fg_layers:
            root.append(layer.element)

        ET.indent(root, space="  ")
        return ET.tostring(root, encoding="unicode", xml_declaration=True)

    def save(self, path: str) -> None:
        """Write SVG to a file."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_string())


# ============================================================================
# Helpers
# ============================================================================

def _apply_attrs(elem: ET.Element, attrs: dict[str, Any]) -> None:
    """Apply keyword attributes to an SVG element, converting Python names."""
    for key, value in attrs.items():
        if value is None:
            continue
        # Convert Python snake_case to SVG kebab-case
        svg_key = key.replace("_", "-")
        elem.set(svg_key, str(value))


def make_bbox_square(bbox: list[float]) -> list[float]:
    """Adjust a bounding box to be square by extending the shorter dimension."""
    minx, miny, maxx, maxy = bbox
    width = maxx - minx
    height = maxy - miny
    if width > height:
        diff = width - height
        miny -= diff / 2
        maxy += diff / 2
    else:
        diff = height - width
        minx -= diff / 2
        maxx += diff / 2
    return [minx, miny, maxx, maxy]
