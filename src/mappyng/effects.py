"""
SVG visual effects for mappyng.

Reusable building blocks for decorative effects on map elements:
- Rounded corners (border-radius on clip paths and borders)
- Box shadows (drop-shadow filter on viewports/groups)
- Glow effects
- Gradient fills

All defaults are imported from :mod:`mappyng.defaults`.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any

from . import defaults as D

# ============================================================================
# Effect configuration
# ============================================================================

@dataclass
class BoxShadowConfig:
    """Drop-shadow configuration for a viewport or element.

    Can be created from a dict, a bool (``True`` for defaults), or directly.

    Parameters
    ----------
    dx : float
        Horizontal shadow offset in SVG px.
    dy : float
        Vertical shadow offset in SVG px.
    blur : float
        Shadow blur radius in SVG px.
    color : str
        Shadow color.
    opacity : float
        Shadow opacity 0-1.
    """
    dx: float = D.BOX_SHADOW_DX
    dy: float = D.BOX_SHADOW_DY
    blur: float = D.BOX_SHADOW_BLUR
    color: str = D.BOX_SHADOW_COLOR
    opacity: float = D.BOX_SHADOW_OPACITY

    @classmethod
    def from_param(cls, value: bool | dict[str, Any] | BoxShadowConfig | None
                   ) -> BoxShadowConfig | None:
        """Parse user input into a BoxShadowConfig or None.

        - ``None`` / ``False``: None (no shadow)
        - ``True``: default shadow
        - ``dict``: shadow with overrides
        - ``BoxShadowConfig``: passed through
        """
        if value is None or value is False:
            return None
        if value is True:
            return cls()
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls(**value)
        raise TypeError(f"Expected bool, dict, or BoxShadowConfig, got {type(value)}")


@dataclass
class GlowConfig:
    """Outer glow configuration for a viewport or element.

    Parameters
    ----------
    blur : float
        Glow blur radius in SVG px.
    color : str
        Glow color.
    opacity : float
        Glow opacity 0-1.
    """
    blur: float = D.GLOW_BLUR
    color: str = D.GLOW_COLOR
    opacity: float = D.GLOW_OPACITY

    @classmethod
    def from_param(cls, value: bool | dict[str, Any] | GlowConfig | None
                   ) -> GlowConfig | None:
        if value is None or value is False:
            return None
        if value is True:
            return cls()
        if isinstance(value, cls):
            return value
        if isinstance(value, dict):
            return cls(**value)
        raise TypeError(f"Expected bool, dict, or GlowConfig, got {type(value)}")


# ============================================================================
# SVG filter builders
# ============================================================================

def build_box_shadow_filter(
    defs: ET.Element,
    filter_id: str,
    config: BoxShadowConfig,
) -> None:
    """Create a box-shadow ``<filter>`` in *defs*.

    The filter renders a colored, blurred, offset shadow *behind* the
    source graphic (using ``feMerge``).

    Parameters
    ----------
    defs : ET.Element
        Document ``<defs>`` to append the filter to.
    filter_id : str
        Unique filter id (e.g. ``"box-shadow-cartouche_0"``).
    config : BoxShadowConfig
        Shadow parameters.
    """
    margin = D.BOX_SHADOW_FILTER_MARGIN
    filt = ET.SubElement(defs, "filter", id=filter_id)
    filt.set("x", f"-{margin}%")
    filt.set("y", f"-{margin}%")
    filt.set("width", f"{100 + 2 * margin}%")
    filt.set("height", f"{100 + 2 * margin}%")

    # 1. Blur source alpha
    blur = ET.SubElement(filt, "feGaussianBlur")
    blur.set("in", "SourceAlpha")
    blur.set("stdDeviation", str(config.blur))
    blur.set("result", "blur")

    # 2. Offset
    offset = ET.SubElement(filt, "feOffset")
    offset.set("in", "blur")
    offset.set("dx", str(config.dx))
    offset.set("dy", str(config.dy))
    offset.set("result", "offsetBlur")

    # 3. Flood with color + opacity
    flood = ET.SubElement(filt, "feFlood")
    flood.set("flood-color", config.color)
    flood.set("flood-opacity", str(config.opacity))
    flood.set("result", "shadowColor")

    # 4. Clip flood to blurred shape
    comp = ET.SubElement(filt, "feComposite")
    comp.set("in", "shadowColor")
    comp.set("in2", "offsetBlur")
    comp.set("operator", "in")
    comp.set("result", "shadow")

    # 5. Merge: shadow first, then source on top
    merge = ET.SubElement(filt, "feMerge")
    ET.SubElement(merge, "feMergeNode").set("in", "shadow")
    ET.SubElement(merge, "feMergeNode").set("in", "SourceGraphic")


def build_glow_filter(
    defs: ET.Element,
    filter_id: str,
    config: GlowConfig,
) -> None:
    """Create an outer-glow ``<filter>`` in *defs*.

    Parameters
    ----------
    defs : ET.Element
        Document ``<defs>``.
    filter_id : str
        Unique filter id.
    config : GlowConfig
        Glow parameters.
    """
    margin = D.GLOW_FILTER_MARGIN
    filt = ET.SubElement(defs, "filter", id=filter_id)
    filt.set("x", f"-{margin}%")
    filt.set("y", f"-{margin}%")
    filt.set("width", f"{100 + 2 * margin}%")
    filt.set("height", f"{100 + 2 * margin}%")

    # Blur the source alpha
    blur = ET.SubElement(filt, "feGaussianBlur")
    blur.set("in", "SourceAlpha")
    blur.set("stdDeviation", str(config.blur))
    blur.set("result", "blur")

    # Flood with glow color
    flood = ET.SubElement(filt, "feFlood")
    flood.set("flood-color", config.color)
    flood.set("flood-opacity", str(config.opacity))
    flood.set("result", "glowColor")

    # Clip to blurred shape
    comp = ET.SubElement(filt, "feComposite")
    comp.set("in", "glowColor")
    comp.set("in2", "blur")
    comp.set("operator", "in")
    comp.set("result", "glow")

    # Merge: glow behind, then source
    merge = ET.SubElement(filt, "feMerge")
    ET.SubElement(merge, "feMergeNode").set("in", "glow")
    ET.SubElement(merge, "feMergeNode").set("in", "SourceGraphic")
