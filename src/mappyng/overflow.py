"""
overflow.py, SVG bounds checking and auto-expansion for mappyng.

Elements rendered outside the initial SVG viewport (legends below the map,
cartouches to the left, wide scale bars, etc.) would be clipped by default.
This module provides a registry where renderers declare their bounding boxes,
and a resolution step that expands the SVG viewBox to fit all declared content.

Usage (inside map.py)::

    # During rendering, declare an element's bounding box:
    map_obj.overflow.register(x0, y0, x1, y1)

    # Before serialization, resolve and expand:
    map_obj.overflow.resolve(map_obj)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass  # avoid circular import; Map is referenced only at runtime


@dataclass
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float


class OverflowRegistry:
    """Collects element bounding boxes and expands the SVG viewBox as needed."""

    def __init__(self) -> None:
        self._boxes: list[BBox] = []

    def register(self, x0: float, y0: float, x1: float, y1: float) -> None:
        """Declare a rendered element's SVG bounding box (in SVG user units)."""
        if x0 < x1 and y0 < y1:
            self._boxes.append(BBox(x0, y0, x1, y1))

    # Extra padding added on each side when overflow is detected, to compensate
    # for font-metrics estimation errors (actual text can be slightly wider than
    # the char-count × em-width heuristic).
    PADDING = 15.0

    def resolve(self, map_obj) -> None:
        """Expand map_obj.svg viewBox to contain all registered bounding boxes.

        Also extends the background rect if the document has one.
        """
        if not self._boxes:
            return

        min_x = min(b.x0 for b in self._boxes)
        min_y = min(b.y0 for b in self._boxes)
        max_x = max(b.x1 for b in self._boxes)
        max_y = max(b.y1 for b in self._boxes)

        def _pad(raw: float) -> float:
            return (raw + self.PADDING) if raw > 0 else 0.0

        overflow_left   = _pad(-min_x)
        overflow_top    = _pad(-min_y)
        overflow_right  = _pad(max_x - map_obj.width)
        overflow_bottom = _pad(max_y - map_obj.height)

        if not any(v > 0 for v in (overflow_left, overflow_top, overflow_right, overflow_bottom)):
            return

        map_obj.svg.expand_viewbox(overflow_left, overflow_top, overflow_right, overflow_bottom)
        _extend_background(map_obj, overflow_left, overflow_top, overflow_right, overflow_bottom)

    def clear(self) -> None:
        self._boxes.clear()


def _extend_background(map_obj, left: float, top: float, right: float, bottom: float) -> None:
    """Resize the background rect to cover the expanded viewBox."""
    bg_layer = map_obj.svg._overlay_layers.get("background")
    if bg_layer is None:
        return
    for child in bg_layer.element:
        if child.tag == "rect" or child.tag.endswith("}rect"):
            new_x = float(child.get("x", 0)) - left
            new_y = float(child.get("y", 0)) - top
            new_w = float(child.get("width", map_obj.width)) + left + right
            new_h = float(child.get("height", map_obj.height)) + top + bottom
            child.set("x", str(new_x))
            child.set("y", str(new_y))
            child.set("width", str(new_w))
            child.set("height", str(new_h))
