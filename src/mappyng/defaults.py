"""
Centralized default values for mappyng.

**Every** configurable constant lives here.  Other modules import what they
need, nothing is hardcoded elsewhere.  Values are organized by functional
area so they're easy to find and override.

All defaults can be overridden at call time via the dict-based API of each
``Map`` method.  The values below are the *factory* defaults used when no
override is provided.
"""

# ============================================================================
# Mathematical / structural constants
# ============================================================================

PHI = 1.618
"""Golden ratio, used for legend swatch proportions."""

# ============================================================================
# Document
# ============================================================================

DOCUMENT_WIDTH = 800
DOCUMENT_HEIGHT = 600
DOCUMENT_PADDING = 20
DOCUMENT_BACKGROUND = "white"
DEFAULT_COORDINATE_PRECISION = 2
"""Decimal places kept for geometry path coordinates in the SVG output.

Lower values shrink the file and speed up parsing at the cost of
sub-pixel accuracy. At the default, coordinates keep hundredths of a
pixel."""
SIMPLIFY_AUTO_PIXELS = 0.5
"""Target tolerance in pixels for ``simplify='auto'``.

The geometric tolerance in CRS units is this value divided by the
viewport scale, so vertices that move less than half a pixel are
dropped. Below this, the change is not visible at the render scale."""
FONT_SCALE_REFERENCE_WIDTH = 800
"""Reference SVG width for auto font_scale."""
FONT_SCALE_REFERENCE_HEIGHT = 600
"""Reference SVG height for auto font_scale."""
FONT_SCALE_AUTO_COEFF = 1.5
"""Multiplier applied to the sqrt(area) ratio in auto font_scale mode."""

# ============================================================================
# Viewport
# ============================================================================

VIEWPORT_PADDING_MAIN = 5
VIEWPORT_PADDING_CARTOUCHE = 2
VIEWPORT_PADDING_ZOOM = 2
VIEWPORT_BORDER_COLOR = "#A3A5C3"
VIEWPORT_BORDER_WIDTH = 0.5

# ============================================================================
# Layout, figure-fraction positions
# ============================================================================

LAYOUT_BASEMAP_X0 = 0.06
"""Left edge of the main map as figure fraction [0..1]."""
LAYOUT_BASEMAP_Y0 = 0.08
"""Bottom edge of the main map (matplotlib convention: y=0 at bottom)."""
LAYOUT_BASEMAP_WIDTH = 0.88
"""Width of the main map as figure fraction."""
LAYOUT_BASEMAP_HEIGHT = 0.83
"""Height of the main map as figure fraction."""

LAYOUT_CARTOUCHE_SIZE = 0.13
"""Cartouche size as fraction of basemap height."""
LAYOUT_CARTOUCHE_HSPACING = 0.01
"""Horizontal gap (figure fraction) between cartouche and basemap."""
LAYOUT_CARTOUCHE_VSPACING = 0.01
"""Vertical gap (figure fraction) between successive cartouches."""
LAYOUT_CARTOUCHE_TITLE_GAP = 0.02
"""Extra vertical gap (figure fraction) when a cartouche has a title."""
LAYOUT_CARTOUCHE_TITLE_OFFSET = 0.01
"""Gap (figure fraction) from basemap top to first cartouche top."""

LAYOUT_ZOOM_LEFT = 0.77
"""Zoom window left edge as figure fraction."""
LAYOUT_ZOOM_BOTTOM = 0.734
"""Zoom window bottom edge as figure fraction."""
LAYOUT_ZOOM_WIDTH = 0.1
"""Zoom window width as figure fraction."""
LAYOUT_ZOOM_HEIGHT = 0.1
"""Zoom window height as figure fraction."""

# ============================================================================
# Fonts
# ============================================================================

FONT_FAMILY = "sans-serif"
FONT_SIZE = 10
FONT_WEIGHT = "normal"
FONT_COLOR = "#6c757d"
FONT_ALPHA = 1.0

# ============================================================================
# Edges
# ============================================================================

EDGE_COLOR = "#4d4d4d"
EDGE_WIDTH = 0.3

# ============================================================================
# Basemap
# ============================================================================

BASEMAP_FILL_COLOR = "#ebeced"
BASEMAP_EDGE_COLOR = "#4d4d4d"
BASEMAP_EDGE_WIDTH = 0.2

# ============================================================================
# Title
# ============================================================================

TITLE_FONT_SIZE = 13
TITLE_FONT_WEIGHT = "bold"
TITLE_MAX_CHARS = 50
TITLE_LINE_HEIGHT_RATIO = 1.3
"""Line height as multiple of font_size."""
TITLE_SUBTITLE_SIZE_RATIO = 0.75
"""Subtitle font size as fraction of title font size."""
TITLE_SUBTITLE_WEIGHT = "normal"
TITLE_SUBTITLE_GAP = 2
"""Gap between title block and subtitle (pixels)."""
TITLE_TOP_GAP = 8
"""Vertical gap between top of main viewport frame and title baseline (pixels)."""

# ============================================================================
# Scale bar
# ============================================================================

SCALE_BAR_LOCATION = "lower right"
SCALE_BAR_FONT_SIZE = 7
SCALE_BAR_FONT_WEIGHT = "normal"
SCALE_BAR_HEIGHT = 3.0
"""Bar thickness in pixels."""
SCALE_BAR_MARGIN = 15
"""Margin from viewport content edge (pixels)."""
SCALE_BAR_TICK_EXTRA = 3
"""Extra height of end ticks beyond the bar (pixels)."""
SCALE_BAR_LABEL_GAP = 3
"""Gap between bar top and label baseline (pixels)."""
SCALE_BAR_TICK_WIDTH = 1.0
SCALE_BAR_UPPER_OFFSET = 4
"""Extra offset when location is 'upper' (pixels)."""
SCALE_BAR_PAD = 1.0
"""Scale bar padding (figure fraction)."""
SCALE_BAR_POSITION = None
"""Manual position as {"x": frac, "y": frac} relative to content area. None = use location."""
SCALE_BAR_UNIT = "km"
"""Unit label appended to auto-generated labels."""
SCALE_BAR_UNIT_FACTOR = 1000.0
"""Divisor to convert map CRS units to display units (e.g. 1000 for m to km)."""

# ============================================================================
# Source text
# ============================================================================

SOURCE_FONT_SIZE = 7
SOURCE_ALPHA = 0.5
SOURCE_ROTATION = 90
SOURCE_FONT_STYLE = "italic"
SOURCE_FONT_WEIGHT = "normal"
SOURCE_OFFSET_X = 14
"""Horizontal offset from viewport right edge (pixels)."""
SOURCE_CONFIG_X = 1.01
"""Source text x position (figure fraction)."""
SOURCE_CONFIG_Y = 0.01
"""Source text y position (figure fraction)."""
SOURCE_LAYOUT = "vertical"
"""Source layout: 'vertical' (rotated 90° at right edge) or 'horizontal' (bottom-right)."""
SOURCE_HORIZONTAL_MARGIN = 8
"""Margin from basemap edge in horizontal mode (pixels)."""
SOURCE_HORIZONTAL_LINE_SPACING = 1.3
"""Line height ratio for multi-line horizontal source text."""
SOURCE_POSITION = None
"""Manual source position as {"x": frac, "y": frac} relative to content area. None = auto."""

# ============================================================================
# Shadow
# ============================================================================

RASTER_ALPHA = 1.0
"""Default raster opacity (0-1)."""

SHADOW_DX = 1.5
SHADOW_DY = 1.5
SHADOW_STD_DEVIATION = 2.5
SHADOW_COLOR = "#555555"
SHADOW_OPACITY = 0.5
SHADOW_FILL = "#ffffff"
SHADOW_FILTER_MARGIN = 20
"""SVG filter region expansion in percent (applied as -N% / +2N%)."""

OCEAN_GRADIENT_WIDTH = 24.0
"""Distance in pixels over which the ocean gradient fades out."""
OCEAN_GRADIENT_COLOR = "#ffffff"
OCEAN_GRADIENT_OPACITY = 0.45
"""Opacity of the gradient along the coast."""
OCEAN_GRADIENT_STEPS = 8
"""Number of bands drawn to approximate the gradient."""

# ============================================================================
# Effects, box shadow
# ============================================================================

BOX_SHADOW_DX = 2.0
"""Horizontal offset of box shadow (pixels)."""
BOX_SHADOW_DY = 2.0
"""Vertical offset of box shadow (pixels)."""
BOX_SHADOW_BLUR = 4.0
"""Gaussian blur radius of box shadow (pixels)."""
BOX_SHADOW_COLOR = "#000000"
BOX_SHADOW_OPACITY = 0.25
BOX_SHADOW_FILTER_MARGIN = 30
"""SVG filter region expansion in percent."""

# ============================================================================
# Effects, glow
# ============================================================================

GLOW_BLUR = 6.0
"""Gaussian blur radius of outer glow (pixels)."""
GLOW_COLOR = "#ffffff"
GLOW_OPACITY = 0.6
GLOW_FILTER_MARGIN = 30
"""SVG filter region expansion in percent."""

# ============================================================================
# Effects, border radius
# ============================================================================

BORDER_RADIUS = 0.0
"""Default border radius for viewports (pixels). 0 = sharp corners."""

# ============================================================================
# Cartouche
# ============================================================================

CARTOUCHE_TITLE_SIZE = 8
CARTOUCHE_TITLE_PADDING = 4
"""Vertical space below the title text before the cartouche box (pixels)."""
CARTOUCHE_TITLE_MARGIN_ABOVE = 3
"""Gap above the cartouche box for the title (pixels)."""
CARTOUCHE_BORDER_WIDTH = 0.5

# ============================================================================
# Zoom
# ============================================================================

ZOOM_BORDER_WIDTH = 1.0

# ============================================================================
# Legend, shared
# ============================================================================

LEGEND_TITLE_FONT_SIZE = 10
LEGEND_TITLE_FONT_WEIGHT = "bold"
LEGEND_TITLE_MAX_CHARS = 35
LEGEND_TITLE_SPACING = 2
"""Vertical gap below the legend title (pixels)."""
LEGEND_SUBTITLE_FONT_SIZE = 8
"""Font size for the legend subtitle (pixels)."""
LEGEND_SUBTITLE_FONT_WEIGHT = "normal"
LEGEND_SUBTITLE_SPACING = 5
"""Vertical gap below the legend subtitle (pixels)."""
LEGEND_FONT_SIZE = 9
"""Fallback font size for legend labels."""
LEGEND_SPACING = 0.01
"""Default legend spacing (figure fraction)."""
LEGEND_LOCATION = "lower left"
LEGEND_ALIGN = "left"
"""Legend horizontal alignment: 'left' or 'center'."""
LEGEND_POSITION = None
"""Legend position as (x_frac, y_frac) relative to viewport content area.
None = default placement below the map. Example: (0.02, 0.7) places the
legend at 2% from left, 70% from top of the main viewport content."""

# ============================================================================
# Legend, frame / box (disabled by default)
# ============================================================================

LEGEND_FRAME = False
"""Whether to draw a background frame behind the legend."""
LEGEND_FRAME_FILL = "#ffffff"
"""Background fill color of the legend frame."""
LEGEND_FRAME_FILL_OPACITY = 0.85
"""Fill opacity of the legend frame."""
LEGEND_FRAME_STROKE = "#cccccc"
"""Border color of the legend frame."""
LEGEND_FRAME_STROKE_WIDTH = 0.5
"""Border width of the legend frame (pixels)."""
LEGEND_FRAME_BORDER_RADIUS = 4.0
"""Corner radius of the legend frame (pixels). 0 = sharp corners."""
LEGEND_FRAME_PADDING = 8.0
"""Internal padding between frame edge and legend content (pixels)."""
LEGEND_FRAME_SHADOW = False
"""Whether to add a drop shadow to the legend frame."""
LEGEND_FRAME_SHADOW_DX = 1.0
LEGEND_FRAME_SHADOW_DY = 1.0
LEGEND_FRAME_SHADOW_BLUR = 3.0
LEGEND_FRAME_SHADOW_OPACITY = 0.15
LEGEND_CONFIG_X = 0.15
"""Legend x position (figure fraction)."""
LEGEND_CONFIG_Y = -0.12
"""Legend y position (figure fraction)."""

LEGEND_HATCH_STYLE = "///"
LEGEND_HATCH_COLOR = "#bcb8b1"
LEGEND_HATCH_LINE_WIDTH = 1.5
LEGEND_HATCH_PATTERN_SIZE = 6

LEGEND_SWATCH_SCALE = 1.4
"""Fixed multiplier applied to swatch dimensions independently of font_scale."""
LEGEND_SWATCH_STROKE_WIDTH = 0.3
LEGEND_SWATCH_SHAPE = "rect"
"""Legend swatch shape: "rect", "rounded" or "circle"."""
LEGEND_SWATCH_ROUNDED_RATIO = 0.25
"""Default corner radius of "rounded" swatches, as a share of the shorter side."""
LEGEND_NODATA_LABEL = "N/A"
LEGEND_BELOW_MAP_GAP = 20
"""Vertical gap between map content bottom and legend top (pixels)."""
LEGEND_NODATA_GAP = 25
"""Horizontal gap between last swatch and N/A indicator (pixels)."""
LEGEND_NODATA_LABEL_GAP = 4
"""Gap between the N/A swatch right edge and its label text (pixels)."""

# ============================================================================
# Legend, choropleth specific
# ============================================================================

CHOROPLETH_SWATCH_WIDTH = 30.0
CHOROPLETH_SWATCH_SPACING = 10.0
CHOROPLETH_LABEL_ROTATION = -33.0
CHOROPLETH_DECIMALS = 1
CHOROPLETH_LABEL_SPACING = 2
"""Gap between swatch bottom and label baseline (pixels)."""
CHOROPLETH_LABEL_MARGIN = 5.0
"""Default margin (px) between the bottom of swatches and the label baseline."""
CHOROPLETH_ORIENTATION = "vertical"
"""Legend orientation: 'horizontal' or 'vertical'."""
CHOROPLETH_VERTICAL_SWATCH_WIDTH = 20.0
"""Swatch width for vertical legend (pixels)."""
CHOROPLETH_VERTICAL_SWATCH_HEIGHT = 16.0
"""Swatch height for vertical legend (pixels)."""
CHOROPLETH_VERTICAL_LABEL_GAP = 6.0
"""Gap between swatch right edge and label text (pixels)."""

# Factor (PCA) legend
FACTOR_POLE_MAX_CHARS = 34
"""Characters per line before a pole interpretation text wraps."""
FACTOR_NOTE_MAX_CHARS = 52
"""Characters per line before the methodology note wraps."""
FACTOR_POLE_GAP = 6.0
"""Vertical gap between a pole text and the class block (pixels)."""
FACTOR_NOTE_GAP = 10.0
"""Vertical gap above the methodology note (pixels)."""
FACTOR_LINE_HEIGHT = 1.2
"""Line-height multiplier for wrapped pole and note text."""
FACTOR_BELOW_GAP = 18.0
"""Gap below the map content where the legend sits by default (pixels)."""
FACTOR_NODATA_GAP = 16.0
"""Extra vertical gap above the no-data entry (pixels)."""
FACTOR_ARROW_WIDTH = 1.2
"""Stroke width of the factor axis arrow."""
FACTOR_ARROW_HEAD = 6.0
"""Arrowhead size of the factor axis arrow (pixels)."""
FACTOR_ARROW_GAP = 16.0
"""Width reserved to the left of the swatches for the axis arrow (pixels)."""
FACTOR_ARROW_LEN = 16.0
"""Length of each pole arrow (pixels)."""
FACTOR_VALUE_FONT_SIZE = 7
"""Default font size of the class break values and no-data label (smaller)."""

# ============================================================================
# Situation, categorical readability
# ============================================================================

SITUATION_MAX_CATEGORIES_WARN = 8
"""Soft limit on the number of categorical symbols in Situation
before a readability warning is emitted (not a hard error)."""

# ============================================================================
# Proportional symbols
# ============================================================================

PROPORTIONAL_FILL = "#e31a1c"
PROPORTIONAL_FILL_OPACITY = 0.7
PROPORTIONAL_STROKE = "#ffffff"
PROPORTIONAL_STROKE_WIDTH = 0.5
PROPORTIONAL_MAX_RADIUS = 30.0
"""Maximum circle radius in SVG pixels (for auto-scaling)."""
PROPORTIONAL_MIN_RADIUS = 2.0
"""Minimum circle radius in SVG pixels (below this, circles disappear)."""

# ============================================================================
# Legend, proportional
# ============================================================================

LEGEND_CIRCLE_EDGECOLOR = "black"
LEGEND_CIRCLE_LINEWIDTH = 0.8
LEGEND_CIRCLE_FILL_OPACITY = 0.4
LEGEND_CIRCLE_NUM_VALUES = 3
"""Number of legend circles when auto-generated."""
LEGEND_CIRCLE_LABEL_GAP = 5
"""Horizontal gap between circle edge and label text (pixels)."""
LEGEND_CIRCLE_LEADER_COLOR = "#999999"
LEGEND_CIRCLE_LEADER_WIDTH = 0.5
LEGEND_CIRCLE_LEADER_DASH = "2,2"
LEGEND_CIRCLE_LEADER_OPACITY = 0.6
"""Opacity of leader lines in nested proportional legend (0-1)."""
LEGEND_CIRCLE_SPACING = 0.02
"""Horizontal spacing between legend circles (figure fraction, horizontal mode)."""
PROPORTIONAL_LEGEND_ORIENTATION = "nested"
"""Proportional legend layout: 'nested', 'vertical', or 'horizontal'."""
PROPORTIONAL_LEGEND_CIRCLE_GAP = 4.0
"""Vertical gap between circle rows in vertical mode (pixels)."""
PROPORTIONAL_LEGEND_HORIZONTAL_GAP = 12.0
"""Horizontal gap between circles in horizontal mode (pixels)."""

# ============================================================================
# Legend, choropleth histogram
# ============================================================================

CHOROPLETH_HIST_WIDTH = 80.0
"""Width of the legend distribution histogram (SVG px)."""
CHOROPLETH_HIST_HEIGHT = 50.0
"""Height of the legend distribution histogram (SVG px)."""
CHOROPLETH_HIST_GAP = 16.0
"""Horizontal gap between legend block and histogram (SVG px)."""
CHOROPLETH_HIST_DEFAULT_BINS = 20
"""Default number of bars in the legend histogram."""
CHOROPLETH_HIST_BASELINE_COLOR = "#888888"
CHOROPLETH_HIST_BAR_STROKE_WIDTH = 0.2

# ============================================================================
# Choropleth, classification
# ============================================================================

CHOROPLETH_DEFAULT_CMAP = "YlOrRd"
CHOROPLETH_DEFAULT_METHOD = "EqualInterval"
CHOROPLETH_DEFAULT_NUM_CLASSES = 5
CHOROPLETH_MIN_CLASSES = 4
CHOROPLETH_MAX_CLASSES = 7

# Choropleth, opacity-as-probability (opacity_column)
CHOROPLETH_DEFAULT_MIN_OPACITY = 0.15
"""Opacity floor for opacity_column: even a near-zero probability stays
visible rather than disappearing into the background."""
CHOROPLETH_DEFAULT_MAX_OPACITY = 1.0
"""Opacity for a probability of 1.0 with opacity_column."""

# StdMean breaks, in standard-deviation steps either side of the mean.
# Each list has an even number of breaks, so the class count is odd and the
# central class straddles the mean. Only these class counts are supported.
CHOROPLETH_STDMEAN_MULTIPLES = {
    5: [-1.0, -0.5, 0.5, 1.0],
    7: [-1.5, -1.0, -0.5, 0.5, 1.0, 1.5],
}

# Choropleth, stock-data heuristic
CHOROPLETH_STOCK_MAGNITUDE_WARN = 1000.0
"""A strictly-positive integer column is flagged as likely stock
(absolute count) data when its maximum reaches this magnitude AND it
also has a wide spread (see CHOROPLETH_STOCK_RATIO_WARN). Keeps
identifier-like columns (small max) and near-constant columns (small
spread) silent. Heuristic only, emits a warning, never an error."""
CHOROPLETH_STOCK_RATIO_WARN = 10.0
"""Minimum max/min ratio (spread) for the stock-data heuristic. Combined
with CHOROPLETH_STOCK_MAGNITUDE_WARN; both must hold to flag a column."""

# Export raster/PDF
EXPORT_DEFAULT_DPI = 96
"""Default DPI for PNG export via cairosvg (extra mappyng[export])."""

# ============================================================================
# Z-order, layer stacking (higher = on top)
# ============================================================================

# ============================================================================
# North arrow
# ============================================================================

NORTH_ARROW_LOCATION = "upper right"
"""Default preset position for the north arrow."""
NORTH_ARROW_POSITION = None
"""Manual position override as {'x': frac, 'y': frac}. None = use location."""
NORTH_ARROW_SIZE = 24.0
"""Total arrow height in SVG px."""
NORTH_ARROW_COLOR = "#4d4d4d"
"""Color for shaft, arrowhead and label."""
NORTH_ARROW_MARGIN = 15.0
"""Distance from content edge in SVG px."""
NORTH_ARROW_LABEL = "N"
"""Text drawn above the arrowhead (pass '' to suppress)."""
NORTH_ARROW_FONT_SIZE = 9
"""Font size for the north label."""
NORTH_ARROW_STROKE_WIDTH = 1.0
"""Shaft stroke width in SVG px."""
NORTH_ARROW_ROTATION = 0.0
"""Manual rotation in degrees (0 = points up)."""

Z_NORTH_ARROW = 250
"""Z-order for north arrow, same level as scale bar."""

Z_BACKGROUND = -100
Z_OCEAN = -50
Z_OCEAN_GRADIENT = -40
"""Coastal gradient, above the ocean and below rasters and graticules."""
Z_RASTER = -5
"""Raster images (GeoTIFF MNT), below basemap polygons."""
Z_GRATICULES = -2
Z_BASEMAP = 0
Z_SHADOW = 1
Z_LAYER_BACKGROUND = 5
Z_CHOROPLETH = 10
Z_SITUATION = 20
Z_PROPORTIONAL = 30
Z_TOPONYME = 40
Z_LAYER_TOP = 50
Z_LAYOUT = 200
Z_CARTOUCHE_TITLE = 200
Z_LEGEND = 250
Z_SCALE_BAR = 250
Z_SOURCE = 250
Z_TITLE = 300

# ============================================================================
# Style presets
# ============================================================================

STYLES = {
    "classic": {
        "title_color": "#6c757d",
        "title_size": TITLE_FONT_SIZE,
        "title_weight": TITLE_FONT_WEIGHT,
        "title_font_family": FONT_FAMILY,
        "edge_color": EDGE_COLOR,
        "edge_width": EDGE_WIDTH,
        "basemap_fill": BASEMAP_FILL_COLOR,
        "basemap_edge_color": BASEMAP_EDGE_COLOR,
        "basemap_edge_width": BASEMAP_EDGE_WIDTH,
        "legend_title_color": "#6c757d",
        "legend_title_size": LEGEND_TITLE_FONT_SIZE,
        "legend_title_weight": LEGEND_TITLE_FONT_WEIGHT,
        "legend_title_font_family": FONT_FAMILY,
        "legend_text_color": "#6c757d",
        "legend_text_size": FONT_SIZE,
        "scale_color": "#6c757d",
        "source_color": "#6c757d",
        "source_size": SOURCE_FONT_SIZE,
        "source_alpha": SOURCE_ALPHA,
        "layout_edge_color": VIEWPORT_BORDER_COLOR,
    },
    "modern": {
        "title_color": "#355070",
        "title_size": TITLE_FONT_SIZE,
        "title_weight": TITLE_FONT_WEIGHT,
        "title_font_family": FONT_FAMILY,
        "edge_color": "#2c3e50",
        "edge_width": 0.2,
        "basemap_fill": "#f7f7f7",
        "basemap_edge_color": "#b5b5b5",
        "basemap_edge_width": 0.1,
        "legend_title_color": "#355070",
        "legend_title_size": LEGEND_TITLE_FONT_SIZE,
        "legend_title_weight": LEGEND_TITLE_FONT_WEIGHT,
        "legend_title_font_family": FONT_FAMILY,
        "legend_text_color": "#355070",
        "legend_text_size": FONT_SIZE,
        "scale_color": "#355070",
        "source_color": "#355070",
        "source_size": SOURCE_FONT_SIZE,
        "source_alpha": SOURCE_ALPHA,
        "layout_edge_color": VIEWPORT_BORDER_COLOR,
    },
}
