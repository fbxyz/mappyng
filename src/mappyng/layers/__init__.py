"""First-class map layers.

A layer describes an intent and renders itself through a
:class:`RenderContext`.
"""

from .base import Layer, LayerStateError, RenderContext, register_layer
from .reference import (
    Basemap,
    DropShadow,
    Graticule,
    OceanGradient,
    Raster,
    Tile,
)
from .thematic import (
    Category,
    Choropleth,
    Label,
    Proportional,
    Situation,
    Vector,
)

__all__ = [
    "Layer",
    "RenderContext",
    "LayerStateError",
    "register_layer",
    "Choropleth",
    "Category",
    "Proportional",
    "Situation",
    "Label",
    "Vector",
    "Basemap",
    "Tile",
    "Raster",
    "Graticule",
    "DropShadow",
    "OceanGradient",
]
