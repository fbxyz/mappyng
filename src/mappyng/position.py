"""Placement of map elements (scale bar, north arrow, source, title, legends).

Every element that accepts a ``position`` resolves it through
:func:`resolve_position`, so all of them understand the same forms.

Forms accepted by ``position``
------------------------------
Relative to the map content area (0, 0 is the top-left corner of the map,
1, 1 the bottom-right; values outside ``[0, 1]`` place the element outside
the map):

* ``(0.46, 0.9)`` or ``{"x": 0.46, "y": 0.9}``: fractions.
* ``("46%", "90%")`` or ``{"x": "46%", "y": "90%"}``: the same, as percentages.

Absolute:

* ``{"px": 120, "py": 80}``: SVG pixels.

Geographic (the element is anchored at a point of the map):

* ``{"geo": (x, y)}``: coordinates in the map CRS (for a Lambert-93 map,
  metres in EPSG:2154).
* ``{"geo": (x, y), "crs": "EPSG:4326"}``: coordinates in another CRS,
  reprojected to the map CRS.
* ``{"lon": 4.2, "lat": 42.6}``: shorthand for WGS 84 longitude/latitude.

What the point designates depends on the element: the left end of the scale
bar, the tip of the north arrow, the start of the source text, the baseline
of the last title line, the top-left corner of a legend.
"""

from __future__ import annotations

import math
from typing import Any

from .errors import LayoutError


def _fraction(value: Any, name: str) -> float:
    """Parse a fraction given as a number or a ``"NN%"`` string."""
    if isinstance(value, str):
        text = value.strip()
        try:
            if text.endswith("%"):
                return float(text[:-1]) / 100.0
            return float(text)
        except ValueError:
            pass
        raise LayoutError(
            f"Invalid position {name}={value!r}: expected a number or a "
            f"percentage such as '40%'."
        )
    try:
        return float(value)
    except (TypeError, ValueError):
        raise LayoutError(
            f"Invalid position {name}={value!r}: expected a number or a "
            f"percentage such as '40%'."
        ) from None


def _geo_to_svg(x: float, y: float, source_crs: Any, vb: Any) -> tuple[float, float]:
    """Project a point from *source_crs* (None = map CRS) to SVG pixels."""
    map_crs = getattr(vb, "crs", None)
    if source_crs is not None:
        if map_crs is None:
            raise LayoutError(
                "Cannot place an element from coordinates in a given CRS: "
                "the map data has no CRS. Set one on the GeoDataFrame, or use "
                "fractions or pixels."
            )
        from pyproj import CRS, Transformer
        try:
            if CRS.from_user_input(source_crs) != CRS.from_user_input(map_crs):
                transformer = Transformer.from_crs(
                    source_crs, map_crs, always_xy=True)
                x, y = transformer.transform(x, y)
        except Exception as e:  # pyproj raises several unrelated types
            raise LayoutError(
                f"Cannot reproject the position from {source_crs!r} to the "
                f"map CRS: {e}"
            ) from e
    if not (math.isfinite(x) and math.isfinite(y)):
        raise LayoutError(
            "The position falls outside the area the map projection can "
            "represent (for example the hidden side of a globe)."
        )
    return vb.geo_to_svg(x, y)


def resolve_position(position: Any, vb: Any) -> tuple[float, float] | None:
    """Resolve a ``position`` parameter to SVG pixel coordinates.

    Parameters
    ----------
    position : None, tuple, list or dict
        See the module docstring for the accepted forms.
    vb : ViewBox
        Viewbox of the target viewport. Its ``crs`` is used for geographic
        positions.

    Returns
    -------
    (x, y) : tuple of float, or None
        SVG pixel coordinates, or None when *position* is None.

    Raises
    ------
    LayoutError
        If *position* is malformed or cannot be projected.
    """
    if position is None:
        return None

    if isinstance(position, (list, tuple)):
        if len(position) != 2:
            raise LayoutError(
                f"Invalid position {position!r}: expected an (x, y) pair."
            )
        xf = _fraction(position[0], "x")
        yf = _fraction(position[1], "y")
        return (vb.content_x + xf * vb.content_width,
                vb.content_y + yf * vb.content_height)

    if not isinstance(position, dict):
        raise LayoutError(
            f"Invalid position {position!r}: expected an (x, y) pair or a "
            f"dict such as {{'x': 0.5, 'y': 0.9}}."
        )

    if "geo" in position:
        pair = position["geo"]
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise LayoutError(
                f"Invalid position geo={pair!r}: expected an (x, y) pair."
            )
        return _geo_to_svg(float(pair[0]), float(pair[1]),
                           position.get("crs"), vb)

    if "lon" in position or "lat" in position:
        if "lon" not in position or "lat" not in position:
            raise LayoutError(
                "A geographic position needs both 'lon' and 'lat'."
            )
        return _geo_to_svg(float(position["lon"]), float(position["lat"]),
                           "EPSG:4326", vb)

    if "px" in position or "py" in position:
        return (position.get("px", vb.content_x),
                position.get("py", vb.content_y))

    xf = _fraction(position.get("x", 0.0), "x")
    yf = _fraction(position.get("y", 0.0), "y")
    return (vb.content_x + xf * vb.content_width,
            vb.content_y + yf * vb.content_height)
