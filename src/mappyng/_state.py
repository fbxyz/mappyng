"""Internal mutable state container for Map.

Groups all state accumulated during add_* calls. Structural state
(viewports, bbox, dimensions) stays on Map itself.

"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .overflow import OverflowRegistry


@dataclass
class MapState:
    """Mutable state accumulated while building a Map.

    Parameters
    ----------
    overflow : OverflowRegistry
        Registry of bounding boxes that may overflow the viewBox
        (legends, cartouches) so the canvas can be expanded.
    interactive_layers : list of dict
        Metadata for interactive layers (type, gdf, column,
        layer_id, id_prefix) used to attach tooltips.
    chrome_bboxes : list of tuple
        Bounding boxes (x0, y0, x1, y1) in SVG px of chrome elements
        (title, scale bar...) for label avoidance.
    layer_counters : dict of str to int
        Per-kind monotonic counters for unique layer ids
        (see Map._next_layer_id).
    layers : list of Layer
        First-class Layer objects registered via Map.add, rendered
        (in z_index order) when the map is built.
    chrome : dict
        Parameters of the chrome elements (title, source, scale bar,
        north arrow), keyed by element name. Drawn when the map is
        built, and serialised.
    classification_reports : dict of int to ClassificationReport
        What each Choropleth layer actually did (method, bounds, class
        sizes, excluded values, adjustments), keyed by layer id.
    """

    overflow: OverflowRegistry = field(default_factory=OverflowRegistry)
    interactive_layers: list[dict[str, Any]] = field(default_factory=list)
    chrome_bboxes: list[tuple[float, float, float, float]] = field(
        default_factory=list
    )
    layer_counters: dict[str, int] = field(default_factory=dict)
    layers: list[Any] = field(default_factory=list)
    chrome: dict[str, Any] = field(default_factory=dict)
    classification_reports: dict[int, Any] = field(default_factory=dict)
