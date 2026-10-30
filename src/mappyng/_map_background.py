"""Background layers of a Map: basemap, graticule, tiles, raster, vector, shadow, gradients.

Mixin for :class:`mappyng.map.Map`; methods rely on Map attributes."""

from __future__ import annotations

import warnings
import xml.etree.ElementTree as ET
from typing import Any

import geopandas as gpd
import shapely
from shapely.geometry import box

from . import defaults as D
from ._map_base import MapBase
from .detail import ZOOM, detail_for, normalize_detail
from .errors import GEO_ERRORS


class BackgroundMixin(MapBase):
    """Background layers of a Map: basemap, graticule, tiles, raster, vector, shadow, gradients."""

    # ------------------------------------------------------------------
    # Basemap
    # ------------------------------------------------------------------

    def _detail_in_map_crs(self, detail: Any) -> dict[Any, Any]:
        """Normalise a ``detail`` parameter and bring it to the map CRS."""
        details = normalize_detail(detail)
        map_crs = self.gdf.crs
        if map_crs is None:
            return details
        return {
            key: (g.to_crs(map_crs) if g.crs is not None and g.crs != map_crs
                  else g)
            for key, g in details.items()
        }

    def _render_basemap(self, fill: str | None = None,
                    stroke: str | None = None,
                    stroke_width: float | None = None,
                    detail: Any = None) -> None:
        """Draw the basemap polygons on the main viewport and all cartouches.

        Parameters
        ----------
        fill : str, optional
            Fill color (default from style or basemap_color override).
        stroke : str, optional
            Outline color (default from style).
        stroke_width : float, optional
            Outline width (default from style).
        detail : GeoDataFrame or dict, optional
            Finer geometry used instead of the map's GeoDataFrame on the
            zoom window and the cartouches. See :mod:`mappyng.detail`.
        """
        details = self._detail_in_map_crs(detail)
        fill = fill or self.basemap_color or self.style["basemap_fill_color"]
        stroke = stroke or self.style["basemap_edge_color"]
        sw = stroke_width or self.style["basemap_edge_width"]
        z = self.style.config.z_order.BASEMAP
        attrs = dict(fill=fill, stroke=stroke, stroke_width=sw)

        # Main map, clip to bbox
        gdf_clip = self._clip_gdf(self.gdf, self.bbox)
        if not gdf_clip.empty:
            self.main.draw_geodataframe("basemap", gdf_clip, z_order=z, **attrs)

        # Cartouches
        for index, vp in self._cartouche_viewports.items():
            params = self.cartouche_params[index]
            finer = detail_for(details, index)
            cart_gdf = self._prepare_cartouche_data(
                self.gdf if finer is None else finer, params)
            if not cart_gdf.empty:
                vp.draw_geodataframe("basemap", cart_gdf, z_order=z, **attrs)

        # Zoom
        if self._zoom_viewport and self._zoom_bbox:
            finer = detail_for(details, ZOOM)
            zoom_gdf = self._clip_gdf(
                self.gdf if finer is None else finer, self._zoom_bbox)
            if not zoom_gdf.empty:
                self._zoom_viewport.draw_geodataframe(
                    "basemap", zoom_gdf, z_order=z, **attrs)

    # ------------------------------------------------------------------
    # Graticules
    # ------------------------------------------------------------------

    def _render_graticule(self, params: dict[str, Any] | None = None) -> None:
        """Draw graticule lines (meridians and parallels) on all viewports.

        Parameters
        ----------
        params : dict, optional
            - ``step`` (float): spacing in degrees (default 10.0).
            - ``stroke`` (str): line color (default ``'#aaaaaa'``).
            - ``opacity`` (float): stroke opacity (default 0.5).
            - ``stroke_width`` (float): line width (default 0.5).
            - ``dash`` (str): SVG stroke-dasharray (default ``'4 2'``).
            - ``position`` (str): ``'background'`` (default) draws the
              graticule above the ocean but below the basemap and data;
              ``'top'`` draws it over everything, which suits globe-style
              maps where the grid should cross the continents.
            - ``z`` (int): explicit stacking order, overriding
              ``position``. Lets the grid be slotted between custom
              layers, e.g. above an ocean fill but below the land.

        Example::

            m.add(Graticule(step=5.0, stroke="#888888", opacity=0.4))
        """
        cfg = params or {}
        step = float(cfg.get("step", 10.0))
        stroke = cfg.get("stroke", "#aaaaaa")
        opacity = float(cfg.get("opacity", 0.5))
        stroke_width = float(cfg.get("stroke_width", 0.5))
        dash = cfg.get("dash", "4 2")
        position = cfg.get("position", "background")
        z_override = cfg.get("z", None)
        if z_override is not None:
            z = int(z_override)
        elif position == "top":
            z = self.style.config.z_order.LAYER_TOP
        else:
            z = self.style.config.z_order.GRATICULES
        attrs = dict(fill="none", stroke=stroke, stroke_width=stroke_width,
                     stroke_opacity=opacity, stroke_dasharray=dash)

        # Main viewport
        grat = self._build_graticule_gdf(self.bbox, self.gdf.crs, step)
        if grat is not None and not grat.empty:
            clipped = self._clip_gdf(grat, self.bbox)
            if not clipped.empty:
                self.main.draw_geodataframe("graticule", clipped, z_order=z, **attrs)

        # Zoom viewport
        if self._zoom_viewport and self._zoom_bbox:
            grat_z = self._build_graticule_gdf(self._zoom_bbox, self.gdf.crs, step)
            if grat_z is not None and not grat_z.empty:
                clipped_z = self._clip_gdf(grat_z, self._zoom_bbox)
                if not clipped_z.empty:
                    self._zoom_viewport.draw_geodataframe(
                        "graticule", clipped_z, z_order=z, **attrs)

        # Cartouche viewports
        for index, vp in self._cartouche_viewports.items():
            cart_params = self.cartouche_params[index]
            cart_crs = cart_params.get("crs") or self.gdf.crs
            cart_bbox = cart_params.get("bbox") or self.bbox
            grat_c = self._build_graticule_gdf(cart_bbox, cart_crs, step)
            if grat_c is not None and not grat_c.empty:
                clip_box = box(*cart_bbox)
                try:
                    clipped_c = grat_c.clip(mask=clip_box)
                    clipped_c = clipped_c[~clipped_c.is_empty]
                except GEO_ERRORS as e:
                    warnings.warn(
                        f"Graticule: clipping to the cartouche failed ({e}); "
                        f"the graticule is drawn unclipped."
                    )
                    clipped_c = grat_c
                if not clipped_c.empty:
                    vp.draw_geodataframe("graticule", clipped_c, z_order=z, **attrs)

    def _build_graticule_gdf(self, bbox: list[float], crs: Any,
                              step: float) -> gpd.GeoDataFrame | None:
        """Generate meridian + parallel lines in the map CRS, clipped to bbox.

        Each line is generated in EPSG:4326 with intermediate points and then
        reprojected, so meridians and parallels bend correctly in curved
        projections (for example orthographic). Projections whose frame
        cannot be expressed as a lon/lat box (the orthographic disc reprojects
        to an infinite extent) fall back to the whole globe; vertices that
        land on invalid coordinates (the hidden hemisphere) are dropped, and
        each line is split into its visible segments.

        Returns None if too many lines would be produced (>1000).
        """
        import numpy as np
        from shapely.geometry import LineString

        # Reproject bbox corners to EPSG:4326 to find the lat/lon extent.
        try:
            bbox_gdf = gpd.GeoDataFrame(
                geometry=[box(*bbox)], crs=crs
            ).to_crs("EPSG:4326")
            b = bbox_gdf.total_bounds  # [minx, miny, maxx, maxy] in lon/lat
        except GEO_ERRORS:
            warnings.warn(
                "Graticule: could not reproject the map bbox to "
                "EPSG:4326, so no graticule was drawn. Check that the map "
                "data has a CRS set."
            )
            return None

        if not np.all(np.isfinite(b)):
            # The frame has no finite lon/lat box (e.g. an orthographic disc
            # whose corners fall beyond the limb): cover the whole globe and
            # let the invalid-vertex pruning below keep the visible part.
            lon_min, lat_min, lon_max, lat_max = -180.0, -90.0, 180.0, 90.0
        else:
            lon_min, lat_min, lon_max, lat_max = b

        # Extend slightly beyond bbox for clean line coverage.
        pad = step * 0.1

        lon_ticks = np.arange(
            np.ceil((lon_min - pad) / step) * step,
            lon_max + pad + step,
            step,
        )
        lat_ticks = np.arange(
            np.ceil((lat_min - pad) / step) * step,
            lat_max + pad + step,
            step,
        )

        # Clamp to valid lat/lon range. Parallels at the poles are degenerate.
        lon_ticks = lon_ticks[(lon_ticks >= -180) & (lon_ticks <= 180)]
        lat_ticks = lat_ticks[(lat_ticks > -90) & (lat_ticks < 90)]

        # Densify each line so it follows the projection's curvature. The
        # along-line sampling stays clamped just inside the poles.
        lat_lo, lat_hi = max(lat_min - pad, -89.5), min(lat_max + pad, 89.5)
        lon_lo, lon_hi = max(lon_min - pad, -180.0), min(lon_max + pad, 180.0)
        lat_samples = np.linspace(lat_lo, lat_hi,
                                  max(2, int((lat_hi - lat_lo) / 2) + 1))
        lon_samples = np.linspace(lon_lo, lon_hi,
                                  max(2, int((lon_hi - lon_lo) / 2) + 1))

        lines = []
        for lon in lon_ticks:
            lines.append(LineString([(lon, la) for la in lat_samples]))
        for lat in lat_ticks:
            lines.append(LineString([(lo, lat) for lo in lon_samples]))

        if len(lines) > 1000:
            warnings.warn(
                "Graticule: the requested 'step' would draw over 1000 "
                "lines, so the graticule was skipped. Increase 'step' (the "
                "spacing in degrees between graticule lines)."
            )
            return None
        if not lines:
            return None

        gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:4326")
        try:
            gdf = gdf.to_crs(crs)
        except GEO_ERRORS as e:
            warnings.warn(
                f"Graticule: reprojecting the graticule to the map CRS "
                f"failed ({e}); no graticule was drawn."
            )
            return None

        return self._prune_nonfinite_lines(gdf)

    @staticmethod
    def _prune_nonfinite_lines(
        gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame | None:
        """Drop non-finite vertices and split lines into their finite runs.

        Curved projections (orthographic) send hidden-hemisphere points to
        infinite coordinates. Keeping only the contiguous runs of finite
        vertices leaves the visible arcs of each meridian and parallel.
        """
        import numpy as np
        from shapely.geometry import LineString

        out = []
        for geom in gdf.geometry:
            if geom is None or geom.is_empty:
                continue
            parts = (geom.geoms if geom.geom_type == "MultiLineString"
                     else [geom])
            for part in parts:
                coords = np.asarray(part.coords)
                finite = np.isfinite(coords).all(axis=1)
                run = []
                for keep, xy in zip(finite, coords):
                    if keep:
                        run.append((xy[0], xy[1]))
                    elif len(run) >= 2:
                        out.append(LineString(run))
                        run = []
                    else:
                        run = []
                if len(run) >= 2:
                    out.append(LineString(run))

        if not out:
            return None
        return gpd.GeoDataFrame(geometry=out, crs=gdf.crs)

    # ------------------------------------------------------------------
    # Tiles
    # ------------------------------------------------------------------

    def _render_tile(self, params: dict[str, Any] | None = None) -> None:
        """Add a web tile basemap (OpenStreetMap, CartoDB, ESRI, Stadia...).

        Tiles are downloaded in XYZ format, assembled with Pillow, and
        embedded as base64 PNG ``<image>`` elements.  The tile mosaic is
        placed below the basemap by default (z_order < 0).

        Requires: ``pip install mercantile Pillow``

        Parameters (dict keys)
        ----------------------
        source : str, default ``"cartodb_positron"``
            Provider alias or custom URL template with ``{x}``, ``{y}``,
            ``{z}`` placeholders.  Built-in aliases:

            - OpenStreetMap: ``"openstreetmap"`` / ``"osm"``
            - CartoDB: ``"cartodb_positron"`` / ``"positron"``,
              ``"cartodb_darkmatter"`` / ``"darkmatter"``,
              ``"cartodb_voyager"`` / ``"voyager"``
            - Stadia/Stamen: ``"terrain"``, ``"toner"``, ``"watercolor"``
            - ESRI: ``"satellite"`` / ``"esri_worldimagery"``,
              ``"esri_worldstreet"``, ``"esri_natgeo"``, ``"esri_ocean"``
            - OpenTopoMap: ``"opentopomap"`` / ``"topo"``
        zoom : int or ``"auto"``
            Zoom level (``"auto"`` picks the smallest zoom where the map
            area spans at least the viewport width in tile pixels).
        zoom_offset : int, default 0
            Added to the auto-calculated zoom level (e.g. ``-1`` to fetch
            lighter, ``+1`` for more detail).
        opacity : float, default 1.0
            Tile opacity (0 = transparent, 1 = opaque).
        on_cartouches : bool, default True
            Render tiles on cartouche viewports.
        on_zoom : bool, default True
            Render tiles on the zoom viewport.
        cache : bool, default True
            Cache tiles on disk in ``~/.cache/mappyng/tiles``.
        max_tiles : int, default 64
            Safety cap on tiles downloaded per viewport.
        extra_zoom_levels : int, default 0
            Number of coarser zoom levels to also fetch (0-3 recommended).
            Levels are composited coarse to fine: finer tiles overwrite
            coarser ones where they exist; coarser tiles fill gaps where
            finer downloads failed.  Example: if auto-zoom is 8 and
            ``extra_zoom_levels=2``, levels 6, 7, 8 are fetched and blended.

        Examples::

            m.add(Tile())                          # CartoDB Positron, auto-zoom
            m.add(Tile(source="satellite"))        # ESRI imagery
            m.add(Tile(source="terrain", opacity=0.7, zoom_offset=-1))
            m.add(Tile(source="https://tile.openstreetmap.org/{z}/{x}/{y}.png"))
        """
        from .tile import TileConfig
        from .tile import add_tile as _add_tile

        cfg_dict = dict(params or {})
        cfg = TileConfig(**cfg_dict)
        _add_tile(self, cfg)

    # ------------------------------------------------------------------
    # Raster
    # ------------------------------------------------------------------

    def _render_raster(self, params: dict[str, Any]) -> None:
        """Add raster backgrounds (GeoTIFF) to the map.

        Each viewport picks the raster file whose geographic footprint
        overlaps its bbox, so ``antilles.tif`` is used for Guadeloupe
        and Martinique cartouches, ``reunion.tif`` for Réunion, etc.

        Parameters (dict keys)
        ----------------------
        paths : dict
            Region name to GeoTIFF path. Example::

                {
                    "metropole": "data/MNT/BDTOPO2018_gen3_NC.tif",
                    "antilles":  "data/MNT/antilles.tif",
                    "guyane":    "data/MNT/guyane.tif",
                    "reunion":   "data/MNT/reunion.tif",
                }
        opacity : float
            Raster opacity 0-1 (default 1.0).
        on_zoom : bool
            Render on zoom viewport (default True).
        on_cartouches : bool
            Render on cartouche viewports (default True).

        Example::

            m.add(Raster(
                paths={
                    "metropole": "data/MNT/BDTOPO2018_gen3_NC.tif",
                    "antilles":  "data/MNT/antilles.tif",
                },
                opacity=0.6,
            ))
        """
        from .raster import add_raster as _add_raster

        cfg = dict(params)
        _add_raster(
            self,
            paths=cfg.pop("paths"),
            opacity=cfg.pop("opacity", 1.0),
            on_zoom=cfg.pop("on_zoom", True),
            on_cartouches=cfg.pop("on_cartouches", True),
            z=cfg.pop("z", None),
        )

    def _get_main_crs(self):
        """Return the CRS EPSG code of the base GeoDataFrame."""
        if self.gdf.crs is None:
            return 4326
        try:
            return self.gdf.crs.to_epsg()
        except GEO_ERRORS:
            return self.gdf.crs

    # ------------------------------------------------------------------
    # Layers
    # ------------------------------------------------------------------

    def _render_vector(self, gdf: gpd.GeoDataFrame,
                       params: dict[str, Any] | None = None) -> None:
        """Add an extra vector layer.

        Parameters
        ----------
        gdf : GeoDataFrame
            Geometries to draw.
        params : dict, optional
            Layer configuration:

            - ``position`` (str): ``'top'`` or ``'background'``
              (default ``'background'``).
            - ``z`` (int): explicit stacking order, overriding
              ``position``. Useful to interleave custom layers, e.g. a
              graticule between an ocean fill and the land.
            - ``fill`` (str): fill color (default ``'none'``).
            - ``stroke`` (str): stroke color.
            - ``stroke_width`` (float): stroke width.
            - ``fill_opacity`` (float): fill opacity.
            - ``stroke_opacity`` (float): stroke opacity. Drawing a wide,
              faint stroke under a thin bright one fakes a glowing line.
            - ``stroke_linecap`` (str): ``'butt'``, ``'round'`` or
              ``'square'``.
            - ``stroke_dasharray`` (str): SVG dash pattern, e.g. ``'4 2'``.
            - ``on_zoom`` (bool): render on zoom (default False).
            - ``on_cartouches`` (bool): render on cartouches (default True).
            - ``detail`` (GeoDataFrame or dict): finer geometry drawn instead
              of *gdf* on the zoom window and the cartouches. See
              :mod:`mappyng.detail`.

        Example::

            m.add(Vector(gdf_reg, stroke="#333", stroke_width=0.4,
                         position="top"))
        """
        cfg = dict(params or {})
        position = cfg.pop("position", "background")
        fill = cfg.pop("fill", "none")
        stroke = cfg.pop("stroke", None) or self.style["edge_color"]
        stroke_width = cfg.pop("stroke_width", None) or self.style["edge_width"]
        fill_opacity = cfg.pop("fill_opacity", None)
        stroke_opacity = cfg.pop("stroke_opacity", None)
        stroke_linecap = cfg.pop("stroke_linecap", None)
        stroke_dasharray = cfg.pop("stroke_dasharray", None)
        on_zoom = cfg.pop("on_zoom", False)
        on_cartouches = cfg.pop("on_cartouches", True)
        details = self._detail_in_map_crs(cfg.pop("detail", None))

        z = self.style.config.z_order
        z_override = cfg.pop("z", None)
        if z_override is not None:
            z_order = int(z_override)
        else:
            z_order = z.LAYER_TOP if position == "top" else z.LAYER_BACKGROUND

        attrs = dict(fill=fill, stroke=stroke, stroke_width=stroke_width)
        if fill_opacity is not None:
            attrs["fill_opacity"] = fill_opacity
        if stroke_opacity is not None:
            attrs["stroke_opacity"] = stroke_opacity
        if stroke_linecap is not None:
            attrs["stroke_linecap"] = stroke_linecap
        if stroke_dasharray is not None:
            attrs["stroke_dasharray"] = stroke_dasharray

        layer_name = f"layer_{position}"

        # Main
        gdf_clip = self._clip_gdf(gdf, self.bbox)
        if not gdf_clip.empty:
            self.main.draw_geodataframe(layer_name, gdf_clip, z_order=z_order, **attrs)

        # Zoom
        if on_zoom and self._zoom_viewport and self._zoom_bbox:
            finer = detail_for(details, ZOOM)
            zoom_gdf = self._clip_gdf(
                gdf if finer is None else finer, self._zoom_bbox)
            if not zoom_gdf.empty:
                self._zoom_viewport.draw_geodataframe(
                    layer_name, zoom_gdf, z_order=z_order, **attrs)

        # Cartouches
        if on_cartouches:
            for index, vp in self._cartouche_viewports.items():
                params = self.cartouche_params[index]
                finer = detail_for(details, index)
                cart_gdf = self._prepare_cartouche_data(
                    gdf if finer is None else finer, params)
                if not cart_gdf.empty:
                    vp.draw_geodataframe(layer_name, cart_gdf, z_order=z_order, **attrs)

    # ------------------------------------------------------------------
    # Shadow
    # ------------------------------------------------------------------

    def add_shadow(self, gdf: gpd.GeoDataFrame,
                   params: dict[str, Any] | None = None) -> Any:
        """Add a drop shadow. Same as ``m.add(DropShadow(gdf, **params))``.

        ``stdDeviation`` is accepted as the former name of ``blur``. See
        :class:`~mappyng.DropShadow` for the parameters.
        """
        from .layers import DropShadow
        cfg = dict(params or {})
        if "stdDeviation" in cfg:
            cfg["blur"] = cfg.pop("stdDeviation")
        return self.add(DropShadow(gdf, **cfg))

    def _add_shadow_filter(self, filter_id: str, dx: float, dy: float,
                           std: float, color: str, opacity: float) -> None:
        """Add the drop-shadow ``<filter>`` to the document ``<defs>``."""
        # Use primitive chain instead of feDropShadow for broad compatibility
        margin = D.SHADOW_FILTER_MARGIN
        filt = ET.SubElement(self.svg._defs, "filter", id=filter_id)
        filt.set("x", f"-{margin}%")
        filt.set("y", f"-{margin}%")
        filt.set("width", f"{100 + 2 * margin}%")
        filt.set("height", f"{100 + 2 * margin}%")

        # 1. Blur the source alpha
        blur = ET.SubElement(filt, "feGaussianBlur")
        blur.set("in", "SourceAlpha")
        blur.set("stdDeviation", str(std))
        blur.set("result", "blur")

        # 2. Offset the blurred shape
        offset = ET.SubElement(filt, "feOffset")
        offset.set("in", "blur")
        offset.set("dx", str(dx))
        offset.set("dy", str(dy))
        offset.set("result", "offsetBlur")

        # 3. Flood with shadow color + opacity
        flood = ET.SubElement(filt, "feFlood")
        flood.set("flood-color", color)
        flood.set("flood-opacity", str(opacity))
        flood.set("result", "shadowColor")

        # 4. Clip flood to the blurred shape
        comp = ET.SubElement(filt, "feComposite")
        comp.set("in", "shadowColor")
        comp.set("in2", "offsetBlur")
        comp.set("operator", "in")
        comp.set("result", "shadow")

        # 5. Merge: shadow underneath, then source graphic on top
        merge = ET.SubElement(filt, "feMerge")
        m1 = ET.SubElement(merge, "feMergeNode")
        m1.set("in", "shadow")
        m2 = ET.SubElement(merge, "feMergeNode")
        m2.set("in", "SourceGraphic")

    def _render_shadow(self, gdf: gpd.GeoDataFrame,
                       params: dict[str, Any]) -> None:
        """Draw a drop shadow for the given geometries.

        Parameters
        ----------
        gdf : GeoDataFrame
            Geometries to shadow.
        params : dict
            ``query``, ``dx``, ``dy``, ``blur``, ``color``, ``opacity``,
            ``fill``, ``on_cartouches`` (default True) and ``on_zoom``
            (default False).
        """
        cfg = dict(params or {})
        query = cfg.pop("query", None)
        on_cartouches = cfg.pop("on_cartouches", True)
        on_zoom = cfg.pop("on_zoom", False)

        sid = self._next_layer_id("shadow")
        filter_id = f"shadow-{sid}"

        dx = cfg.pop("dx", D.SHADOW_DX)
        dy = cfg.pop("dy", D.SHADOW_DY)
        std = cfg.pop("blur", D.SHADOW_STD_DEVIATION)
        color = cfg.pop("color", D.SHADOW_COLOR)
        opacity = cfg.pop("opacity", D.SHADOW_OPACITY)
        fill = cfg.pop("fill", D.SHADOW_FILL)

        self._add_shadow_filter(filter_id, dx, dy, std, color, opacity)

        # Filter gdf
        data = gdf.query(query) if query else gdf
        if data.empty:
            return

        # Dissolve to get a single outline
        dissolved = data.dissolve()

        z = self.style.config.z_order.SHADOW
        attrs = dict(fill=fill, stroke="none", filter=f"url(#{filter_id})")

        # Main viewport
        clipped = self._clip_gdf(dissolved, self.bbox)
        if not clipped.empty:
            self.main.draw_geodataframe(
                f"shadow_{sid}", clipped, z_order=z, **attrs)

        # Cartouches
        if on_cartouches:
            for index, vp in self._cartouche_viewports.items():
                params = self.cartouche_params[index]
                cart_gdf = self._prepare_cartouche_data(dissolved, params)
                if not cart_gdf.empty:
                    vp.draw_geodataframe(
                        f"shadow_{sid}", cart_gdf, z_order=z, **attrs)

        # Zoom
        if on_zoom and self._zoom_viewport and self._zoom_bbox:
            zoom_gdf = self._clip_gdf(dissolved, self._zoom_bbox)
            if not zoom_gdf.empty:
                self._zoom_viewport.draw_geodataframe(
                    f"shadow_{sid}", zoom_gdf, z_order=z, **attrs)

    # ------------------------------------------------------------------
    # Ocean gradient
    # ------------------------------------------------------------------

    def _render_ocean_gradient(self, gdf: gpd.GeoDataFrame,
                               params: dict[str, Any]) -> None:
        """Draw a gradient on the ocean, fading out from the coastline.

        The gradient is drawn as nested buffers of the dissolved
        geometries, each with a small opacity, so it renders the same in
        SVG, PNG and PDF (no SVG filter).

        Parameters
        ----------
        gdf : GeoDataFrame
            Land geometries the gradient starts from.
        params : dict
            ``query``, ``width`` (px), ``color``, ``opacity``, ``steps``,
            ``on_cartouches`` (default True) and ``on_zoom`` (default True).
        """
        cfg = dict(params)
        query = cfg.pop("query", None)
        width = float(cfg.pop("width", D.OCEAN_GRADIENT_WIDTH))
        color = cfg.pop("color", D.OCEAN_GRADIENT_COLOR)
        opacity = float(cfg.pop("opacity", D.OCEAN_GRADIENT_OPACITY))
        steps = int(cfg.pop("steps", D.OCEAN_GRADIENT_STEPS))
        on_cartouches = cfg.pop("on_cartouches", True)
        on_zoom = cfg.pop("on_zoom", True)

        data = gdf.query(query) if query else gdf
        if data.empty:
            return

        targets = [(self.main, data)]
        if on_zoom and self._zoom_viewport is not None:
            targets.append((self._zoom_viewport, data))
        if on_cartouches:
            for index, vp in self._cartouche_viewports.items():
                crs = self.cartouche_params[index].get("crs")
                local = data.to_crs(crs) if crs and data.crs else data
                targets.append((vp, local))

        sid = self._next_layer_id("ocean_gradient")
        z = self.style.config.z_order.OCEAN_GRADIENT
        alphas = _gradient_alphas(opacity, steps)
        for vp, local in targets:
            bands = _gradient_bands(local.geometry, vp.viewbox.geo_bounds,
                                    width, steps, vp.viewbox.scale)
            for band, alpha in zip(bands, alphas):
                band_gdf = gpd.GeoDataFrame(geometry=[band], crs=local.crs)
                vp.draw_geodataframe(
                    f"ocean_gradient_{sid}", band_gdf, z_order=z,
                    fill=color, fill_opacity=round(alpha, 4), stroke="none")

    # ------------------------------------------------------------------
    # Gradients
    # ------------------------------------------------------------------

    def add_radial_gradient(
        self,
        stops: list[tuple[float, str]],
        *,
        gradient_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Define a radial gradient and return its fill reference.

        Same as adding a :class:`~mappyng.RadialGradient` and using its
        ``url``. Without ``gradient_id``, ids are numbered ``radial-1``,
        ``radial-2``...

        Returns
        -------
        str
            A ``"url(#id)"`` string.
        """
        from .elements import RadialGradient
        if gradient_id is None:
            gradient_id = f"radial-{self._next_layer_id('radial')}"
        gradient = RadialGradient(stops, gradient_id=gradient_id, **kwargs)
        self.add(gradient)
        return gradient.url


def _gradient_alphas(opacity: float, steps: int) -> list[float]:
    """Opacity of each nested band, outermost first.

    The bands overlap: a point in ring ``j`` (``j = 1`` along the coast)
    is covered by the bands ``j..steps``. The opacities are chosen so the
    resulting opacity follows ``opacity * (1 - x) ** 2``, ``x`` being the
    relative distance to the coast at the middle of the ring.
    """
    target = [opacity * (1 - (j - 0.5) / steps) ** 2
              for j in range(1, steps + 1)]
    alphas = []
    outer = 0.0
    for t in reversed(target):
        alphas.append(1 - (1 - t) / (1 - outer))
        outer = t
    return alphas


def _gradient_bands(geoms: gpd.GeoSeries, bounds: tuple[float, ...],
                    width: float, steps: int, scale: float) -> list[Any]:
    """Nested buffers of *geoms*, outermost first, clipped to *bounds*.

    *width* is in pixels; *scale* converts map units to pixels.
    """
    distance = width / scale
    pixel = 1.0 / scale
    minx, miny, maxx, maxy = bounds
    land = shapely.clip_by_rect(
        shapely.union_all(shapely.make_valid(geoms.values)),
        minx - distance, miny - distance, maxx + distance, maxy + distance)
    if land.is_empty:
        return []
    land = land.simplify(pixel / 2)
    bands = []
    for k in range(steps, 0, -1):
        band = land.buffer(distance * k / steps, quad_segs=4)
        band = shapely.clip_by_rect(band.simplify(pixel / 2),
                                    minx, miny, maxx, maxy)
        if not band.is_empty:
            bands.append(band)
    return bands
