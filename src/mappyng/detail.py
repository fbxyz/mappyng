"""Alternative, finer geometry for the zoom window and the cartouches.

A map is often drawn from a generalised (simplified) layer, which looks
coarse once magnified in a zoom window or an inset. ``detail`` lets a layer
draw its zoom/cartouche views from a finer layer of the same areas, while
keeping the layer's symbology: the classes, colours and opacities are
computed once, from the layer's own data, then carried to the finer
geometries through a join key.

Accepted forms of ``detail``
----------------------------
* a GeoDataFrame: used on the zoom window and on every cartouche;
* a dict mapping targets to GeoDataFrames. Targets are ``"zoom"``,
  ``"cartouches"`` (every cartouche) and cartouche indexes (``0``, ``1``...);
  an index takes precedence over ``"cartouches"``.

``join`` names the key shared by the layer's data and the finer layer: a
column name present in both, a ``(layer_column, detail_column)`` pair, or
``None`` to join on the index. Several finer rows may share one key (for
example a unit split into islands); each takes the unit's symbology.
"""

from __future__ import annotations

import warnings
from typing import Any

import geopandas as gpd
from pandas.api.types import is_numeric_dtype

ZOOM = "zoom"
CARTOUCHES = "cartouches"


def normalize_detail(detail: Any) -> dict[Any, gpd.GeoDataFrame]:
    """Return *detail* as a ``{target: GeoDataFrame}`` dict (possibly empty)."""
    if detail is None:
        return {}
    if isinstance(detail, gpd.GeoDataFrame):
        return {ZOOM: detail, CARTOUCHES: detail}
    if isinstance(detail, dict):
        for key, value in detail.items():
            valid_key = key in (ZOOM, CARTOUCHES) or (
                isinstance(key, int) and not isinstance(key, bool))
            if not valid_key:
                raise ValueError(
                    f"detail: unknown target {key!r}. Use 'zoom', "
                    f"'cartouches' or a cartouche index (0, 1...)."
                )
            if not isinstance(value, gpd.GeoDataFrame):
                raise ValueError(
                    f"detail[{key!r}] must be a GeoDataFrame, got "
                    f"{type(value).__name__}."
                )
        return dict(detail)
    raise ValueError(
        f"detail must be a GeoDataFrame or a dict of GeoDataFrames, got "
        f"{type(detail).__name__}."
    )


def detail_for(details: dict[Any, gpd.GeoDataFrame], target: Any
               ) -> gpd.GeoDataFrame | None:
    """Finer layer for *target* (``"zoom"`` or a cartouche index), or None."""
    if target == ZOOM:
        return details.get(ZOOM)
    if target in details:
        return details[target]
    return details.get(CARTOUCHES)


def _split_join(join: Any) -> tuple[str | None, str | None]:
    if join is None:
        return None, None
    if isinstance(join, str):
        return join, join
    if isinstance(join, (list, tuple)) and len(join) == 2:
        return join[0], join[1]
    raise ValueError(
        f"join must be a column name, a (layer_column, detail_column) pair "
        f"or None, got {join!r}."
    )


def join_detail(frame: gpd.GeoDataFrame, detail: gpd.GeoDataFrame,
                join: Any = None, *, what: str = "layer",
                ) -> gpd.GeoDataFrame:
    """Give *frame*'s attributes to the geometries of *detail*.

    Parameters
    ----------
    frame : GeoDataFrame
        The layer's data (carries the symbology columns).
    detail : GeoDataFrame
        The finer geometries.
    join : str, tuple or None
        Join key, see the module docstring.
    what : str
        Name used in messages.

    Returns
    -------
    GeoDataFrame
        One row per finer geometry that matches a row of *frame*, with
        *frame*'s columns, in *frame*'s CRS. The index is *frame*'s index,
        so element ids stay the same as on the main map. Rows of *detail*
        with no match are dropped; rows of *frame* with no finer geometry
        are not drawn (a warning lists them).
    """
    left, right = _split_join(join)
    if frame.empty:
        return frame

    if frame.crs is not None and detail.crs is not None \
            and frame.crs != detail.crs:
        detail = detail.to_crs(frame.crs)

    attrs = frame.drop(columns=frame.geometry.name)
    attrs = attrs.assign(__frame_index=frame.index.to_numpy())
    if left is None:
        keys = frame.index.to_numpy()
        detail_keys = detail.index.to_numpy()
    else:
        for col, owner, df in ((left, what, frame), (right, "detail", detail)):
            if col not in df.columns:
                raise ValueError(
                    f"detail join: column {col!r} is not in the {owner} "
                    f"data. Available columns: "
                    f"{[c for c in df.columns if c != df.geometry.name]}."
                )
        keys = frame[left].to_numpy()
        detail_keys = detail[right].to_numpy()

    attrs["__join_key"] = keys
    if attrs["__join_key"].duplicated().any():
        raise ValueError(
            f"detail join: the key of the {what} data has duplicates, so "
            f"its symbology cannot be matched to the finer geometries "
            f"unambiguously. Use a unique key column."
        )

    finer = gpd.GeoDataFrame(
        {"__join_key": detail_keys}, geometry=detail.geometry.to_numpy(),
        crs=detail.crs,
    )
    if is_numeric_dtype(attrs["__join_key"]) != is_numeric_dtype(finer["__join_key"]):
        raise ValueError(
            f"detail join: the key is {attrs['__join_key'].dtype} in the "
            f"{what} data but {finer['__join_key'].dtype} in the finer layer, "
            f"so no value can match. Convert one side so both have the same "
            f"type, for example gdf[col] = gdf[col].astype(str)."
        )

    merged = finer.merge(attrs, on="__join_key", how="inner")

    missing = attrs.loc[~attrs["__join_key"].isin(finer["__join_key"]),
                        "__join_key"]
    if len(missing):
        shown = ", ".join(repr(k) for k in missing.head(5))
        more = f" and {len(missing) - 5} more" if len(missing) > 5 else ""
        warnings.warn(
            f"detail: {len(missing)} {what} area(s) have no geometry in the "
            f"finer layer and are not drawn in the zoom/cartouches "
            f"({shown}{more}). Check that 'join' matches the key in both "
            f"layers.",
            UserWarning, stacklevel=3,
        )

    merged.index = merged.pop("__frame_index")
    merged = merged.drop(columns="__join_key")
    merged.index.name = frame.index.name
    return merged
