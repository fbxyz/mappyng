"""Attributes and methods that the Map mixins rely on, declared for type checkers.

``BackgroundMixin`` and ``ChromeMixin`` are mixins of :class:`mappyng.map.Map`
and use its state (``self.main``, ``self.svg``, ``self.gdf``...). Declaring
them here, in a common base class, lets a type checker follow those accesses.
The annotations create no attribute at runtime, and the method stubs exist
only under ``TYPE_CHECKING``: the real values and methods are those of
``Map``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import geopandas as gpd

    from ._state import MapState
    from .config import Style
    from .overflow import OverflowRegistry
    from .renderer import SvgDocument, SvgViewport


class MapBase:
    """Declares the ``Map`` members used by the mixins (see module docstring)."""

    gdf: gpd.GeoDataFrame
    bbox: list[float]
    width: float
    height: float
    padding: float
    style: Style
    font_scale: float
    basemap_color: str | None
    svg: SvgDocument
    main: SvgViewport
    cartouche_params: dict[int, Any]
    _cartouche_viewports: dict[int, SvgViewport]
    _zoom_viewport: SvgViewport | None
    _zoom_bbox: list[float] | None
    _state: MapState

    if TYPE_CHECKING:
        @property
        def overflow(self) -> OverflowRegistry: ...

        def add(self, *items: Any) -> Any: ...

        def _next_layer_id(self, kind: str) -> int: ...

        def _clip_gdf(self, gdf: gpd.GeoDataFrame,
                      bbox: list[float]) -> gpd.GeoDataFrame: ...

        def _prepare_cartouche_data(self, gdf: gpd.GeoDataFrame,
                                    params: dict[str, Any]
                                    ) -> gpd.GeoDataFrame: ...
