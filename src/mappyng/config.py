"""
Configuration management for mappyng.

Style definitions, colormaps, and z-order. All default values are
imported from :mod:`mappyng.defaults`, nothing is hardcoded here.
"""

from dataclasses import dataclass, field
from typing import Any

from . import defaults as D


def alpha_blend_hex(fg: str, bg: str, alpha: float) -> str:
    """Alpha-composite *fg* over *bg* and return an opaque ``#RRGGBB`` colour.

    Both colours are ``#RRGGBB`` hex strings. ``alpha`` in ``[0, 1]`` is the
    foreground's opacity: 0 yields *bg*, 1 yields *fg*. Unlike SVG
    ``fill-opacity``, the result is a single solid colour, independent of
    whatever ends up drawn underneath.
    """
    def _to_rgb(hex_color: str):
        h = hex_color.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    fr, fg_, fb = _to_rgb(fg)
    br, bg_, bb = _to_rgb(bg)
    r = round(br + (fr - br) * alpha)
    g = round(bg_ + (fg_ - bg_) * alpha)
    b = round(bb + (fb - bb) * alpha)
    return f"#{r:02x}{g:02x}{b:02x}"


@dataclass
class ZOrderConfig:
    """Z-order for SVG layer stacking (higher = on top)."""
    OCEAN: int = D.Z_OCEAN
    OCEAN_GRADIENT: int = D.Z_OCEAN_GRADIENT
    RASTER: int = D.Z_RASTER
    GRATICULES: int = D.Z_GRATICULES
    SHADOW: int = D.Z_SHADOW
    BASEMAP: int = D.Z_BASEMAP
    LAYER_BACKGROUND: int = D.Z_LAYER_BACKGROUND
    CHOROPLETH: int = D.Z_CHOROPLETH
    SITUATION: int = D.Z_SITUATION
    PROPORTIONAL: int = D.Z_PROPORTIONAL
    TOPONYME: int = D.Z_TOPONYME
    LAYER_TOP: int = D.Z_LAYER_TOP
    LAYOUT: int = D.Z_LAYOUT


@dataclass
class FontConfig:
    """Font settings."""
    family: str = D.FONT_FAMILY
    size: int = D.FONT_SIZE
    weight: str = D.FONT_WEIGHT
    color: str = D.FONT_COLOR
    opacity: float = D.FONT_ALPHA


@dataclass
class EdgeConfig:
    """Stroke settings."""
    color: str = D.EDGE_COLOR
    width: float = D.EDGE_WIDTH


@dataclass
class LegendConfig:
    """Legend settings."""
    title: FontConfig = field(default_factory=lambda: FontConfig(
        size=D.LEGEND_TITLE_FONT_SIZE, weight=D.LEGEND_TITLE_FONT_WEIGHT,
    ))
    text: FontConfig = field(default_factory=FontConfig)
    hatch_style: str = D.LEGEND_HATCH_STYLE
    hatch_color: str = D.LEGEND_HATCH_COLOR
    spacing: float = D.LEGEND_SPACING
    location: str = D.LEGEND_LOCATION
    x: float = D.LEGEND_CONFIG_X
    y: float = D.LEGEND_CONFIG_Y
    circle_stroke: str = D.LEGEND_CIRCLE_EDGECOLOR
    circle_stroke_width: float = D.LEGEND_CIRCLE_LINEWIDTH
    circle_spacing: float = D.LEGEND_CIRCLE_SPACING
    title_max_chars: int = D.LEGEND_TITLE_MAX_CHARS


@dataclass
class BasemapConfig:
    """Basemap polygon styling."""
    fill_color: str = D.BASEMAP_FILL_COLOR
    edge: EdgeConfig = field(default_factory=lambda: EdgeConfig(
        color=D.BASEMAP_EDGE_COLOR, width=D.BASEMAP_EDGE_WIDTH,
    ))


@dataclass
class ScaleConfig:
    """Scale bar settings."""
    color: str = D.FONT_COLOR
    location: str = D.SCALE_BAR_LOCATION
    pad: float = D.SCALE_BAR_PAD


@dataclass
class SourceConfig:
    """Source text settings."""
    font: FontConfig = field(default_factory=lambda: FontConfig(
        size=D.SOURCE_FONT_SIZE, opacity=D.SOURCE_ALPHA,
    ))
    x: float = D.SOURCE_CONFIG_X
    y: float = D.SOURCE_CONFIG_Y
    rotation: float = D.SOURCE_ROTATION


@dataclass
class StyleConfig:
    """Complete style configuration."""
    name: str
    title: FontConfig = field(default_factory=FontConfig)
    legend: LegendConfig = field(default_factory=LegendConfig)
    edge: EdgeConfig = field(default_factory=EdgeConfig)
    basemap: BasemapConfig = field(default_factory=BasemapConfig)
    scale: ScaleConfig = field(default_factory=ScaleConfig)
    source: SourceConfig = field(default_factory=SourceConfig)
    z_order: ZOrderConfig = field(default_factory=ZOrderConfig)
    layout_edge_color: str = D.VIEWPORT_BORDER_COLOR


@dataclass
class Style:
    """Wrapper providing dict-like access to StyleConfig."""
    config: StyleConfig

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __getitem__(self, key: str) -> Any:
        mapping: dict[str, Any] = {
            "edge_color": self.config.edge.color,
            "edge_width": self.config.edge.width,
            "basemap_fill_color": self.config.basemap.fill_color,
            "basemap_edge_color": self.config.basemap.edge.color,
            "basemap_edge_width": self.config.basemap.edge.width,
            "title_color": self.config.title.color,
            "title_size": self.config.title.size,
            "title_fontweight": self.config.title.weight,
            "title_font_family": self.config.title.family,
            "legend_title_fontsize": self.config.legend.title.size,
            "legend_title_fontcolor": self.config.legend.title.color,
            "legend_title_fontweight": self.config.legend.title.weight,
            "legend_title_fontfamily": self.config.legend.title.family,
            "legend_fontsize": self.config.legend.text.size,
            "legend_fontcolor": self.config.legend.text.color,
            "legend_fontweight": self.config.legend.text.weight,
            "legend_fontfamily": self.config.legend.text.family,
            "legend_hatch_style": self.config.legend.hatch_style,
            "legend_hatch_color": self.config.legend.hatch_color,
            "scale_color": self.config.scale.color,
            "scale_location": self.config.scale.location,
            "scale_pad": self.config.scale.pad,
            "source_color": self.config.source.font.color,
            "source_alpha": self.config.source.font.opacity,
            "source_fontsize": self.config.source.font.size,
            "source_fontweight": self.config.source.font.weight,
            "source_fontfamily": self.config.source.font.family,
            "ax_layout_edge_color": self.config.layout_edge_color,
        }
        if key not in mapping:
            raise KeyError(f"Unknown style key: {key}")
        return mapping[key]


# ============================================================================
# Colormaps
# ============================================================================

#: Sequential and diverging colour ramps: colormap name, then number of
#: classes (4 to 7), then the list of ``#RRGGBB`` colours.
COLORMAP_DEFS: dict[str, dict[int, list[str]]] = {
    'YlOrRd': {
        4: ['#ffffb2', '#fecc5c', '#fd8d3c', '#e31a1c'],
        5: ['#ffffb2', '#fecc5c', '#fd8d3c', '#f03b20', '#bd0026'],
        6: ['#ffffb2', '#fed976', '#feb24c', '#fd8d3c', '#f03b20', '#bd0026'],
        7: ['#ffffb2', '#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#b10026'],
    },
    'Blues': {
        4: ['#eff3ff', '#bdd7e7', '#6baed6', '#2171b5'],
        5: ['#eff3ff', '#bdd7e7', '#6baed6', '#3182bd', '#08519c'],
        6: ['#eff3ff', '#c6dbef', '#9ecae1', '#6baed6', '#3182bd', '#08519c'],
        7: ['#eff3ff', '#c6dbef', '#9ecae1', '#6baed6', '#4292c6', '#2171b5', '#084594'],
    },
    'Greens': {
        4: ['#edf8e9', '#bae4b3', '#74c476', '#238b45'],
        5: ['#edf8e9', '#bae4b3', '#74c476', '#31a354', '#006d2c'],
        6: ['#edf8e9', '#c7e9c0', '#a1d99b', '#74c476', '#31a354', '#006d2c'],
        7: ['#edf8e9', '#c7e9c0', '#a1d99b', '#74c476', '#41ab5d', '#238b45', '#005a32'],
    },
    'Reds': {
        4: ['#fee5d9', '#fcae91', '#fb6a4a', '#cb181d'],
        5: ['#fee5d9', '#fcae91', '#fb6a4a', '#de2d26', '#a50f15'],
        6: ['#fee5d9', '#fcbba1', '#fc9272', '#fb6a4a', '#de2d26', '#a50f15'],
        7: ['#fee5d9', '#fcbba1', '#fc9272', '#fb6a4a', '#ef3b2c', '#cb181d', '#99000d'],
    },
    'RdYlGn': {
        4: ['#d7191c', '#fdae61', '#a6d96a', '#1a9641'],
        5: ['#d7191c', '#fdae61', '#ffffbf', '#a6d96a', '#1a9641'],
        6: ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60', '#1a9850'],
        7: ['#d73027', '#fc8d59', '#fee08b', '#ffffbf', '#d9ef8b', '#91cf60', '#1a9850'],
    },
    'RdBu': {
        4: ['#ca0020', '#f4a582', '#92c5de', '#0571b0'],
        5: ['#ca0020', '#f4a582', '#f7f7f7', '#92c5de', '#0571b0'],
        6: ['#b2182b', '#ef8a62', '#fddbc7', '#d1e5f0', '#67a9cf', '#2166ac'],
        7: ['#b2182b', '#ef8a62', '#fddbc7', '#f7f7f7', '#d1e5f0', '#67a9cf', '#2166ac'],
    },
    'BrBG': {
        4: ['#a6611a', '#dfc27d', '#80cdc1', '#018571'],
        5: ['#a6611a', '#dfc27d', '#f5f5f5', '#80cdc1', '#018571'],
        6: ['#8c510a', '#d8b365', '#f6e8c3', '#c7eae5', '#5ab4ac', '#01665e'],
        7: ['#8c510a', '#d8b365', '#f6e8c3', '#f5f5f5', '#c7eae5', '#5ab4ac', '#01665e'],
    },
}

# Palettes whose colours run from one hue through a light centre to a
# contrasting hue. They read the two sides apart, which suits classifications
# centred on a midpoint (StdMean around the mean, factor scores around zero).
DIVERGING_COLORMAPS = ('RdYlGn', 'RdBu', 'BrBG')


def _build_style_from_dict(name: str, s: dict[str, Any]) -> StyleConfig:
    """Build a StyleConfig from a flat style dict.

    Used both for presets and for user-supplied overrides.
    """
    return StyleConfig(
        name=name,
        title=FontConfig(color=s["title_color"], size=s["title_size"],
                         weight=s["title_weight"],
                         family=s.get("title_font_family", D.FONT_FAMILY)),
        legend=LegendConfig(
            title=FontConfig(color=s["legend_title_color"],
                             size=s["legend_title_size"],
                             weight=s["legend_title_weight"],
                             family=s.get("legend_title_font_family", D.FONT_FAMILY)),
            text=FontConfig(color=s["legend_text_color"],
                            size=s["legend_text_size"]),
        ),
        edge=EdgeConfig(color=s["edge_color"], width=s["edge_width"]),
        basemap=BasemapConfig(
            fill_color=s["basemap_fill"],
            edge=EdgeConfig(color=s["basemap_edge_color"],
                            width=s["basemap_edge_width"]),
        ),
        scale=ScaleConfig(color=s["scale_color"]),
        source=SourceConfig(font=FontConfig(color=s["source_color"],
                                            size=s["source_size"],
                                            opacity=s["source_alpha"])),
        layout_edge_color=s["layout_edge_color"],
    )


def _build_style(name: str) -> StyleConfig:
    """Build a StyleConfig from a defaults.STYLES preset."""
    return _build_style_from_dict(name, D.STYLES[name])


STYLE_CONFIGS: dict[str, StyleConfig] = {
    name: _build_style(name) for name in D.STYLES
}


class ConfigManager:
    """Manager for style configurations and colormaps."""

    @staticmethod
    def get_style(style_input: str | dict[str, Any] = "classic") -> Style:
        """Build a Style from a preset name or a dict.

        Parameters
        ----------
        style_input : str or dict
            - ``str``, a registered preset name (e.g. ``"classic"``,
              ``"modern"``).
            - ``dict``, custom overrides.  If the dict contains a
              ``"base"`` key its value selects the starting preset
              (default ``"classic"``); all other keys override the
              corresponding ``STYLES`` values before building.

        Returns
        -------
        Style
        """
        if isinstance(style_input, str):
            if style_input not in STYLE_CONFIGS:
                raise ValueError(
                    f"Unknown style: {style_input}. "
                    f"Available: {list(STYLE_CONFIGS.keys())}"
                )
            return Style(STYLE_CONFIGS[style_input])

        if isinstance(style_input, dict):
            overrides = dict(style_input)
            base_name = overrides.pop("base", "classic")
            if base_name not in D.STYLES:
                raise ValueError(
                    f"Unknown base style: {base_name}. "
                    f"Available: {list(D.STYLES.keys())}"
                )
            merged = {**D.STYLES[base_name], **overrides}
            # Build a one-off StyleConfig from the merged dict
            return Style(_build_style_from_dict(base_name, merged))

        raise TypeError(
            f"style must be a str or dict, got {type(style_input)}"
        )

    @staticmethod
    def get_colormap(name: str, num_classes: int) -> list[str]:
        """Return a list of hex color strings for a built-in colormap.

        Parameters
        ----------
        name : str
            Colormap name. Available: ``"YlOrRd"``, ``"Blues"``,
            ``"Greens"``, ``"Reds"``, ``"RdYlGn"``.
        num_classes : int
            Number of classes (4-7).

        Returns
        -------
        list of str
            Hex color strings, length == num_classes.

        Raises
        ------
        ValueError
            If *name* or *num_classes* is not available.
        """
        if name not in COLORMAP_DEFS:
            raise ValueError(f"Unknown colormap: {name}. Available: {list(COLORMAP_DEFS.keys())}")
        if num_classes not in COLORMAP_DEFS[name]:
            raise ValueError(f"Invalid number of classes for {name}: {num_classes}")
        return COLORMAP_DEFS[name][num_classes]

    @staticmethod
    def add_style(name: str, config) -> None:
        """Register a custom style under *name*.

        Parameters
        ----------
        name : str
            Style name (used as ``style=`` in :class:`~mappyng.Map`).
        config : StyleConfig or dict
            A :class:`StyleConfig` instance, or a flat dict of overrides
            (same format as ``STYLES`` presets).  When a dict is passed it
            is merged on top of the ``"classic"`` preset before building
            the :class:`StyleConfig`.
        """
        if isinstance(config, dict):
            base = {**D.STYLES["classic"], **config}
            config = _build_style_from_dict(name, base)
        elif not isinstance(config, StyleConfig):
            raise TypeError("config must be a StyleConfig or a dict of style overrides")
        STYLE_CONFIGS[name] = config
