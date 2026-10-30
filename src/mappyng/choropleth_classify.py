"""Classification and colour/opacity resolution for choropleths."""

from __future__ import annotations

import warnings
from dataclasses import asdict, dataclass, field
from typing import Any

import geopandas as gpd
import mapclassify as mc
import numpy as np

from . import defaults as D
from .config import COLORMAP_DEFS

# ============================================================================
# Classification
# ============================================================================

METHODS = {
    "EqualInterval": lambda col, k: mc.EqualInterval(col, k=k),
    "Quantiles": lambda col, k: mc.Quantiles(col, k=k),
    "FisherJenks": lambda col, k: mc.FisherJenks(col, k=k),
    "Q6": lambda col, _: mc.Percentiles(col, pct=[5, 25, 50, 75, 95, 100]),
    "StdMean": lambda col, k: mc.StdMean(col, multiples=D.CHOROPLETH_STDMEAN_MULTIPLES[k]),
    "PrettyBreaks": lambda col, k: mc.PrettyBreaks(col, k=k),
}


def _resolve_stdmean_k(num_classes: int) -> int:
    """Validate and snap the StdMean class count.

    StdMean splits the data in standard-deviation steps either side of the
    mean, with a central class straddling it, so the count must be odd. Only
    the counts in :data:`~mappyng.defaults.CHOROPLETH_STDMEAN_MULTIPLES` (5 and
    7) are supported. They build a *double gamme* (diverging) palette: one ramp
    below the mean and one above, meeting at a neutral central class.

    An unsupported count is not an error: it snaps to the nearest valid count
    (5 or 7) and emits a :class:`UserWarning`, so the map still renders.
    """
    if num_classes in D.CHOROPLETH_STDMEAN_MULTIPLES:
        return num_classes
    allowed = sorted(D.CHOROPLETH_STDMEAN_MULTIPLES)
    snapped = min(allowed, key=lambda k: (abs(k - num_classes), k))
    warnings.warn(
        f"StdMean supports {', '.join(str(k) for k in allowed)} classes only "
        f"(odd counts: standard-deviation steps either side of the mean, with a "
        f"central class straddling it). Requested num_classes={num_classes}; "
        f"using num_classes={snapped} instead.",
        UserWarning,
        stacklevel=2,
    )
    return snapped


def _resolve_num_classes(method: str | list, num_classes: int) -> int:
    """Return the effective number of classes."""
    if method == "Q6":
        return 6
    if method == "StdMean":
        return _resolve_stdmean_k(num_classes)
    if isinstance(method, list):
        # method is a list of break points (edges): N+1 values to N classes
        return len(method) - 1
    if not D.CHOROPLETH_MIN_CLASSES <= num_classes <= D.CHOROPLETH_MAX_CLASSES:
        raise ValueError(
            f"num_classes must be {D.CHOROPLETH_MIN_CLASSES}-"
            f"{D.CHOROPLETH_MAX_CLASSES}, got {num_classes}"
        )
    return num_classes


def _resolve_colors(cmap: str | list[str], num_classes: int) -> list[str]:
    """Return a list of hex color strings."""
    if isinstance(cmap, list):
        if len(cmap) != num_classes:
            raise ValueError(
                f"Custom color list length ({len(cmap)}) != num_classes ({num_classes})"
            )
        return cmap
    if cmap not in COLORMAP_DEFS:
        raise ValueError(f"Unknown colormap: {cmap}. Available: {list(COLORMAP_DEFS)}")
    if num_classes not in COLORMAP_DEFS[cmap]:
        raise ValueError(f"No {num_classes}-class palette for '{cmap}'")
    return COLORMAP_DEFS[cmap][num_classes]


def _resolve_colors_with_fallback(cmap: str | list[str], k_real: int,
                                  label: str = "PrettyBreaks") -> list[str]:
    """Resolve colors for a real class count, with fallback for missing palette sizes.

    Used when the actual class count may differ from the requested k (PrettyBreaks,
    or breaks that collapsed). If the colormap has no palette for k_real, the nearest
    available palette is used
    (preferring the smallest k_avail >= k_real, then truncating to k_real colors).
    A warning is emitted when a fallback is applied.

    Parameters
    ----------
    cmap : str or list
        Colormap name or explicit list of hex colors.
    k_real : int
        Actual number of classes produced by the classifier.
    label : str
        Name used in warnings and errors (the classification method).

    Returns
    -------
    list of str
        Exactly k_real hex color strings.
    """
    if isinstance(cmap, list):
        if len(cmap) != k_real:
            raise ValueError(
                f"Custom color list length ({len(cmap)}) must equal the real number "
                f"of {label} classes ({k_real})."
            )
        return cmap
    if cmap not in COLORMAP_DEFS:
        raise ValueError(f"Unknown colormap: {cmap}. Available: {list(COLORMAP_DEFS)}")
    palette_map = COLORMAP_DEFS[cmap]
    if k_real in palette_map:
        return palette_map[k_real]
    available = sorted(palette_map.keys())
    # Prefer smallest k_avail >= k_real (then truncate); fallback to largest available.
    candidates_above = [k for k in available if k >= k_real]
    if candidates_above:
        k_avail = min(candidates_above)
        colors = palette_map[k_avail][:k_real]
        warnings.warn(
            f"{label}: no {k_real}-class palette for '{cmap}'. "
            f"Using first {k_real} colors from the {k_avail}-class palette.",
            UserWarning,
            stacklevel=4,
        )
    else:
        k_avail = max(available)
        colors = palette_map[k_avail]
        warnings.warn(
            f"{label}: no {k_real}-class palette for '{cmap}' and no larger palette "
            f"available. Using the {k_avail}-class palette ({k_avail} colors for {k_real} classes).",
            UserWarning,
            stacklevel=4,
        )
    return colors


def _looks_like_stock(values: np.ndarray) -> float | None:
    """Return the column maximum if *values* look like stock data, else None.

    A choropleth maps colour value, read as a relative quantity. Absolute
    counts (stock) are better served by proportional symbols. This heuristic
    flags the common signature of stock data so a (non-blocking) warning can
    be emitted. All of the following must hold:

    * at least 3 non-NaN values,
    * all strictly positive,
    * all integer-valued (rates, densities and averages are typically
      fractional, so this filters most relative variables out),
    * the maximum reaches
      :data:`~mappyng.defaults.CHOROPLETH_STOCK_MAGNITUDE_WARN` (rules out
      identifier-like columns with a small range, e.g. region ids),
    * the max/min ratio is at least
      :data:`~mappyng.defaults.CHOROPLETH_STOCK_RATIO_WARN` (rules out
      near-constant columns such as a year of reference).

    Parameters
    ----------
    values : np.ndarray
        Raw column values (may contain NaN).

    Returns
    -------
    float or None
        The column maximum when it looks like stock data, else None.
    """
    v = np.asarray(values, dtype=float)
    v = v[~np.isnan(v)]
    if v.size < 3 or np.any(v <= 0):
        return None
    if not np.allclose(v, np.round(v)):
        return None
    vmin, vmax = float(v.min()), float(v.max())
    if vmax < D.CHOROPLETH_STOCK_MAGNITUDE_WARN:
        return None
    if vmax / vmin < D.CHOROPLETH_STOCK_RATIO_WARN:
        return None
    return vmax


@dataclass
class ClassificationReport:
    """What a classification actually did, for inspection after rendering.

    Parameters
    ----------
    column : str
        Classified column.
    method : str
        Method really applied (``"Custom breaks"`` for an explicit list).
    requested_classes, applied_classes : int
        Class count asked for and class count really produced.
    bins : list of float
        Class bounds, minimum first (``applied_classes + 1`` values).
    counts : list of int
        Number of features per class.
    n_valid, n_excluded : int
        Features classified, and features left out because the value is NaN.
    cmap : str or list of str
        Palette requested (a colormap name, or the explicit colour list).
    colors : list of str
        Colour really used for each class, in class order, after any palette
        adjustment and after ``reverse``.
    adjustments : list of str
        Human-readable automatic corrections (snapped class count, merged
        classes, palette reduced to fewer colours...) with their reason.
        Empty when nothing was adjusted.
    """

    column: str
    method: str
    requested_classes: int
    applied_classes: int
    bins: list[float]
    counts: list[int]
    n_valid: int
    n_excluded: int
    cmap: Any = None
    colors: list[str] = field(default_factory=list)
    adjustments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_dataframe(self) -> Any:
        """One row per class: bounds, colour and number of features."""
        import pandas as pd
        return pd.DataFrame({
            "class": range(self.applied_classes),
            "lower": self.bins[:-1],
            "upper": self.bins[1:],
            "color": self.colors or [""] * self.applied_classes,
            "count": self.counts,
        })

    def __str__(self) -> str:
        lines = [
            f"Classification of {self.column!r}: {self.method}, "
            f"{self.applied_classes} classes (requested {self.requested_classes})",
            f"  {self.n_valid} features classified, "
            f"{self.n_excluded} excluded (no value)",
        ]
        for i, c in enumerate(self.counts):
            lines.append(f"  [{self.bins[i]:g} ; {self.bins[i + 1]:g}] : {c}")
        lines += [f"  adjustment: {a}" for a in self.adjustments]
        return "\n".join(lines)


@dataclass
class CategoryReport:
    """What a Category layer drew: features per category, exclusions.

    Parameters
    ----------
    column : str
        Column holding the categories.
    categories : list
        Categories in legend order (``"__default__"`` stands for the values
        drawn with ``default_fill``).
    counts : list of int
        Number of features per category.
    n_valid, n_excluded : int
        Features drawn with a category colour, and features left out because
        the value is missing.
    unmapped : list
        Values absent from ``fill_map`` that fell back to ``default_fill``.
    """

    column: str
    categories: list[Any]
    counts: list[int]
    n_valid: int
    n_excluded: int
    unmapped: list[Any] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_dataframe(self) -> Any:
        """One row per category with its number of features."""
        import pandas as pd
        return pd.DataFrame({"category": self.categories, "count": self.counts})

    def __str__(self) -> str:
        lines = [f"Categories of {self.column!r}: {len(self.categories)}",
                 f"  {self.n_valid} features drawn, "
                 f"{self.n_excluded} excluded (no value)"]
        lines += [f"  {c}: {n}" for c, n in zip(self.categories, self.counts)]
        if self.unmapped:
            lines.append(f"  default fill used for: {self.unmapped}")
        return "\n".join(lines)


def build_report(
    column: str, method: str | list, requested: int, resolved: int,
    classified: gpd.GeoDataFrame, nodata: gpd.GeoDataFrame, bins: np.ndarray,
    adjustments: list[str], cmap: Any = None,
    colors: list[str] | None = None,
) -> ClassificationReport:
    """Summarise a finished classification (see :class:`ClassificationReport`)."""
    k_real = len(bins) - 1
    counts = np.bincount(classified["_class"].to_numpy(dtype=int),
                         minlength=k_real)[:k_real]
    return ClassificationReport(
        column=column,
        method=method if isinstance(method, str) else "Custom breaks",
        requested_classes=requested,
        applied_classes=k_real,
        bins=[float(b) for b in bins],
        counts=[int(c) for c in counts],
        n_valid=len(classified),
        n_excluded=len(nodata),
        cmap=cmap if isinstance(cmap, str) or cmap is None else list(cmap),
        colors=list(colors or []),
        adjustments=adjustments,
    )


def palette_adjustment(cmap: Any, colors: list[str]) -> str | None:
    """Explain how *colors* differ from the palette requested, if they do.

    ``None`` when *colors* is exactly the ``len(colors)``-class palette of
    *cmap* (or an explicit list is used as given).
    """
    n = len(colors)
    if isinstance(cmap, str):
        full = COLORMAP_DEFS.get(cmap, {})
        if list(full.get(n, [])) == list(colors):
            return None
        sizes = sorted(k for k in full if k >= n)
        src = sizes[0] if sizes else (max(full) if full else None)
        return (f"palette {cmap!r} has no {n}-class version: the first {n} "
                f"colours of its {src}-class version are used")
    return None


def classify(
    gdf: gpd.GeoDataFrame,
    column: str,
    method: str | list = D.CHOROPLETH_DEFAULT_METHOD,
    num_classes: int = D.CHOROPLETH_DEFAULT_NUM_CLASSES,
    decimals: int = D.CHOROPLETH_DECIMALS,
) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame, mc.classifiers.MapClassifier, np.ndarray]:
    """Classify a GeoDataFrame column and assign class indices.

    Returns
    -------
    classified : GeoDataFrame
        Rows with data, gains ``_class`` (int) column.
    nodata : GeoDataFrame
        Rows where *column* is NaN.
    scheme : mapclassify classifier
        The fitted classification object.
    bins : ndarray
        Bin edges including the minimum value.
    """
    gdf = gdf.copy()
    nodata = gdf[gdf[column].isna()]
    gdf = gdf.dropna(subset=[column])

    if isinstance(method, list):
        bins_list = [float(v) for v in method]
        scheme = mc.UserDefined(gdf[column], bins=bins_list[1:])
    else:
        if method not in METHODS:
            raise ValueError(f"Unknown method '{method}'. Available: {list(METHODS)}")
        if method == "StdMean":
            # StdMean has its own valid class counts (5, 7); snap with a warning
            # rather than enforcing the generic 4-7 range.
            num_classes = _resolve_stdmean_k(num_classes)
        elif not D.CHOROPLETH_MIN_CLASSES <= num_classes <= D.CHOROPLETH_MAX_CLASSES:
            raise ValueError(
                f"num_classes must be {D.CHOROPLETH_MIN_CLASSES}-"
                f"{D.CHOROPLETH_MAX_CLASSES}, got {num_classes}"
            )
        gdf[column] = gdf[column].round(decimals=decimals)
        scheme = METHODS[method](gdf[column], num_classes)

    bins = np.round([gdf[column].min()] + list(scheme.bins), decimals)
    # Use len(scheme.bins) as the effective class count: for PrettyBreaks,
    # scheme.k reports the requested k, not the actual number of bins produced.
    k_eff = len(scheme.bins)
    gdf["_class"] = np.clip(scheme.yb, 0, k_eff - 1)
    return gdf, nodata, scheme, bins


def _resolve_opacity_bins(
    gdf: gpd.GeoDataFrame,
    opacity_column: str | None,
    opacity_bins: int | list[float] | None,
) -> tuple[gpd.GeoDataFrame, int | None]:
    """Discretize *opacity_column* into a small number of levels.

    Replaces each value with its bin's centre and adds an integer
    ``_opacity_class`` column. Two features that share both the colour
    class and the opacity class are then drawn with the exact same style,
    so ``dissolve`` can merge them without approximating anything (a plain
    per-feature ``mean`` would blur the opacity of a dissolved group).

    Parameters
    ----------
    opacity_bins : int, list of float, or None
        ``None`` (default) leaves *opacity_column* continuous, one opacity
        per feature. An int discretizes ``[0, 1]`` into that many
        equal-width bins. A list is used as explicit bin edges (in the
        same ``[0, 1]`` probability domain).

    Returns
    -------
    gdf : GeoDataFrame
        Copy with *opacity_column* replaced by bin centres and a new
        ``_opacity_class`` column, when *opacity_bins* is set.
    n_levels : int or None
        Number of opacity levels, or ``None`` if untouched.
    """
    if opacity_column is None or opacity_bins is None:
        return gdf, None
    if isinstance(opacity_bins, int):
        edges = np.linspace(0.0, 1.0, opacity_bins + 1)
    else:
        edges = np.asarray(sorted(float(b) for b in opacity_bins))
    n = len(edges) - 1
    gdf = gdf.copy()
    values = gdf[opacity_column].to_numpy(dtype=float)
    idx = np.clip(np.digitize(values, edges[1:-1], right=True), 0, n - 1)
    centers = (edges[:-1] + edges[1:]) / 2
    gdf[opacity_column] = centers[idx]
    gdf["_opacity_class"] = idx
    return gdf, n
