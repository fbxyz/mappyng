"""Contrast of the borders shared by touching areas of a choropleth.

Where two neighbouring areas have similar fill colours (two light ones, or two
dark ones) and the outline is too close to them in tone, the border between
them disappears. This module finds those shared borders and redraws **only
them**, in a colour that stands out, on top of the polygons: the polygons keep
their own outline.

A shared border is *weak* when both

* its two fills are close in tone (contrast ratio below ``fill_ratio``), so the
  colour change itself does not show the border, and
* the outline colour is close to at least one of the fills (contrast ratio
  below ``stroke_ratio``), so the outline does not show it either.

Contrast is the WCAG contrast ratio of the relative luminances, from 1 (same
tone) to 21 (black on white).
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

import numpy as np
import shapely

from .config import parse_color

#: Layer name of the redrawn borders in the SVG.
BORDER_LAYER = "choropleth_borders"

@dataclass
class BorderContrast:
    """Settings of the border contrast check.

    Passed as the ``border_contrast`` parameter of
    :class:`~mappyng.Choropleth` and :class:`~mappyng.Category`, or built from
    ``True``, ``"fix"``, ``"check"`` or a dict of these fields.

    Parameters
    ----------
    mode : str
        ``"fix"`` (default) redraws the weak borders in a contrasting colour.
        ``"check"`` only reveals them: they are drawn thick in *check_color* and
        a warning reports how many there are and between which areas.
    fill_ratio : float
        Two fills whose contrast ratio is **below** this value are considered
        alike (default 1.5): the colour change alone does not show the border.
    stroke_ratio : float
        An outline whose contrast ratio with a fill is **below** this value does
        not show against it (default 2.0).
    light, dark : str
        The two colours tried for a weak border. The one that contrasts most with
        the two fills is used, provided it improves on the current outline.
    check_color : str
        Colour of the weak borders in ``"check"`` mode (default magenta).
    width_factor : float
        Width of a redrawn border relative to the outline width (default 1.0).
    """

    mode: str = "fix"
    fill_ratio: float = 1.5
    stroke_ratio: float = 2.0
    light: str = "#ffffff"
    dark: str = "#222222"
    check_color: str = "#ff00ff"
    width_factor: float = 1.0

    def __post_init__(self) -> None:
        if self.mode not in ("fix", "check"):
            raise ValueError(
                f"border_contrast mode must be 'fix' or 'check', got "
                f"{self.mode!r}."
            )
        for name in ("fill_ratio", "stroke_ratio", "width_factor"):
            if not getattr(self, name) > 0:
                raise ValueError(
                    f"border_contrast {name} must be positive, got "
                    f"{getattr(self, name)!r}."
                )
        for name in ("light", "dark", "check_color"):
            if _rgb(getattr(self, name)) is None:
                raise ValueError(
                    f"border_contrast {name} must be a visible colour, got "
                    f"{getattr(self, name)!r}."
                )

    def to_dict(self) -> dict[str, Any]:
        """Return the settings as a plain dict."""
        return dataclasses.asdict(self)


def parse_border_contrast(value: Any) -> BorderContrast | None:
    """Turn a ``border_contrast`` parameter into a :class:`BorderContrast`.

    ``None`` and ``False`` disable the check; ``True`` and ``"fix"`` use the
    defaults; ``"check"`` reveals the weak borders; a dict sets any field.
    """
    if value is None or value is False:
        return None
    if value is True:
        return BorderContrast()
    if isinstance(value, BorderContrast):
        return dataclasses.replace(value)
    if isinstance(value, str):
        return BorderContrast(mode=value)
    if isinstance(value, dict):
        known = {f.name for f in dataclasses.fields(BorderContrast)}
        unknown = set(value) - known
        if unknown:
            raise ValueError(
                f"border_contrast: unknown option(s) {sorted(unknown)}. "
                f"Available: {sorted(known)}."
            )
        return BorderContrast(**value)
    raise ValueError(
        f"border_contrast must be True, 'fix', 'check', a dict or a "
        f"BorderContrast, got {value!r}."
    )


# ---------------------------------------------------------------------------
# Colour maths
# ---------------------------------------------------------------------------

def _rgb(color: str | None) -> tuple[int, int, int] | None:
    """Parse a colour; ``None`` for no colour ("none", "transparent", None)."""
    try:
        return parse_color(color)
    except ValueError as e:
        raise ValueError(f"border_contrast: {e}") from None


def luminance(color: str) -> float:
    """WCAG relative luminance of *color*, from 0 (black) to 1 (white)."""
    rgb = _rgb(color)
    if rgb is None:
        raise ValueError(f"luminance: {color!r} is not a colour.")
    lin = [(c / 255 / 12.92) if c / 255 <= 0.03928
           else ((c / 255 + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contrast_ratio(l1: float, l2: float) -> float:
    """WCAG contrast ratio of two relative luminances (1 to 21)."""
    hi, lo = (l1, l2) if l1 >= l2 else (l2, l1)
    return (hi + 0.05) / (lo + 0.05)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

@dataclass
class WeakBorder:
    """A border shared by two areas that needs a more visible colour.

    Parameters
    ----------
    i, j : int
        Positions of the two areas in the geometries given to
        :func:`find_weak_borders`.
    geometry : shapely geometry
        The shared border (line or multi-line).
    color : str
        Colour proposed for it.
    """

    i: int
    j: int
    geometry: Any
    color: str


def _shared_lines(geom: Any) -> Any:
    """The linear part of an intersection of two boundaries, or None."""
    if geom is None or geom.is_empty:
        return None
    lines = [p for p in shapely.get_parts(geom)
             if p.geom_type in ("LineString", "LinearRing") and p.length > 0]
    if not lines:
        return None
    return shapely.line_merge(shapely.multilinestrings(
        [np.asarray(line.coords) for line in lines]))


def find_weak_borders(geometries: Any, fills: list[str], stroke: str | None,
                      cfg: BorderContrast) -> list[WeakBorder]:
    """Find the shared borders that the outline does not make visible.

    Parameters
    ----------
    geometries : GeoSeries or array of shapely geometries
        The areas, in the same order as *fills*.
    fills : list of str
        Fill colour of each area.
    stroke : str or None
        Outline colour of the areas (``None`` or ``"none"``: no outline).
    cfg : BorderContrast
        Thresholds and candidate colours.

    Returns
    -------
    list of WeakBorder
        One entry per weak border between two touching areas that share a
        stretch of border of non-zero length. In ``"check"`` mode the colour is
        ``cfg.check_color``.
    """
    n = len(fills)
    if n < 2:
        return []
    geoms = np.asarray(getattr(geometries, "values", geometries), dtype=object)
    lum = [luminance(f) for f in fills]
    stroke_lum = (luminance(stroke)
                  if stroke is not None and _rgb(stroke) is not None else None)
    cand = [(c, luminance(c)) for c in (cfg.light, cfg.dark)]

    tree = shapely.STRtree(geoms)
    a, b = tree.query(geoms, predicate="intersects")
    keep = a < b
    a, b = a[keep], b[keep]

    weak: list[tuple[int, int, str]] = []
    for i, j in zip(a.tolist(), b.tolist()):
        if contrast_ratio(lum[i], lum[j]) >= cfg.fill_ratio:
            continue
        current = (1.0 if stroke_lum is None else
                   min(contrast_ratio(stroke_lum, lum[i]),
                       contrast_ratio(stroke_lum, lum[j])))
        if current >= cfg.stroke_ratio:
            continue
        color, best = max(
            ((c, min(contrast_ratio(cl, lum[i]), contrast_ratio(cl, lum[j])))
             for c, cl in cand), key=lambda t: t[1])
        if best <= current:
            continue  # neither candidate would show better than the outline
        weak.append((i, j, color))
    if not weak:
        return []

    idx = np.array([(i, j) for i, j, _ in weak])
    boundaries = {k: shapely.boundary(geoms[k]) for k in np.unique(idx)}
    inter = shapely.intersection([boundaries[i] for i in idx[:, 0]],
                                 [boundaries[j] for j in idx[:, 1]])
    out = []
    for (i, j, color), geom in zip(weak, inter):
        lines = _shared_lines(geom)
        if lines is not None:
            out.append(WeakBorder(
                i, j, lines,
                cfg.check_color if cfg.mode == "check" else color))
    return out


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def draw_weak_borders(viewport: Any, borders: list[WeakBorder], *,
                      stroke_width: float, z_order: int, cfg: BorderContrast,
                      tolerance: float | None = None) -> None:
    """Draw the weak borders on *viewport*, one path set per colour.

    The paths sit above the polygons and ignore the pointer, so hover
    tooltips still reach the areas underneath.
    """
    from .renderer import geometry_to_paths

    by_color: dict[str, list[Any]] = defaultdict(list)
    for border in borders:
        by_color[border.color].append(border.geometry)
    width = (stroke_width * 3 if cfg.mode == "check"
             else stroke_width * cfg.width_factor)
    for color, geoms in by_color.items():
        merged = shapely.line_merge(shapely.union_all(geoms))
        if tolerance:
            merged = merged.simplify(tolerance)
        for d in geometry_to_paths(merged, viewport.viewbox):
            viewport.add_path(
                BORDER_LAYER, d, z_order=z_order,
                fill="none", stroke=color, stroke_width=width,
                stroke_linecap="round", stroke_linejoin="round",
                **{"class": "choropleth-border", "pointer-events": "none"},
            )


def report_weak_borders(borders: list[WeakBorder], labels: Any,
                        layer: str) -> str:
    """One-line summary of the weak borders, naming the first few pairs."""
    pairs = [f"{labels[b.i]!s}/{labels[b.j]!s}" for b in borders[:5]]
    more = f" and {len(borders) - 5} more" if len(borders) > 5 else ""
    return (
        f"{layer}: {len(borders)} border(s) between areas of similar colour "
        f"are hard to see with the current outline (e.g. "
        f"{', '.join(pairs)}{more}). They are drawn thick in the check colour. "
        f"Use border_contrast=True to redraw them in a contrasting colour."
    )
