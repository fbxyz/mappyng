"""
Automatic label placement for mappyng, simulated annealing, ported from d3-labeler.

Supports:
- Anti-overlap between labels (label-label energy)
- Obstacle avoidance (proportional symbols, markers, etc.)
- Chrome avoidance (title, scale bar, source)
- Leader lines when label is far from anchor
- Priority-based hiding when labels can't all fit
"""

import math
import random
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

import geopandas as gpd
import pandas as pd
from shapely.geometry import MultiPoint, Point
from shapely.geometry import box as shapely_box
from shapely.strtree import STRtree

# ============================================================================
# Position helpers
# ============================================================================

POSITIONS = ["NE", "E", "SE", "S", "SW", "W", "NW", "N"]

_POS_DX = {"NE": 1, "E": 1, "SE": 1, "S": 0, "SW": -1, "W": -1, "NW": -1, "N": 0}
_POS_DY = {"NE": -1, "E": 0, "SE": 1, "S": 1, "SW": 1, "W": 0, "NW": -1, "N": -1}


def estimate_text_bbox(text: str, font_size: float,
                       font_family: str = "sans-serif",
                       font_weight: str = "normal") -> tuple[float, float]:
    """Estimate text bounding box (width, height) without rendering."""
    coeff = 1.15 if font_weight in ("bold", "700", "800", "900") else 1.0
    width = font_size * 0.55 * coeff * len(text)
    height = font_size * 1.2
    return width, height


def _split_at_dash(text: str, max_chars: int) -> list[str]:
    """Split a label into max 2 lines at the dash nearest the middle.

    Returns a 1-element list if splitting is not needed or not possible.
    The dash is kept at the end of the first line (French typographic convention).

    Examples
    --------
    >>> _split_at_dash("HAUTS-DE-SEINE", 12)
    ['HAUTS-DE-', 'SEINE']
    >>> _split_at_dash("SEINE-ET-MARNE", 12)
    ['SEINE-ET-', 'MARNE']
    >>> _split_at_dash("PARIS", 12)
    ['PARIS']
    """
    if len(text) <= max_chars:
        return [text]
    dashes = [i for i, c in enumerate(text) if c == "-"]
    if not dashes:
        return [text]
    mid = len(text) / 2.0
    # Pick the dash closest to the middle
    best = min(dashes, key=lambda i: abs((i + 1) - mid))
    return [text[:best + 1], text[best + 1:]]


def _bbox_for_lines(lines: list[str], font_size: float,
                    font_family: str = "sans-serif",
                    font_weight: str = "normal") -> tuple[float, float]:
    """Bounding box for a multi-line label (max-width × stacked height)."""
    widths = [estimate_text_bbox(ln, font_size, font_family, font_weight)[0]
              for ln in lines]
    _, line_h = estimate_text_bbox("A", font_size, font_family, font_weight)
    return max(widths), line_h * len(lines)


LINE_HEIGHT_RATIO = 1.2   # SVG dy between baselines as multiple of font_size


def _place_label(ax: float, ay: float,
                 w: float, h: float,
                 pos: str, offset: float) -> tuple[float, float]:
    """Compute top-left (x,y) for a label at `pos` direction from anchor."""
    dx = _POS_DX[pos]
    dy = _POS_DY[pos]

    if pos in ("N", "S"):
        x = ax - w / 2
    elif dx > 0:
        x = ax + offset
    else:
        x = ax - offset - w

    if pos in ("E", "W"):
        y = ay - h / 2
    elif dy < 0:          # upward in SVG (N, NE, NW)
        y = ay - offset - h
    else:                 # downward in SVG (S, SE, SW)
        y = ay + offset

    return x, y


def _label_box(x: float, y: float, w: float, h: float):
    return shapely_box(x, y, x + w, y + h)


#: Distance (px) under which a symbol centre counts as the label anchor.
SYMBOL_ANCHOR_TOLERANCE = 1.0
#: Segments per quarter circle of the polygons standing for symbols.
SYMBOL_QUAD_SEGS = 4


def _symbol_radius_at(ax: float, ay: float,
                      symbols: Sequence[tuple[float, float, float]]) -> float:
    """Radius of the largest symbol centred on the anchor, or 0."""
    tol2 = SYMBOL_ANCHOR_TOLERANCE ** 2
    radii = [r for cx, cy, r in symbols
             if (cx - ax) ** 2 + (cy - ay) ** 2 <= tol2]
    return max(radii, default=0.0)


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class LabelConfig:
    """Label placement configuration for ``Label``.

    Parameters
    ----------
    font_size : float
        Label font size in SVG px (default 10.0).
    font_family : str
        Font family (default ``"sans-serif"``).
    font_weight : str
        Font weight (default ``"normal"``).
    color : str
        Label text color (default ``"#000000"``).
    halo_color : str or None
        Halo (text outline) color.  None disables the halo.
    halo_width : float
        Halo stroke width in SVG px (default 2.0).
    priority_col : str or None
        Column name used for priority ranking (higher value = placed first).
    min_priority : float or None
        Minimum priority threshold; rows below it are skipped.
    max_labels : int or None
        Hard cap on the number of labels placed.
    initial_position : str
        Starting candidate position (default ``"NE"``).
        One of: ``"NE"``, ``"E"``, ``"SE"``, ``"S"``, ``"SW"``, ``"W"``,
        ``"NW"``, ``"N"``.
    label_offset : float
        Distance from anchor point to label edge in SVG px (default 4.0).
    max_displacement : float
        Maximum distance (px) a label may be moved away from its initial
        position, measured between the label edge and the edge of the
        symbol at its anchor (default 40.0).
    avoid_overlap : bool
        Enable label-label overlap avoidance (default True).
    allow_hide : bool
        Allow labels to be hidden when they cannot be placed without overlap
        (default True).
    allow_symbol_overlap : bool
        With *allow_hide*, keep a label that still covers a map symbol
        (situation marker, proportional circle) after placement, instead
        of hiding it (default False).
    leader_lines : bool
        Draw leader lines when label is displaced beyond *leader_threshold*
        (default True).
    leader_threshold : float
        Minimum displacement (× label height) that triggers a leader line.
    wrap : bool
        Wrap long labels at dashes (default True).
    wrap_max_chars : int
        Max characters per line before wrapping (default 12).
    numbered_above : int or None
        Switch to numbered-circle mode when label count exceeds this value.
        None = always use text labels.
    n_sweeps : int
        Number of simulated-annealing sweeps (default 50).
    seed : int or None
        Random seed for reproducible placement (default 42).
    target : str
        Viewport to place labels on: ``"main"`` (default), ``"zoom"``, or
        ``"cartouche:<index>"``.
    """

    # Appearance
    font_size: float = 10.0
    font_family: str = "sans-serif"
    font_weight: str = "normal"
    color: str = "#000000"
    halo_color: str | None = "#ffffff"
    halo_width: float = 2.0
    # Priority / filtering
    priority_col: str | None = None
    min_priority: float | None = None
    max_labels: int | None = None
    # Placement
    initial_position: str = "NE"
    candidate_positions: list[str] = field(
        default_factory=lambda: ["NE", "E", "SE", "S", "SW", "W", "NW", "N"]
    )
    label_offset: float = 4.0
    max_displacement: float = 40.0
    # Anti-overlap
    avoid_overlap: bool = True
    allow_hide: bool = True
    allow_symbol_overlap: bool = False
    # Leader lines
    leader_lines: bool = True
    leader_threshold: float = 1.5
    leader_color: str = "#666666"
    leader_width: float = 0.5
    # Wrapping
    wrap: bool = True
    wrap_max_chars: int = 12
    # Numbered mode (auto-triggered when label count > numbered_above)
    numbered_above: int | None = None
    # Legend position: {"x": float, "y": float} in figure fractions (0-1),
    # where (0,0) = bottom-left and (1,1) = top-right, same convention as
    # other mappyng legend positions.  None = automatic (bottom-right,
    # aligned with the legend column).
    numbered_legend_position: dict | None = None
    # Circle appearance
    numbered_circle_r: float = 5.0
    numbered_circle_fill: str = "#ffffff"
    numbered_circle_stroke: str = "#333333"
    # Legend box style
    numbered_legend_bg: str = "white"
    numbered_legend_bg_opacity: float = 0.88
    numbered_legend_border: str = "#cccccc"
    numbered_legend_title: str | None = None
    # Simulated annealing
    n_sweeps: int = 50
    initial_temperature: float = 1.0
    final_temperature: float = 0.01
    seed: int | None = 42
    # Target viewport
    target: str = "main"
    # Energy weights
    w_LL: float = 30.0   # label-label
    w_LO: float = 25.0   # label-obstacle
    w_LC: float = 100.0  # label-chrome
    w_LA: float = 30.0   # label-anchor circle
    w_D: float = 1.0     # distance from anchor
    w_OR: float = 3.0    # orientation bias
    w_OOB: float = 1000.0  # out-of-bounds


# ============================================================================
# Label candidate
# ============================================================================

@dataclass
class LabelCandidate:
    text: str
    anchor_x: float
    anchor_y: float
    anchor_r: float     # radius of the anchor marker (px)
    width: float
    height: float
    x: float            # current top-left x (SVG px)
    y: float            # current top-left y (SVG px)
    pos: str            # current position name
    priority: float = 0.0
    visible: bool = True
    lines: list[str] = field(default_factory=list)  # 1 or 2 display lines
    symbol_r: float = 0.0  # radius of the symbol drawn at the anchor (px)


# ============================================================================
# Obstacle index
# ============================================================================

class ObstacleIndex:
    """Spatial index for obstacles using shapely STRtree (SVG pixel coords)."""

    def __init__(self, geoms: list[Any]):
        self._geoms = list(geoms)
        self._tree = STRtree(self._geoms) if self._geoms else None
        self._bounds = [g.bounds for g in self._geoms]

    def overlap_area_bounds(self, x1: float, y1: float,
                            x2: float, y2: float) -> float:
        """Same as :meth:`overlap_area` for the box ``(x1, y1, x2, y2)``.

        Most candidate positions touch no obstacle: a float test on the
        obstacle bounds settles those without building a geometry.
        """
        for bx1, by1, bx2, by2 in self._bounds:
            if x1 < bx2 and bx1 < x2 and y1 < by2 and by1 < y2:
                return self.overlap_area(shapely_box(x1, y1, x2, y2))
        return 0.0

    def overlap_area(self, label_box) -> float:
        if not self._tree:
            return 0.0
        area = 0.0
        for i in self._tree.query(label_box):
            inter = label_box.intersection(self._geoms[i])
            area += inter.area
        return area


# ============================================================================
# Label placer, simulated annealing
# ============================================================================

class LabelPlacer:
    """
    Simulated annealing label placer, adapted from d3-labeler (BSD).

    Energy function:
        E = w_LL * Σ label-label overlap
          + w_LO * Σ label-obstacle overlap
          + w_LC * Σ label-chrome overlap
          + w_LA * Σ label-anchor overlap
          + w_D  * distance(label_center, anchor)
          + w_OR * orientation_penalty
          + w_OOB * out_of_bounds_area
    """

    def __init__(self,
                 labels: list[LabelCandidate],
                 obstacle_index: ObstacleIndex,
                 chrome_boxes: list,
                 viewport_bbox: tuple[float, float, float, float],
                 config: LabelConfig,
                 rng: random.Random):
        self.labels = labels
        self.obs = obstacle_index
        self.chrome = chrome_boxes
        self.vbbox = viewport_bbox        # (x0, y0, x1, y1) SVG px
        self.cfg = config
        self.rng = rng
        self._vbox = shapely_box(*viewport_bbox)

    # ------------------------------------------------------------------
    # Fast float-only bbox overlap (avoids shapely for hot inner loop)
    # ------------------------------------------------------------------

    @staticmethod
    def _bb_overlap(ax1: float, ay1: float, ax2: float, ay2: float,
                    bx1: float, by1: float, bx2: float, by2: float) -> float:
        """Axis-aligned bbox intersection area, pure Python."""
        dx = min(ax2, bx2) - max(ax1, bx1)
        dy = min(ay2, by2) - max(ay1, by1)
        return dx * dy if dx > 0 and dy > 0 else 0.0

    def energy(self, i: int) -> float:
        cfg = self.cfg
        lab = self.labels[i]
        # Label bbox corners
        lx1, ly1 = lab.x, lab.y
        lx2, ly2 = lab.x + lab.width, lab.y + lab.height
        e = 0.0

        # Distance label-center to anchor
        cx = (lx1 + lx2) * 0.5
        cy = (ly1 + ly2) * 0.5
        e += cfg.w_D * math.sqrt((cx - lab.anchor_x) ** 2 + (cy - lab.anchor_y) ** 2)

        # Orientation bias
        if lab.pos != cfg.initial_position:
            e += cfg.w_OR

        bb = self._bb_overlap
        w_LL, w_LA = cfg.w_LL, cfg.w_LA

        # Label-label and label-anchor overlap (pure float, O(n)). This is
        # the hot loop of the annealing: the box intersection of
        # _bb_overlap is written out, and a pair that does not overlap
        # adds nothing.
        for other in self.labels:
            if other is not lab and other.visible:
                # label-label
                ox1 = other.x
                ox2 = ox1 + other.width
                dx = (lx2 if lx2 < ox2 else ox2) - (lx1 if lx1 > ox1 else ox1)
                if dx > 0:
                    oy1 = other.y
                    oy2 = oy1 + other.height
                    dy = ((ly2 if ly2 < oy2 else oy2)
                          - (ly1 if ly1 > oy1 else oy1))
                    if dy > 0:
                        e += w_LL * (dx * dy)
            # label-anchor for every anchor (including self)
            r = other.anchor_r
            ox1 = other.anchor_x - r
            ox2 = other.anchor_x + r
            dx = (lx2 if lx2 < ox2 else ox2) - (lx1 if lx1 > ox1 else ox1)
            if dx > 0:
                oy1 = other.anchor_y - r
                oy2 = other.anchor_y + r
                dy = (ly2 if ly2 < oy2 else oy2) - (ly1 if ly1 > oy1 else oy1)
                if dy > 0:
                    e += w_LA * (dx * dy)

        # Label-obstacle overlap (shapely STRtree, sparse)
        if cfg.avoid_overlap:
            e += cfg.w_LO * self.obs.overlap_area_bounds(lx1, ly1, lx2, ly2)

        # Label-chrome overlap (float arithmetic, typically few boxes)
        vx0, vy0, vx1, vy1 = self.vbbox
        for cbox in self.chrome:
            cb = cbox.bounds  # (minx, miny, maxx, maxy)
            e += cfg.w_LC * bb(lx1, ly1, lx2, ly2, cb[0], cb[1], cb[2], cb[3])

        # Out-of-bounds penalty (float arithmetic)
        oob_x = max(0.0, vx0 - lx1) + max(0.0, lx2 - vx1)
        oob_y = max(0.0, vy0 - ly1) + max(0.0, ly2 - vy1)
        if oob_x > 0 or oob_y > 0:
            clamp_w = max(0.0, lab.width - oob_x)
            clamp_h = max(0.0, lab.height - oob_y)
            oob_area = lab.width * lab.height - clamp_w * clamp_h
            e += cfg.w_OOB * oob_area

        return e

    def mcmove(self, T: float) -> None:
        rng = self.rng
        cfg = self.cfg
        n = len(self.labels)
        if n == 0:
            return
        i = rng.randint(0, n - 1)
        lab = self.labels[i]

        old_x, old_y = lab.x, lab.y
        old_E = self.energy(i)

        sigma = cfg.max_displacement * T
        lab.x += rng.gauss(0, sigma)
        lab.y += rng.gauss(0, sigma)

        # Reject if too far from the anchor. The distance runs from the
        # label edge to the edge of the anchor symbol: measured between
        # centres, a wide label or a large symbol would already be "too
        # far" at its initial position and could never move.
        gap_x = max(lab.x - lab.anchor_x, 0.0,
                    lab.anchor_x - (lab.x + lab.width))
        gap_y = max(lab.y - lab.anchor_y, 0.0,
                    lab.anchor_y - (lab.y + lab.height))
        gap = math.sqrt(gap_x ** 2 + gap_y ** 2) - lab.symbol_r
        if gap > cfg.max_displacement:
            lab.x, lab.y = old_x, old_y
            return

        new_E = self.energy(i)
        dE = new_E - old_E
        if dE >= 0 and rng.random() >= math.exp(-dE / max(T, 1e-10)):
            lab.x, lab.y = old_x, old_y

    def mcrotate(self, T: float) -> None:
        rng = self.rng
        cfg = self.cfg
        n = len(self.labels)
        if n == 0:
            return
        i = rng.randint(0, n - 1)
        lab = self.labels[i]

        old_x, old_y, old_pos = lab.x, lab.y, lab.pos
        old_E = self.energy(i)

        candidates = [p for p in cfg.candidate_positions if p != lab.pos]
        if not candidates:
            return
        new_pos = rng.choice(candidates)
        lab.x, lab.y = _place_label(
            lab.anchor_x, lab.anchor_y, lab.width, lab.height,
            new_pos, cfg.label_offset + lab.symbol_r,
        )
        lab.pos = new_pos

        new_E = self.energy(i)
        dE = new_E - old_E
        if dE >= 0 and rng.random() >= math.exp(-dE / max(T, 1e-10)):
            lab.x, lab.y, lab.pos = old_x, old_y, old_pos

    def run(self) -> list[LabelCandidate]:
        cfg = self.cfg
        if not self.labels:
            return self.labels

        n_iter = cfg.n_sweeps * len(self.labels)
        T0, Tf = cfg.initial_temperature, cfg.final_temperature

        for k in range(n_iter):
            T = T0 * (Tf / T0) ** (k / n_iter)
            if self.rng.random() < 0.5:
                self.mcmove(T)
            else:
                self.mcrotate(T)

        if cfg.avoid_overlap:
            self._snap_off_obstacles()
        if cfg.allow_hide:
            self._hide_colliding()

        return self.labels

    def _snap_off_obstacles(self) -> None:
        """Move labels that still cover an obstacle to a free position.

        Random moves can leave a label slightly over a symbol edge. Each
        such label is tried at every candidate position around its anchor
        and moved to the one with the lowest energy that covers no
        obstacle. Labels with no free position are left in place.
        """
        cfg = self.cfg
        for i, lab in enumerate(self.labels):
            lbox = _label_box(lab.x, lab.y, lab.width, lab.height)
            if self.obs.overlap_area(lbox) <= 0:
                continue
            original = (lab.x, lab.y, lab.pos)
            best = None
            for pos in cfg.candidate_positions:
                x, y = _place_label(lab.anchor_x, lab.anchor_y, lab.width,
                                    lab.height, pos,
                                    cfg.label_offset + lab.symbol_r)
                if self.obs.overlap_area(
                        _label_box(x, y, lab.width, lab.height)) > 0:
                    continue
                lab.x, lab.y, lab.pos = x, y, pos
                energy = self.energy(i)
                if best is None or energy < best[0]:
                    best = (energy, x, y, pos)
            if best is None:
                lab.x, lab.y, lab.pos = original
            else:
                _, lab.x, lab.y, lab.pos = best

    def _hide_colliding(self) -> None:
        """Greedy hide: keep highest-priority labels, hide conflicting lower ones.

        A label conflicts with a label already kept, or covers an obstacle
        (a map symbol, for instance).
        """
        order = sorted(range(len(self.labels)), key=lambda i: -self.labels[i].priority)
        accepted: list[int] = []
        for i in order:
            lab = self.labels[i]
            lbox = _label_box(lab.x, lab.y, lab.width, lab.height)
            if (self.cfg.avoid_overlap and not self.cfg.allow_symbol_overlap
                    and self.obs.overlap_area(lbox) > 0):
                lab.visible = False
                continue
            collides = any(
                lbox.intersects(_label_box(
                    self.labels[j].x, self.labels[j].y,
                    self.labels[j].width, self.labels[j].height,
                ))
                for j in accepted
            )
            if collides:
                lab.visible = False
            else:
                accepted.append(i)


# ============================================================================
# SVG emission
# ============================================================================

def _xml_escape(text: str) -> str:
    """Escape XML special characters."""
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))


def _add_text_content(elem: ET.Element, lines: list[str],
                      x: float, baseline_y: float, font_size: float) -> None:
    """Fill a <text> element with 1 or 2 lines using <tspan> for line 2."""
    if len(lines) == 1:
        elem.text = lines[0]
    else:
        # Line 1 as a tspan so line 2 can use dy
        ts1 = ET.SubElement(elem, "tspan")
        ts1.set("x", f"{x:.2f}")
        ts1.set("y", f"{baseline_y:.2f}")
        ts1.text = lines[0]
        ts2 = ET.SubElement(elem, "tspan")
        ts2.set("x", f"{x:.2f}")
        ts2.set("dy", f"{font_size * LINE_HEIGHT_RATIO:.2f}")
        ts2.text = lines[1]


def emit_labels_svg(labels: list[LabelCandidate],
                    config: LabelConfig,
                    layer_elem: ET.Element) -> None:
    """Append label SVG elements to an existing layer <g> element."""
    fs = config.font_size
    for lab in labels:
        if not lab.visible:
            continue

        lines = lab.lines if lab.lines else [lab.text]

        # Baseline of first line = top + font_size
        baseline_y = lab.y + fs
        cx = lab.x + lab.width / 2

        g = ET.SubElement(layer_elem, "g")
        g.set("class", "mappyng-label")
        g.set("data-priority", f"{lab.priority:.2f}")

        # Leader line (drawn first so it's under text). Distances are
        # measured from the edge of the symbol drawn at the anchor.
        dist = math.sqrt(
            (cx - lab.anchor_x) ** 2 + (baseline_y - lab.anchor_y) ** 2
        )
        gap = dist - lab.symbol_r
        if config.leader_lines and gap > config.leader_threshold * lab.height:
            start = lab.symbol_r / dist
            x1 = lab.anchor_x + (cx - lab.anchor_x) * start
            y1 = lab.anchor_y + (baseline_y - lab.anchor_y) * start
            line = ET.SubElement(g, "line")
            line.set("x1", f"{x1:.2f}")
            line.set("y1", f"{y1:.2f}")
            line.set("x2", f"{cx:.2f}")
            line.set("y2", f"{baseline_y:.2f}")
            line.set("stroke", config.leader_color)
            line.set("stroke-width", str(config.leader_width))

        text_attrs = {
            "font-family": config.font_family,
            "font-size": str(fs),
            "font-weight": config.font_weight,
        }

        # Halo
        if config.halo_color:
            th = ET.SubElement(g, "text")
            th.set("x", f"{lab.x:.2f}")
            th.set("y", f"{baseline_y:.2f}")
            for k, v in text_attrs.items():
                th.set(k, v)
            th.set("fill", "none")
            th.set("stroke", config.halo_color)
            th.set("stroke-width", str(config.halo_width))
            th.set("stroke-linejoin", "round")
            _add_text_content(th, lines, lab.x, baseline_y, fs)

        # Fill text
        t = ET.SubElement(g, "text")
        t.set("x", f"{lab.x:.2f}")
        t.set("y", f"{baseline_y:.2f}")
        for k, v in text_attrs.items():
            t.set(k, v)
        t.set("fill", config.color)
        _add_text_content(t, lines, lab.x, baseline_y, fs)


# ============================================================================
# Numbered mode emission
# ============================================================================

def _numbered_ranked(labels: list[LabelCandidate]) -> list[LabelCandidate]:
    """Return up to 10 labels sorted by priority descending."""
    return sorted(labels, key=lambda l: -l.priority)[:10]


def emit_numbered_circles(
    labels: list[LabelCandidate],
    config: LabelConfig,
    layer_elem: ET.Element,
) -> list[LabelCandidate]:
    """Emit numbered circles at anchor positions in *layer_elem*.

    Returns the ranked list (<= 10) so the caller can emit the matching legend.
    """
    ranked = _numbered_ranked(labels)
    r = config.numbered_circle_r
    fs_num = max(r * 1.1, config.font_size * 0.65)

    for n, lab in enumerate(ranked, start=1):
        g = ET.SubElement(layer_elem, "g")
        g.set("class", "mappyng-label-numbered")
        g.set("data-n", str(n))
        g.set("data-label", lab.text)  # ElementTree escapes attributes

        circ = ET.SubElement(g, "circle")
        circ.set("cx", f"{lab.anchor_x:.2f}")
        circ.set("cy", f"{lab.anchor_y:.2f}")
        circ.set("r", str(r))
        circ.set("fill", config.numbered_circle_fill)
        circ.set("stroke", config.numbered_circle_stroke)
        circ.set("stroke-width", "0.8")

        t = ET.SubElement(g, "text")
        t.set("x", f"{lab.anchor_x:.2f}")
        t.set("y", f"{lab.anchor_y + fs_num * 0.38:.2f}")
        t.set("text-anchor", "middle")
        t.set("font-size", f"{fs_num:.2f}")
        t.set("font-family", config.font_family)
        t.set("font-weight", "bold")
        t.set("fill", config.numbered_circle_stroke)
        t.text = str(n)

    return ranked


def numbered_legend_size(ranked: list[LabelCandidate],
                         config: LabelConfig) -> tuple[float, float]:
    """Return (width, height) in SVG px for the legend box."""
    r = config.numbered_circle_r
    pad = 4.0
    fs_leg = config.font_size
    line_h = fs_leg * 1.5
    title_h = fs_leg * 1.6 if config.numbered_legend_title else 0.0
    max_len = max((len(l.text) for l in ranked), default=4)
    w = r * 2 + pad * 3 + fs_leg * 0.55 * max_len
    h = len(ranked) * line_h + pad * 2 + title_h
    return w, h


def emit_numbered_legend(
    ranked: list[LabelCandidate],
    config: LabelConfig,
    lx: float,
    ly: float,
    layer_elem: ET.Element,
) -> None:
    """Emit the numbered key legend box at absolute SVG position (lx, ly).

    ``ranked`` must be the list returned by :func:`emit_numbered_circles`
    so numbers match 1-for-1.
    """
    r = config.numbered_circle_r
    fs_num = max(r * 1.1, config.font_size * 0.65)
    pad = 4.0
    fs_leg = config.font_size
    line_h = fs_leg * 1.5
    title_h = fs_leg * 1.6 if config.numbered_legend_title else 0.0

    legend_w, legend_h = numbered_legend_size(ranked, config)

    g_leg = ET.SubElement(layer_elem, "g")
    g_leg.set("class", "mappyng-label-legend-box")

    bg = ET.SubElement(g_leg, "rect")
    bg.set("x", f"{lx:.2f}")
    bg.set("y", f"{ly:.2f}")
    bg.set("width", f"{legend_w:.2f}")
    bg.set("height", f"{legend_h:.2f}")
    bg.set("fill", config.numbered_legend_bg)
    bg.set("fill-opacity", str(config.numbered_legend_bg_opacity))
    bg.set("rx", "2")
    bg.set("stroke", config.numbered_legend_border)
    bg.set("stroke-width", "0.5")

    # Optional title
    if config.numbered_legend_title:
        tt = ET.SubElement(g_leg, "text")
        tt.set("x", f"{lx + pad:.2f}")
        tt.set("y", f"{ly + pad + fs_leg * 0.85:.2f}")
        tt.set("font-size", f"{fs_leg:.2f}")
        tt.set("font-family", config.font_family)
        tt.set("font-weight", "bold")
        tt.set("fill", config.color)
        tt.text = config.numbered_legend_title

    for n, lab in enumerate(ranked, start=1):
        cy_row = ly + pad + title_h + (n - 0.5) * line_h
        baseline = cy_row + fs_leg * 0.38

        circ = ET.SubElement(g_leg, "circle")
        circ.set("cx", f"{lx + pad + r:.2f}")
        circ.set("cy", f"{cy_row:.2f}")
        circ.set("r", str(r))
        circ.set("fill", config.numbered_circle_fill)
        circ.set("stroke", config.numbered_circle_stroke)
        circ.set("stroke-width", "0.8")

        tn = ET.SubElement(g_leg, "text")
        tn.set("x", f"{lx + pad + r:.2f}")
        tn.set("y", f"{cy_row + fs_num * 0.38:.2f}")
        tn.set("text-anchor", "middle")
        tn.set("font-size", f"{fs_num:.2f}")
        tn.set("font-family", config.font_family)
        tn.set("font-weight", "bold")
        tn.set("fill", config.numbered_circle_stroke)
        tn.text = str(n)

        tname = ET.SubElement(g_leg, "text")
        tname.set("x", f"{lx + pad + r * 2 + pad:.2f}")
        tname.set("y", f"{baseline:.2f}")
        tname.set("font-size", f"{fs_leg:.2f}")
        tname.set("font-family", config.font_family)
        tname.set("font-weight", config.font_weight)
        tname.set("fill", config.color)
        tname.text = lab.text


def emit_numbered_svg(
    labels: list[LabelCandidate],
    config: LabelConfig,
    viewport_bbox: tuple[float, float, float, float],
    layer_elem: ET.Element,
    legend_layer: ET.Element | None = None,
    legend_xy: tuple[float, float] | None = None,
) -> None:
    """Emit numbered circles + legend box.

    If *legend_layer* and *legend_xy* are provided, the legend box is placed
    in that external layer (e.g. the main map layer, adjacent to the zoom
    window).  Otherwise it falls back to the same *layer_elem* with corner
    positioning inside *viewport_bbox*.
    """
    ranked = emit_numbered_circles(labels, config, layer_elem)

    if legend_layer is not None and legend_xy is not None:
        emit_numbered_legend(ranked, config, legend_xy[0], legend_xy[1], legend_layer)
    else:
        # Fallback: place inside the viewport (SE corner) when no external
        # layer is available (e.g. unit tests or main-viewport use).
        vx0, vy0, vx1, vy1 = viewport_bbox
        pad = 4.0
        legend_w, legend_h = numbered_legend_size(ranked, config)
        lx = max(vx0 + pad, vx1 - legend_w - pad * 2)
        ly = max(vy0 + pad, vy1 - legend_h - pad * 2)
        emit_numbered_legend(ranked, config, lx, ly, layer_elem)


# ============================================================================
# Public entry point (used by Map.add_labels)
# ============================================================================

def place_labels(
    gdf: gpd.GeoDataFrame,
    column: str,
    viewbox,           # mappyng ViewBox
    viewport,          # SvgViewport
    chrome_bboxes_svg: list[tuple[float, float, float, float]],
    config: LabelConfig,
    z_order: int = 40,
    legend_layer: ET.Element | None = None,
    legend_xy: tuple[float, float] | None = None,
    symbols: Sequence[tuple[float, float, float]] = (),
) -> None:
    """
    Place labels for a GeoDataFrame and emit SVG into `viewport`.

    Parameters
    ----------
    gdf : GeoDataFrame
        Features to label. Geometries should already be in the viewport CRS.
    column : str
        Column containing the label text.
    viewbox : ViewBox
        Coordinate transform for geo to SVG pixel conversion.
    viewport : SvgViewport
        Target viewport to emit SVG into.
    chrome_bboxes_svg : list of (x0,y0,x1,y1)
        Chrome element bounding boxes (title, scale bar...) in SVG px.
    config : LabelConfig
        All placement parameters.
    z_order : int
        Z-order for the label layer.
    symbols : sequence of (cx, cy, r)
        Point symbols drawn in the viewport (SVG px). Each is an obstacle,
        and a label whose anchor is the centre of symbols keeps its
        ``label_offset`` from the edge of the largest of them.
    """
    rng = random.Random(config.seed)

    # --- Build LabelCandidates ---
    labels: list[LabelCandidate] = []
    anchor_r = max(config.font_size * 0.3, 2.0)

    for _, row in gdf.iterrows():
        raw = row[column]
        # None, NaN, NaT and pd.NA all mean "no name": no label is drawn.
        if raw is None or (not isinstance(raw, str) and pd.isna(raw)):
            continue
        text = str(raw)
        if not text:
            continue

        geom = row.geometry
        if geom is None or geom.is_empty:
            continue

        # Anchor point: representative_point for robustness
        pt = geom.representative_point() if not isinstance(geom, (Point, MultiPoint)) else (
            geom if isinstance(geom, Point) else list(geom.geoms)[0]
        )
        if isinstance(pt, MultiPoint):
            pt = list(pt.geoms)[0]

        ax, ay = viewbox.geo_to_svg(pt.x, pt.y)

        # Priority
        priority = float(row[config.priority_col]) if (
            config.priority_col and config.priority_col in gdf.columns
        ) else 0.0
        if priority != priority:  # NaN: a missing priority ranks last
            priority = float("-inf")

        # Wrapping: split at dash if text too long
        if config.wrap:
            lines = _split_at_dash(text, config.wrap_max_chars)
        else:
            lines = [text]

        w, h = _bbox_for_lines(lines, config.font_size,
                               config.font_family, config.font_weight)
        symbol_r = _symbol_radius_at(ax, ay, symbols)
        ix, iy = _place_label(ax, ay, w, h, config.initial_position,
                              config.label_offset + symbol_r)

        labels.append(LabelCandidate(
            text=text,
            anchor_x=ax, anchor_y=ay, anchor_r=max(anchor_r, symbol_r),
            width=w, height=h,
            x=ix, y=iy,
            pos=config.initial_position,
            priority=priority,
            visible=True,
            lines=lines,
            symbol_r=symbol_r,
        ))

    if not labels:
        return

    # --- Filter by priority ---
    if config.min_priority is not None:
        labels = [l for l in labels if l.priority >= config.min_priority]
    if config.max_labels is not None:
        labels = sorted(labels, key=lambda l: -l.priority)[:config.max_labels]

    # --- Viewport bounds ---
    vb = viewbox
    viewport_bbox = (
        vb.content_x, vb.content_y,
        vb.content_x + vb.content_width,
        vb.content_y + vb.content_height,
    )

    layer = viewport.get_layer("labels", z_order=z_order)

    # --- Numbered mode: skip annealing when too many labels ---
    if config.numbered_above is not None and len(labels) > config.numbered_above:
        emit_numbered_svg(labels, config, viewport_bbox, layer,
                          legend_layer=legend_layer, legend_xy=legend_xy)
        return

    # --- Obstacle index (SVG px) ---
    chrome_shapes = [shapely_box(*bb) for bb in chrome_bboxes_svg]
    # Polygons circumscribed to the symbol discs, so they cover them fully.
    grow = 1.0 / math.cos(math.pi / (4 * SYMBOL_QUAD_SEGS))
    symbol_geoms = [Point(cx, cy).buffer(r * grow, quad_segs=SYMBOL_QUAD_SEGS)
                    for cx, cy, r in symbols]
    obs_idx = ObstacleIndex(symbol_geoms)

    # --- Run annealing ---
    placer = LabelPlacer(
        labels=labels,
        obstacle_index=obs_idx,
        chrome_boxes=chrome_shapes,
        viewport_bbox=viewport_bbox,
        config=config,
        rng=rng,
    )
    placed = placer.run()

    # --- Emit SVG ---
    emit_labels_svg(placed, config, layer)
