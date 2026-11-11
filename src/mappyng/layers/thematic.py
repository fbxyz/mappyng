"""Thematic (data-driven) layers.

Choropleth, proportional and situation layers. Each is a first-class
object whose ``render`` delegates to the matching drawing helper on
:class:`~mappyng.Map`.
"""

from __future__ import annotations

import warnings
from typing import Any

from .. import defaults as D
from .base import _UNSET, Layer, RenderContext, collect_set, register_layer


def _class_tooltip_frame(column: str, labels: list[str]) -> Any:
    """Tooltip data of a dissolved layer: one row per class.

    A dissolved polygon merges every feature of a class, so it has no row
    of its own in the layer data. Its tooltip gives the class instead,
    under the name of the mapped column. The index matches the element
    ids written by the renderer (``class0``, ``class1``...).
    """
    import pandas as pd
    return pd.DataFrame(
        {column: labels}, index=[f"class{i}" for i in range(len(labels))])


def _require_column(layer: Layer, column: Any, role: str = "column") -> None:
    """Raise in plain language when *column* is not a column of the data."""
    columns = getattr(layer.gdf, "columns", None)
    if column is None or columns is None or column in columns:
        return
    available = [c for c in columns if c != "geometry"]
    raise ValueError(
        f"{type(layer).__name__}: {role} {column!r} is not a column of gdf. "
        f"Available columns: {available}."
    )


@register_layer
class Choropleth(Layer):
    """Choropleth (graduated colour) layer.

    Maps a *relative* quantity (rate, ratio, density) to colour value.

    Parameters
    ----------
    gdf : GeoDataFrame
        Polygons with a numeric column.
    column : str
        Column to classify (required).
    cmap : str or list, optional
        Colour ramp name or explicit list of hex colours (default from
        defaults). With ``"StdMean"`` a diverging ramp (``"RdBu"``,
        ``"BrBG"``, ``"RdYlGn"``) reads the two sides of the mean apart; a
        sequential ramp raises a warning.
    reverse : bool, optional
        Reverse the colour order, so the lowest class takes the ramp's last
        colour (default False). Applies to named ramps and explicit lists.
    method : str, optional
        Classification scheme: ``"Quantiles"``, ``"EqualInterval"``,
        ``"FisherJenks"``, ``"Q6"``, ``"StdMean"`` or ``"PrettyBreaks"``.
    num_classes : int, optional
        Number of classes, usually 4 to 7 (default 5). ``"StdMean"`` supports
        5 or 7 (the central class straddles the mean, so the count is odd); any
        other count snaps to the nearest valid one with a warning. ``"Q6"``
        always yields 6.
    stroke : str, optional
        Outline colour of each area as ``#RRGGBB`` (default from style).
    stroke_width : float, optional
        Outline width (default from style).
    legend : dict or False, optional
        Legend configuration (see :class:`ChoroplethLegendConfig`), or a
        legend config instance. ``False`` draws no legend.
    dissolve : bool, optional
        Merge adjacent areas that share a class before drawing (default
        False).
    simplify : None, str or float, optional
        Geometry simplification: ``None`` (default, no simplification),
        ``"auto"`` (half a pixel at the render scale) or a tolerance in
        the data CRS units.
    opacity_column : str, optional
        Column holding a probability/confidence in ``[0, 1]``. When set,
        colour still encodes *column*'s class while opacity encodes
        certainty (linearly mapped onto ``[min_opacity, max_opacity]``).
    min_opacity, max_opacity : float, optional
        Opacity bounds for *opacity_column* (defaults 0.15 and 1.0).
        Ignored without *opacity_column*.
    blend_background : str, optional
        With *opacity_column*, pre-composite the class colour over this
        ``#RRGGBB`` background and draw an opaque solid fill instead of
        relying on SVG ``fill-opacity``. Gives a colour that looks the same
        regardless of what renders underneath; omit it to use native SVG
        transparency, which blends live with the basemap or other layers.
    opacity_bins : int or list of float, optional
        Discretize *opacity_column* into this many equal-width bins over
        ``[0, 1]`` (or explicit bin edges). With *dissolve*, features
        sharing both class and opacity bin merge into one path instead of
        having their opacity averaged. ``None`` (default) keeps opacity
        continuous, one value per feature.
    detail : GeoDataFrame or dict, optional
        Finer geometry for the zoom window and the cartouches, drawn
        instead of the generalised one. The symbology computed from *gdf*
        is carried to it through *detail_join*. A GeoDataFrame applies to
        the zoom and every cartouche; a dict maps ``"zoom"``,
        ``"cartouches"`` or a cartouche index to a GeoDataFrame.
        See :mod:`mappyng.detail`.
    detail_join : str, tuple or None, optional
        Key shared by *gdf* and *detail*: a column name present in both,
        a ``(gdf_column, detail_column)`` pair, or None (default) to join
        on the index.
    border_contrast : bool, str, dict or BorderContrast, optional
        Make the borders between touching areas of similar colour visible:
        ``True`` redraws only those shared borders in a contrasting colour,
        ``"check"`` reveals them thick in magenta and warns, a dict or a
        :class:`~mappyng.BorderContrast` sets thresholds and colours.
        Default off. See :mod:`mappyng.border_contrast`.
    on_zoom : bool, optional
        Draw on the zoom viewport (default True).
    on_cartouches : bool, optional
        Draw on cartouche viewports (default True).
    z_index : int, optional
        Render order (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m.add(Choropleth(gdf, column="density", method="FisherJenks"))
    """

    #: :class:`~mappyng.choropleth_classify.ClassificationReport` of the last
    #: render (method applied, bounds, class sizes, excluded values,
    #: adjustments); ``None`` until the layer has been drawn.
    report = None

    kind = "choropleth"
    requires_gdf = True

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        column: Any = _UNSET,
        cmap: Any = _UNSET,
        reverse: Any = _UNSET,
        method: Any = _UNSET,
        num_classes: Any = _UNSET,
        stroke: Any = _UNSET,
        stroke_width: Any = _UNSET,
        legend: Any = _UNSET,
        dissolve: Any = _UNSET,
        simplify: Any = _UNSET,
        opacity_column: Any = _UNSET,
        min_opacity: Any = _UNSET,
        max_opacity: Any = _UNSET,
        blend_background: Any = _UNSET,
        opacity_bins: Any = _UNSET,
        detail: Any = _UNSET,
        detail_join: Any = _UNSET,
        border_contrast: Any = _UNSET,
        on_zoom: Any = _UNSET,
        on_cartouches: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(
                column=column, cmap=cmap, reverse=reverse, method=method,
                num_classes=num_classes, stroke=stroke,
                stroke_width=stroke_width, legend=legend,
                dissolve=dissolve, simplify=simplify,
                opacity_column=opacity_column, min_opacity=min_opacity,
                max_opacity=max_opacity, blend_background=blend_background,
                opacity_bins=opacity_bins,
                detail=detail, detail_join=detail_join,
                border_contrast=border_contrast,
                on_zoom=on_zoom, on_cartouches=on_cartouches,
            ),
        )

    def validate(self) -> None:
        from ..border_contrast import parse_border_contrast
        parse_border_contrast(self.params.get("border_contrast"))
        if "column" not in self.params:
            raise ValueError(
                "Choropleth needs a 'column' parameter naming the "
                "numeric column to classify, e.g. "
                "Choropleth(gdf, column='density'). A choropleth "
                "colours each area by a value, so it has nothing to draw "
                "without one."
            )
        _require_column(self, self.params["column"])
        simplify = self.params.get("simplify")
        if simplify is not None and not isinstance(simplify, (int, float)):
            if simplify != "auto":
                raise ValueError(
                    f"simplify must be None, 'auto' or a number, got "
                    f"{simplify!r}. Use 'auto' to target half a pixel at "
                    f"the render scale, or pass a tolerance in the data "
                    f"CRS units."
                )
        opacity_column = self.params.get("opacity_column")
        if (opacity_column is not None and self.gdf is not None
                and opacity_column not in getattr(self.gdf, "columns", ())):
            raise ValueError(
                f"Choropleth: opacity_column {opacity_column!r} is not "
                f"a column of gdf. Available columns: "
                f"{list(self.gdf.columns)}."
            )
        blend_background = self.params.get("blend_background")
        if blend_background is not None and opacity_column is None:
            raise ValueError(
                "Choropleth: blend_background has no effect without "
                "opacity_column; pass opacity_column to drive per-feature "
                "opacity from a probability column."
            )
        # Semiology check: a choropleth maps colour value, read
        # as a relative quantity. Warn (never block) if the column looks
        # like stock data. Emitted at construction, once.
        from ..choropleth import _looks_like_stock
        column = self.params["column"]
        if self.gdf is not None and column in getattr(self.gdf, "columns", ()):
            try:
                stock_max = _looks_like_stock(
                    self.gdf[column].to_numpy(dtype=float))
            except (TypeError, ValueError):
                stock_max = None
            if stock_max is not None:
                warnings.warn(
                    f"Choropleth: column '{column}' looks like absolute "
                    f"count (stock) data: strictly positive integers "
                    f"reaching large values (max about {stock_max:.0f}) with "
                    f"a wide spread. A choropleth maps colour value, read as "
                    f"a relative quantity (rate, ratio, density). For "
                    f"absolute counts, Proportional preserves the "
                    f"magnitude. Consider normalising by area or population, "
                    f"or use Proportional.",
                    UserWarning, stacklevel=2,
                )
        # Semiology check: StdMean is a diverging classification (classes are
        # standard-deviation steps either side of the mean). A sequential
        # palette flattens that symmetry. Warn (never block) toward a
        # diverging palette.
        from ..config import DIVERGING_COLORMAPS
        method = self.params.get("method", D.CHOROPLETH_DEFAULT_METHOD)
        cmap = self.params.get("cmap", D.CHOROPLETH_DEFAULT_CMAP)
        if (isinstance(method, str) and method == "StdMean"
                and isinstance(cmap, str)
                and cmap not in DIVERGING_COLORMAPS):
            choices = ", ".join(repr(c) for c in DIVERGING_COLORMAPS)
            warnings.warn(
                f"Choropleth: method 'StdMean' is a diverging "
                f"classification (classes are standard-deviation steps either "
                f"side of the mean), but cmap {cmap!r} is sequential. A "
                f"diverging palette reads the two sides apart. Try cmap "
                f"{choices}.",
                UserWarning, stacklevel=2,
            )

    def render(self, ctx: RenderContext) -> None:
        from ..choropleth import add_choropleth as _add_choropleth
        cfg = dict(self.params)
        column = cfg.pop("column")
        layer_id = _add_choropleth(
            ctx.map, ctx.map._in_map_crs(self.gdf),
            column=column,
            cmap=cfg.pop("cmap", D.CHOROPLETH_DEFAULT_CMAP),
            reverse=cfg.pop("reverse", False),
            method=cfg.pop("method", D.CHOROPLETH_DEFAULT_METHOD),
            num_classes=cfg.pop("num_classes", D.CHOROPLETH_DEFAULT_NUM_CLASSES),
            stroke=cfg.pop("stroke", None),
            stroke_width=cfg.pop("stroke_width", None),
            legend_params=cfg.pop("legend", None),
            dissolve=cfg.pop("dissolve", False),
            simplify=cfg.pop("simplify", None),
            opacity_column=cfg.pop("opacity_column", None),
            min_opacity=cfg.pop("min_opacity", D.CHOROPLETH_DEFAULT_MIN_OPACITY),
            max_opacity=cfg.pop("max_opacity", D.CHOROPLETH_DEFAULT_MAX_OPACITY),
            blend_background=cfg.pop("blend_background", None),
            opacity_bins=cfg.pop("opacity_bins", None),
            on_zoom=cfg.pop("on_zoom", True),
            on_cartouches=cfg.pop("on_cartouches", True),
            detail=cfg.pop("detail", None),
            detail_join=cfg.pop("detail_join", None),
            border_contrast=cfg.pop("border_contrast", None),
        )
        self.report = ctx.map._state.classification_reports.get(layer_id)
        tip_gdf = self.gdf
        if self.params.get("dissolve") and self.report is not None:
            bins = self.report.bins
            tip_gdf = _class_tooltip_frame(column, [
                f"{bins[i]:g} \u2013 {bins[i + 1]:g}"
                for i in range(len(bins) - 1)])
        ctx.map._state.interactive_layers.append({
            "type": "choropleth",
            "gdf": tip_gdf,
            "column": column,
            "layer_id": layer_id,
            "id_prefix": f"choro-{layer_id}-",
        })
        self._rendered = True


@register_layer
class Category(Layer):
    """Categorical (qualitative) choropleth layer.

    Colours each polygon by a nominal category (an id, a type, a cluster
    label...) via an explicit mapping, rather than classifying a continuous
    value like :class:`Choropleth`. Opacity can separately encode a
    probability/confidence column.

    Parameters
    ----------
    gdf : GeoDataFrame
        Polygons with a category column.
    column : str
        Column holding the category per feature (required).
    fill_map : dict
        Mapping ``category -> "#RRGGBB"`` (required).
    default_fill : str, optional
        Colour for categories present in *column* but absent from
        *fill_map*. Without it, an unmapped category raises ``ValueError``.
    default_label : str, optional
        Legend label for the *default_fill* bucket (default ``"Autre"``).
    stroke : str, optional
        Outline colour of each area as ``#RRGGBB`` (default from style).
    stroke_width : float, optional
        Outline width (default from style).
    legend : dict or False, optional
        Legend configuration (ChoroplethLegendConfig fields). Defaults to
        a vertical legend with one swatch per category. ``False`` draws no
        legend.
    dissolve : bool, optional
        Merge adjacent areas that share a category before drawing
        (default False).
    simplify : None, str or float, optional
        Geometry simplification, see :class:`Choropleth`.
    opacity_column : str, optional
        Column holding a probability/confidence in ``[0, 1]``. When set,
        colour encodes the category while opacity encodes certainty
        (linearly mapped onto ``[min_opacity, max_opacity]``).
    min_opacity, max_opacity : float, optional
        Opacity bounds for *opacity_column* (defaults 0.15 and 1.0).
    blend_background : str, optional
        With *opacity_column*, pre-composite the category colour over this
        ``#RRGGBB`` background and draw an opaque solid fill instead of
        relying on SVG ``fill-opacity``.
    opacity_bins : int or list of float, optional
        Discretize *opacity_column* into this many equal-width bins over
        ``[0, 1]`` (or explicit bin edges). With *dissolve*, features
        sharing both category and opacity bin merge into one path instead
        of having their opacity averaged.
    detail : GeoDataFrame or dict, optional
        Finer geometry for the zoom window and the cartouches, drawn
        instead of the generalised one. The symbology computed from *gdf*
        is carried to it through *detail_join*. A GeoDataFrame applies to
        the zoom and every cartouche; a dict maps ``"zoom"``,
        ``"cartouches"`` or a cartouche index to a GeoDataFrame.
        See :mod:`mappyng.detail`.
    detail_join : str, tuple or None, optional
        Key shared by *gdf* and *detail*: a column name present in both,
        a ``(gdf_column, detail_column)`` pair, or None (default) to join
        on the index.
    border_contrast : bool, str, dict or BorderContrast, optional
        Make the borders between touching areas of similar colour visible:
        ``True`` redraws only those shared borders in a contrasting colour,
        ``"check"`` reveals them thick in magenta and warns, a dict or a
        :class:`~mappyng.BorderContrast` sets thresholds and colours.
        Default off. See :mod:`mappyng.border_contrast`.
    on_zoom : bool, optional
        Draw on the zoom viewport (default True).
    on_cartouches : bool, optional
        Draw on cartouche viewports (default True).
    z_index : int, optional
        Render order (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m.add(Category(
    ...     gdf, column="cluster",
    ...     fill_map={"A": "#1f78b4", "B": "#33a02c", "C": "#e31a1c"},
    ...     opacity_column="confidence",
    ... ))
    """

    #: :class:`~mappyng.choropleth_classify.CategoryReport` of the last render
    #: (features per category, excluded values); ``None`` until drawn.
    report = None

    kind = "category"
    requires_gdf = True

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        column: Any = _UNSET,
        fill_map: Any = _UNSET,
        default_fill: Any = _UNSET,
        default_label: Any = _UNSET,
        stroke: Any = _UNSET,
        stroke_width: Any = _UNSET,
        legend: Any = _UNSET,
        dissolve: Any = _UNSET,
        simplify: Any = _UNSET,
        opacity_column: Any = _UNSET,
        min_opacity: Any = _UNSET,
        max_opacity: Any = _UNSET,
        blend_background: Any = _UNSET,
        opacity_bins: Any = _UNSET,
        detail: Any = _UNSET,
        detail_join: Any = _UNSET,
        border_contrast: Any = _UNSET,
        on_zoom: Any = _UNSET,
        on_cartouches: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(
                column=column, fill_map=fill_map, default_fill=default_fill,
                default_label=default_label, stroke=stroke,
                stroke_width=stroke_width, legend=legend,
                dissolve=dissolve, simplify=simplify,
                opacity_column=opacity_column, min_opacity=min_opacity,
                max_opacity=max_opacity, blend_background=blend_background,
                opacity_bins=opacity_bins,
                detail=detail, detail_join=detail_join,
                border_contrast=border_contrast,
                on_zoom=on_zoom, on_cartouches=on_cartouches,
            ),
        )

    def validate(self) -> None:
        from ..border_contrast import parse_border_contrast
        parse_border_contrast(self.params.get("border_contrast"))
        if "column" not in self.params:
            raise ValueError(
                "Category needs a 'column' parameter naming the "
                "category column, e.g. "
                "Category(gdf, column='cluster', fill_map={...})."
            )
        if "fill_map" not in self.params:
            raise ValueError(
                "Category needs a 'fill_map' parameter mapping each "
                "category to a colour, e.g. "
                "Category(gdf, column='cluster', "
                "fill_map={'A': '#1f78b4', 'B': '#33a02c'})."
            )
        _require_column(self, self.params["column"])
        opacity_column = self.params.get("opacity_column")
        if (opacity_column is not None and self.gdf is not None
                and opacity_column not in getattr(self.gdf, "columns", ())):
            raise ValueError(
                f"Category: opacity_column {opacity_column!r} is not "
                f"a column of gdf. Available columns: "
                f"{list(self.gdf.columns)}."
            )
        blend_background = self.params.get("blend_background")
        if blend_background is not None and opacity_column is None:
            raise ValueError(
                "Category: blend_background has no effect without "
                "opacity_column; pass opacity_column to drive per-feature "
                "opacity from a probability column."
            )

    def render(self, ctx: RenderContext) -> None:
        from ..category import add_category as _add_category
        cfg = dict(self.params)
        column = cfg.pop("column")
        layer_id = _add_category(
            ctx.map, ctx.map._in_map_crs(self.gdf),
            column=column,
            fill_map=cfg.pop("fill_map"),
            default_fill=cfg.pop("default_fill", None),
            default_label=cfg.pop("default_label", "Autre"),
            stroke=cfg.pop("stroke", None),
            stroke_width=cfg.pop("stroke_width", None),
            legend_params=cfg.pop("legend", None),
            dissolve=cfg.pop("dissolve", False),
            simplify=cfg.pop("simplify", None),
            opacity_column=cfg.pop("opacity_column", None),
            min_opacity=cfg.pop("min_opacity", D.CHOROPLETH_DEFAULT_MIN_OPACITY),
            max_opacity=cfg.pop("max_opacity", D.CHOROPLETH_DEFAULT_MAX_OPACITY),
            blend_background=cfg.pop("blend_background", None),
            opacity_bins=cfg.pop("opacity_bins", None),
            on_zoom=cfg.pop("on_zoom", True),
            on_cartouches=cfg.pop("on_cartouches", True),
            detail=cfg.pop("detail", None),
            detail_join=cfg.pop("detail_join", None),
            border_contrast=cfg.pop("border_contrast", None),
        )
        self.report = ctx.map._state.classification_reports.get(layer_id)
        tip_gdf = self.gdf
        if self.params.get("dissolve") and self.report is not None:
            default_label = self.params.get("default_label", "Autre")
            tip_gdf = _class_tooltip_frame(column, [
                default_label if c == "__default__" else str(c)
                for c in self.report.categories])
        ctx.map._state.interactive_layers.append({
            "type": "category",
            "gdf": tip_gdf,
            "column": column,
            "layer_id": layer_id,
            "id_prefix": f"choro-{layer_id}-",
        })
        self._rendered = True


@register_layer
class Proportional(Layer):
    """Proportional symbols layer.

    Maps an *absolute* quantity (stock) to symbol size, preserving
    magnitude where colour value would flatten it.

    Parameters
    ----------
    gdf : GeoDataFrame
        Geometries with a numeric column.
    column : str
        Column driving symbol size (required).
    fill : str, optional
        Symbol fill colour as ``#RRGGBB`` (default from defaults).
    fill_opacity : float, optional
        Symbol fill opacity in ``[0, 1]`` (default from defaults).
    stroke : str, optional
        Symbol outline colour (default from defaults).
    stroke_width : float, optional
        Symbol outline width (default from defaults).
    max_radius : float, optional
        Radius in pixels of the largest symbol (default from defaults).
    reference_value : float, optional
        Value mapped to ``reference_radius`` for the legend. Defaults to
        the data maximum.
    reference_radius : float, optional
        Radius in pixels for ``reference_value``. Defaults to
        ``max_radius``.
    legend : dict or False, optional
        Legend configuration (see :class:`ProportionalLegendConfig`).
        ``False`` draws no legend.
    on_zoom : bool, optional
        Draw on the zoom viewport (default True).
    on_cartouches : bool, optional
        Draw on cartouche viewports (default True).
    fill_column : str, optional
        Column giving a category per feature. With *fill_map*, colours each
        circle individually so a single layer can mix colours while keeping the
        global "smallest on top" ordering (one layer per colour breaks it).
    fill_map : dict, optional
        Mapping ``category -> colour`` used with *fill_column*; unmapped
        categories fall back to *fill*.
    detail : GeoDataFrame or dict, optional
        Finer geometry for the zoom window and the cartouches, used to
        place the circles instead of the generalised one. Values and
        colours stay those of *gdf*, carried through *detail_join*. A
        GeoDataFrame applies to the zoom and every cartouche; a dict maps
        ``"zoom"``, ``"cartouches"`` or a cartouche index to a
        GeoDataFrame. See :mod:`mappyng.detail`.
    detail_join : str, tuple or None, optional
        Key shared by *gdf* and *detail*: a column name present in both,
        a ``(gdf_column, detail_column)`` pair, or None (default) to join
        on the index.
    z_index : int, optional
        Render order (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m.add(Proportional(gdf, column="population", max_radius=30))
    >>> m.add(Proportional(gdf, column="n", fill_column="type",
    ...                         fill_map={"a": "#6A1B9A", "b": "#78909C"}))
    """

    kind = "proportional"
    requires_gdf = True

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        column: Any = _UNSET,
        fill: Any = _UNSET,
        fill_opacity: Any = _UNSET,
        stroke: Any = _UNSET,
        stroke_width: Any = _UNSET,
        max_radius: Any = _UNSET,
        reference_value: Any = _UNSET,
        reference_radius: Any = _UNSET,
        legend: Any = _UNSET,
        on_zoom: Any = _UNSET,
        on_cartouches: Any = _UNSET,
        detail: Any = _UNSET,
        detail_join: Any = _UNSET,
        fill_column: Any = _UNSET,
        fill_map: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(
                column=column, fill=fill, fill_opacity=fill_opacity,
                stroke=stroke, stroke_width=stroke_width,
                max_radius=max_radius, reference_value=reference_value,
                reference_radius=reference_radius, legend=legend,
                on_zoom=on_zoom, on_cartouches=on_cartouches,
                fill_column=fill_column, fill_map=fill_map,
                detail=detail, detail_join=detail_join,
            ),
        )

    def validate(self) -> None:
        if "column" not in self.params:
            raise ValueError(
                "Proportional needs a 'column' parameter naming the "
                "numeric column that drives symbol size, e.g. "
                "Proportional(gdf, column='population')."
            )
        _require_column(self, self.params["column"])
        _require_column(self, self.params.get("fill_column"), "fill_column")

    def render(self, ctx: RenderContext) -> None:
        from ..proportional import add_proportional as _add_proportional
        cfg = dict(self.params)
        column = cfg.pop("column")
        layer_id = _add_proportional(
            ctx.map, ctx.map._in_map_crs(self.gdf),
            column=column,
            fill=cfg.pop("fill", D.PROPORTIONAL_FILL),
            fill_opacity=cfg.pop("fill_opacity", D.PROPORTIONAL_FILL_OPACITY),
            stroke=cfg.pop("stroke", D.PROPORTIONAL_STROKE),
            stroke_width=cfg.pop("stroke_width", D.PROPORTIONAL_STROKE_WIDTH),
            max_radius=cfg.pop("max_radius", D.PROPORTIONAL_MAX_RADIUS),
            reference_value=cfg.pop("reference_value", None),
            reference_radius=cfg.pop("reference_radius", None),
            legend_params=cfg.pop("legend", None),
            on_zoom=cfg.pop("on_zoom", True),
            on_cartouches=cfg.pop("on_cartouches", True),
            detail=cfg.pop("detail", None),
            detail_join=cfg.pop("detail_join", None),
            fill_column=cfg.pop("fill_column", None),
            fill_map=cfg.pop("fill_map", None),
        )
        ctx.map._state.interactive_layers.append({
            "type": "proportional",
            "gdf": self.gdf,
            "column": column,
            "layer_id": layer_id,
            "id_prefix": f"prop-{layer_id}-",
        })
        self._rendered = True


@register_layer
class Situation(Layer):
    """Situation (qualitative point/area) layer.

    Parameters
    ----------
    gdf : GeoDataFrame
        Geometries to draw.
    column : str, optional
        Category column. When set together with ``symbol``, each category
        gets its own marker.
    symbol : dict, optional
        Mapping of category value to a per-category marker style.
    marker : str, optional
        Marker shape used in uniform mode (default ``"circle"``).
    fill : str, optional
        Marker fill colour as ``#RRGGBB`` (default ``"#e31a1c"``).
    size : float, optional
        Marker size in pixels (default 8).
    stroke : str, optional
        Marker outline colour (default ``"#ffffff"``).
    stroke_width : float, optional
        Marker outline width (default 0.5).
    fill_opacity : float, optional
        Marker fill opacity in ``[0, 1]`` (default 1).
    inner_fill : str, optional
        Fill colour of an inner marker, for layered symbols.
    inner_stroke : str, optional
        Outline colour of the inner marker.
    label : str, optional
        Column holding a short text drawn next to each marker.
    legend : dict or False, optional
        Legend configuration (see :class:`SituationLegendConfig`).
        ``None`` or ``False`` draws no legend.
    on_zoom : bool, optional
        Draw on the zoom viewport (default True).
    on_cartouches : bool, optional
        Draw on cartouche viewports (default True).
    detail : GeoDataFrame or dict, optional
        Finer geometry for the zoom window and the cartouches, used to
        place the markers instead of the generalised one. Values and
        colours stay those of *gdf*, carried through *detail_join*. A
        GeoDataFrame applies to the zoom and every cartouche; a dict maps
        ``"zoom"``, ``"cartouches"`` or a cartouche index to a
        GeoDataFrame. See :mod:`mappyng.detail`.
    detail_join : str, tuple or None, optional
        Key shared by *gdf* and *detail*: a column name present in both,
        a ``(gdf_column, detail_column)`` pair, or None (default) to join
        on the index.
    z_index : int, optional
        Render order (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m.add(Situation(gdf, marker="square", fill="#1f78b4"))
    """

    kind = "situation"
    requires_gdf = True

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        column: Any = _UNSET,
        symbol: Any = _UNSET,
        marker: Any = _UNSET,
        fill: Any = _UNSET,
        size: Any = _UNSET,
        stroke: Any = _UNSET,
        stroke_width: Any = _UNSET,
        fill_opacity: Any = _UNSET,
        inner_fill: Any = _UNSET,
        inner_stroke: Any = _UNSET,
        label: Any = _UNSET,
        legend: Any = _UNSET,
        on_zoom: Any = _UNSET,
        on_cartouches: Any = _UNSET,
        detail: Any = _UNSET,
        detail_join: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(
                column=column, symbol=symbol, marker=marker, fill=fill,
                size=size, stroke=stroke, stroke_width=stroke_width,
                fill_opacity=fill_opacity, inner_fill=inner_fill,
                inner_stroke=inner_stroke, label=label, legend=legend,
                on_zoom=on_zoom, on_cartouches=on_cartouches,
                detail=detail, detail_join=detail_join,
            ),
        )

    def validate(self) -> None:
        # Semiology check: too many categorical symbols hurt
        # readability. Warn (never block) at construction.
        symbol = self.params.get("symbol")
        column = self.params.get("column")
        if column and symbol and len(symbol) > D.SITUATION_MAX_CATEGORIES_WARN:
            warnings.warn(
                f"Situation: {len(symbol)} categories defined. The human "
                f"eye reliably distinguishes about "
                f"{D.SITUATION_MAX_CATEGORIES_WARN} categorical symbols on a "
                f"single map; beyond that, readability drops. Consider "
                f"grouping categories or splitting the map.",
                UserWarning, stacklevel=2,
            )

    def render(self, ctx: RenderContext) -> None:
        from ..situation import add_situation as _add_situation
        cfg = dict(self.params)
        column = cfg.pop("column", None)
        layer_id = _add_situation(
            ctx.map, ctx.map._in_map_crs(self.gdf),
            column=column,
            symbol=cfg.pop("symbol", None),
            marker=cfg.pop("marker", "circle"),
            fill=cfg.pop("fill", "#e31a1c"),
            size=cfg.pop("size", 8.0),
            stroke=cfg.pop("stroke", "#ffffff"),
            stroke_width=cfg.pop("stroke_width", 0.5),
            fill_opacity=cfg.pop("fill_opacity", 1.0),
            inner_fill=cfg.pop("inner_fill", None),
            inner_stroke=cfg.pop("inner_stroke", None),
            label=cfg.pop("label", None),
            legend_params=cfg.pop("legend", None),
            on_zoom=cfg.pop("on_zoom", True),
            on_cartouches=cfg.pop("on_cartouches", True),
            detail=cfg.pop("detail", None),
            detail_join=cfg.pop("detail_join", None),
        )
        ctx.map._state.interactive_layers.append({
            "type": "situation",
            "gdf": self.gdf,
            "column": column,
            "layer_id": layer_id,
            "id_prefix": f"situ-{layer_id}-",
        })
        self._rendered = True


@register_layer
class Label(Layer):
    """Text label layer placed by simulated annealing.

    Parameters
    ----------
    gdf : GeoDataFrame
        Geometries to label.
    column : str
        Column holding the label text (required).
    target : str, optional
        Viewport to place labels on: ``"main"`` (default), ``"zoom"`` or
        ``"cartouche:<index>"``.
    font_size : float, optional
        Label font size in pixels (default 10).
    font_family : str, optional
        Font family (default ``"sans-serif"``).
    font_weight : str, optional
        Font weight (default ``"normal"``).
    color : str, optional
        Text colour as ``#RRGGBB`` (default ``"#000000"``).
    halo_color : str or None, optional
        Halo (outline) colour; ``None`` disables the halo.
    halo_width : float, optional
        Halo width in pixels (default 2).
    priority_col : str, optional
        Column ranking which labels are placed first (higher first).
    min_priority : float, optional
        Skip rows whose priority is below this threshold.
    max_labels : int, optional
        Hard cap on the number of labels placed.
    initial_position : str, optional
        Starting candidate position (default ``"NE"``).
    candidate_positions : list of str, optional
        Candidate positions tried around each anchor.
    label_offset : float, optional
        Distance from anchor to label edge in pixels (default 4).
    max_displacement : float, optional
        Maximum displacement before a label is hidden (default 40).
    avoid_overlap : bool, optional
        Enable label-label overlap avoidance (default True).
    allow_hide : bool, optional
        Allow hiding labels that cannot be placed (default True). A label
        that still covers a map symbol after placement is hidden too.
    allow_symbol_overlap : bool, optional
        Keep labels that cover a map symbol instead of hiding them
        (default False). Useful on dense maps where most labels would be
        hidden.
    leader_lines : bool, optional
        Draw leader lines for displaced labels (default True).
    leader_threshold : float, optional
        Displacement (in label heights) that triggers a leader line.
    leader_color : str, optional
        Leader line colour (default ``"#666666"``).
    leader_width : float, optional
        Leader line width (default 0.5).
    wrap : bool, optional
        Wrap long labels at dashes (default True).
    wrap_max_chars : int, optional
        Maximum characters per line before wrapping (default 12).
    numbered_above : int, optional
        Switch to numbered-circle mode past this label count.
    numbered_legend_position : dict, optional
        Legend placement ``{"x": frac, "y": frac}`` in figure fractions.
    numbered_circle_r : float, optional
        Numbered circle radius in pixels (default 5).
    numbered_circle_fill : str, optional
        Numbered circle fill colour (default ``"#ffffff"``).
    numbered_circle_stroke : str, optional
        Numbered circle outline colour (default ``"#333333"``).
    numbered_legend_bg : str, optional
        Numbered legend background colour (default ``"white"``).
    numbered_legend_bg_opacity : float, optional
        Numbered legend background opacity (default 0.88).
    numbered_legend_border : str, optional
        Numbered legend border colour (default ``"#cccccc"``).
    numbered_legend_title : str, optional
        Numbered legend title text.
    n_sweeps : int, optional
        Number of annealing sweeps (default 50).
    initial_temperature : float, optional
        Annealing start temperature (default 1.0).
    final_temperature : float, optional
        Annealing end temperature (default 0.01).
    seed : int, optional
        Random seed for reproducible placement. Defaults to the map seed.
    w_LL, w_LO, w_LC, w_LA, w_D, w_OR, w_OOB : float, optional
        Energy weights tuning the placement: label-label, label-obstacle,
        label-chrome, label-anchor, distance, orientation bias and
        out-of-bounds penalties.
    detail : GeoDataFrame or dict, optional
        Finer geometry used to place the labels of a zoom or cartouche
        *target* instead of the generalised one. Text and priority stay
        those of *gdf*, carried through *detail_join*; a unit made of
        several finer parts is labelled once. A GeoDataFrame applies to a
        zoom or cartouche target; a dict maps ``"zoom"``, ``"cartouches"``
        or a cartouche index to a GeoDataFrame. Ignored for the main map.
        See :mod:`mappyng.detail`.
    detail_join : str, tuple or None, optional
        Key shared by *gdf* and *detail*: a column name present in both,
        a ``(gdf_column, detail_column)`` pair, or None (default) to join
        on the index.
    z_index : int, optional
        Render order (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m.add(Label(gdf, column="name", priority_col="population",
    ...                  max_labels=20, font_size=9))
    """

    kind = "labels"
    requires_gdf = True

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        column: Any = _UNSET,
        target: Any = _UNSET,
        font_size: Any = _UNSET,
        font_family: Any = _UNSET,
        font_weight: Any = _UNSET,
        color: Any = _UNSET,
        halo_color: Any = _UNSET,
        halo_width: Any = _UNSET,
        priority_col: Any = _UNSET,
        min_priority: Any = _UNSET,
        max_labels: Any = _UNSET,
        initial_position: Any = _UNSET,
        candidate_positions: Any = _UNSET,
        label_offset: Any = _UNSET,
        max_displacement: Any = _UNSET,
        avoid_overlap: Any = _UNSET,
        allow_hide: Any = _UNSET,
        allow_symbol_overlap: Any = _UNSET,
        leader_lines: Any = _UNSET,
        leader_threshold: Any = _UNSET,
        leader_color: Any = _UNSET,
        leader_width: Any = _UNSET,
        wrap: Any = _UNSET,
        wrap_max_chars: Any = _UNSET,
        numbered_above: Any = _UNSET,
        numbered_legend_position: Any = _UNSET,
        numbered_circle_r: Any = _UNSET,
        numbered_circle_fill: Any = _UNSET,
        numbered_circle_stroke: Any = _UNSET,
        numbered_legend_bg: Any = _UNSET,
        numbered_legend_bg_opacity: Any = _UNSET,
        numbered_legend_border: Any = _UNSET,
        numbered_legend_title: Any = _UNSET,
        n_sweeps: Any = _UNSET,
        initial_temperature: Any = _UNSET,
        final_temperature: Any = _UNSET,
        seed: Any = _UNSET,
        w_LL: Any = _UNSET,
        w_LO: Any = _UNSET,
        w_LC: Any = _UNSET,
        w_LA: Any = _UNSET,
        w_D: Any = _UNSET,
        w_OR: Any = _UNSET,
        w_OOB: Any = _UNSET,
        detail: Any = _UNSET,
        detail_join: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(
                column=column, target=target, font_size=font_size,
                font_family=font_family, font_weight=font_weight,
                color=color, halo_color=halo_color, halo_width=halo_width,
                priority_col=priority_col, min_priority=min_priority,
                max_labels=max_labels, initial_position=initial_position,
                candidate_positions=candidate_positions,
                label_offset=label_offset,
                max_displacement=max_displacement,
                avoid_overlap=avoid_overlap, allow_hide=allow_hide,
                allow_symbol_overlap=allow_symbol_overlap,
                leader_lines=leader_lines, leader_threshold=leader_threshold,
                leader_color=leader_color, leader_width=leader_width,
                wrap=wrap, wrap_max_chars=wrap_max_chars,
                numbered_above=numbered_above,
                numbered_legend_position=numbered_legend_position,
                numbered_circle_r=numbered_circle_r,
                numbered_circle_fill=numbered_circle_fill,
                numbered_circle_stroke=numbered_circle_stroke,
                numbered_legend_bg=numbered_legend_bg,
                numbered_legend_bg_opacity=numbered_legend_bg_opacity,
                numbered_legend_border=numbered_legend_border,
                numbered_legend_title=numbered_legend_title,
                n_sweeps=n_sweeps, initial_temperature=initial_temperature,
                final_temperature=final_temperature, seed=seed,
                w_LL=w_LL, w_LO=w_LO, w_LC=w_LC, w_LA=w_LA, w_D=w_D,
                w_OR=w_OR, w_OOB=w_OOB,
                detail=detail, detail_join=detail_join,
            ),
        )

    def validate(self) -> None:
        if "column" not in self.params:
            raise ValueError(
                "Label needs a 'column' parameter naming the text "
                "column to label with, e.g. "
                "Label(gdf, column='name')."
            )
        _require_column(self, self.params["column"])
        _require_column(self, self.params.get("priority_col"), "priority_col")

    def render(self, ctx: RenderContext) -> None:
        params = dict(self.params)
        column = params.pop("column")
        ctx.map._render_labels(self.gdf, column, **params)
        self._rendered = True


@register_layer
class Vector(Layer):
    """Raw vector layer drawn with explicit styling.

    Parameters
    ----------
    gdf : GeoDataFrame
        Geometries to draw.
    position : str, optional
        ``"background"`` (default) or ``"top"`` relative to the data.
        Without ``position`` or ``z``, a positive ``z_index`` implies
        ``"top"``.
    z : int, optional
        Explicit stacking order, overriding ``position``.
    fill : str, optional
        Fill colour as ``#RRGGBB`` (default ``"none"``).
    stroke : str, optional
        Stroke colour (default from style).
    stroke_width : float, optional
        Stroke width (default from style).
    fill_opacity : float, optional
        Fill opacity in ``[0, 1]``.
    stroke_opacity : float, optional
        Stroke opacity in ``[0, 1]``. A wide faint stroke under a thin
        bright one fakes a glowing line.
    stroke_linecap : str, optional
        ``"butt"``, ``"round"`` or ``"square"``.
    stroke_dasharray : str, optional
        SVG dash pattern, e.g. ``"4 2"``.
    detail : GeoDataFrame or dict, optional
        Finer geometry drawn instead of *gdf* on the zoom window and the
        cartouches (see :class:`Choropleth`). No join is needed: the
        finer geometries replace *gdf*'s.
    on_zoom : bool, optional
        Draw on the zoom viewport (default False).
    on_cartouches : bool, optional
        Draw on cartouche viewports (default True).
    z_index : int, optional
        Render order among layers (default 0).
    visible : bool, optional
        Whether the layer is drawn (default True).

    Examples
    --------
    >>> m.add(Vector(gdf, stroke="#333", stroke_width=0.4, position="top"))
    """

    kind = "vector"
    requires_gdf = True

    def __init__(
        self,
        gdf: Any | None = None,
        *,
        position: Any = _UNSET,
        z: Any = _UNSET,
        fill: Any = _UNSET,
        stroke: Any = _UNSET,
        stroke_width: Any = _UNSET,
        fill_opacity: Any = _UNSET,
        stroke_opacity: Any = _UNSET,
        stroke_linecap: Any = _UNSET,
        stroke_dasharray: Any = _UNSET,
        detail: Any = _UNSET,
        on_zoom: Any = _UNSET,
        on_cartouches: Any = _UNSET,
        z_index: int = 0,
        visible: bool = True,
    ) -> None:
        super().__init__(
            gdf, z_index=z_index, visible=visible,
            **collect_set(
                position=position, z=z, fill=fill, stroke=stroke,
                stroke_width=stroke_width, fill_opacity=fill_opacity,
                stroke_opacity=stroke_opacity, stroke_linecap=stroke_linecap,
                detail=detail,
                stroke_dasharray=stroke_dasharray, on_zoom=on_zoom,
                on_cartouches=on_cartouches,
            ),
        )

    def render(self, ctx: RenderContext) -> None:
        params = dict(self.params)
        # A raised z_index lifts the layer above the data, like position="top".
        if self.z_index > 0 and "z" not in params and "position" not in params:
            params["position"] = "top"
        ctx.map._render_vector(ctx.map._in_map_crs(self.gdf), params)
        self._rendered = True
