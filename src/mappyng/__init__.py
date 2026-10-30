"""
mappyng, SVG-native cartographic visualization library.

Built on GeoDataFrames and pure SVG output.

Example
-------
>>> import mappyng as mp
>>> from mappyng.data import load_france_regions
>>>
>>> regions = load_france_regions()
>>> m = (
...     mp.Map(regions, width=800, height=600)
...     + mp.Basemap()
...     + mp.Title("Régions de France")
...     + mp.ScaleBar(length=100000)
... )
>>> m.render("map.svg")
"""

__version__ = "1.0.0"

from . import defaults
from .border_contrast import BorderContrast
from .choropleth import ChoroplethLegendConfig, FactorLegend
from .choropleth_classify import CategoryReport, ClassificationReport
from .config import (
    ConfigManager,
    EdgeConfig,
    FontConfig,
    LegendConfig,
    Style,
    StyleConfig,
)
from .effects import BoxShadowConfig, GlowConfig
from .elements import (
    Element,
    Inset,
    Insets,
    Legend,
    NorthArrow,
    RadialGradient,
    ScaleBar,
    Source,
    Title,
    Tooltip,
    Zoom,
)
from .errors import (
    CartoucheError,
    DataError,
    LayoutError,
    MapError,
    RenderError,
    handle_map_errors,
)
from .interactive import HoverEffect, InteractiveMap, TooltipStyle
from .layers import (
    Basemap,
    Category,
    Choropleth,
    DropShadow,
    Graticule,
    Label,
    Layer,
    LayerStateError,
    OceanGradient,
    Proportional,
    Raster,
    RenderContext,
    Situation,
    Tile,
    Vector,
)
from .legend import BaseLegendConfig
from .map import Map
from .proportional import ProportionalLegendConfig
from .renderer import SvgDocument, SvgViewport, ViewBox
from .situation import MarkerConfig, SituationLegendConfig
from .tile import TileConfig
from .tile import list_providers as list_tile_providers
from .toponyme import LabelConfig

__all__ = [
    "Map",
    "defaults",
    "ConfigManager",
    "StyleConfig",
    "Style",
    "FontConfig",
    "EdgeConfig",
    "LegendConfig",
    "BaseLegendConfig",
    "ChoroplethLegendConfig",
    "CategoryReport",
    "ClassificationReport",
    "FactorLegend",
    "ProportionalLegendConfig",
    "BoxShadowConfig",
    "GlowConfig",
    "InteractiveMap",
    "TooltipStyle",
    "HoverEffect",
    "MarkerConfig",
    "SituationLegendConfig",
    "ViewBox",
    "SvgViewport",
    "SvgDocument",
    "MapError",
    "RenderError",
    "CartoucheError",
    "DataError",
    "LayoutError",
    "handle_map_errors",
    "LabelConfig",
    "TileConfig",
    "list_tile_providers",
    "Layer",
    "RenderContext",
    "LayerStateError",
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
    "Element",
    "Title",
    "Source",
    "ScaleBar",
    "NorthArrow",
    "Legend",
    "BorderContrast",
    "Inset",
    "Insets",
    "Zoom",
    "Tooltip",
    "RadialGradient",
]
