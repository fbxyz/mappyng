"""YAML (de)serialisation of a :class:`~mappyng.Map`.

The serialised form captures the map's intent: its configuration, the
ordered list of layers with their parameters, the zoom window and the
chrome. It does
not store the rendered SVG nor the raw geometry. Geometry is referenced,
not inlined: :func:`from_yaml` reattaches it from a caller-supplied
GeoDataFrame.

The root ``mappyng`` key holds an integer schema version so the format
can evolve without breaking older files.
"""

from __future__ import annotations

import os
from typing import Any

from . import defaults as D

#: Serialisation schema version (bumped on incompatible format changes).
SCHEMA_VERSION = 1


# ---------------------------------------------------------------------------
# Data sources
#
# The serialised form is geometry-free: a layer's ``data`` block records
# *where* its geometry comes from, not the geometry itself. A block is a
# "source" when it names a built-in ``dataset`` or a file ``path``; these
# are resolved to a GeoDataFrame at load time so a map can be built from a
# YAML file alone, with no Python glue. (An exported map records only
# ``in_memory: true`` because a live Map does not track its data's origin;
# declare a source by hand to make the YAML self-contained.)
# ---------------------------------------------------------------------------

#: Keys in a ``data`` block that mark it as a resolvable source.
_SOURCE_KEYS = ("dataset", "path")


def _has_source(spec: dict[str, Any] | None) -> bool:
    """True when *spec* declares a resolvable data source."""
    return isinstance(spec, dict) and any(k in spec for k in _SOURCE_KEYS)


def _resolve_path(path: str, base_dir: str | None) -> str:
    """Resolve *path* relative to *base_dir* (the YAML file's directory)."""
    if base_dir and not os.path.isabs(path):
        return os.path.join(base_dir, path)
    return path


def _resolve_data_source(spec: dict[str, Any],
                         base_dir: str | None = None) -> Any:
    """Build a GeoDataFrame from a ``data`` source block.

    Recognised keys:

    ``dataset``
        Name of a built-in dataset (see :func:`mappyng.data.list_datasets`),
        e.g. ``france_departments``.
    ``path``
        A vector file read with :func:`geopandas.read_file`. Relative paths
        resolve against *base_dir* (the YAML file's directory).
    ``crs``
        Optional target CRS; the frame is reprojected with ``to_crs``.
    ``filter``
        Optional row filter, a pandas ``query`` expression evaluated with
        the Python engine (so ``COD_GEO.str.len() == 2`` works). This
        executes the expression, so only load YAML you trust.
    ``join``
        Optional attribute join from a CSV. A mapping with ``path`` and
        ``left_on``/``right_on`` (or a shared ``on``); optional ``how``
        (default ``left``), ``dtype`` (column to type, e.g. to keep leading
        zeros) and ``columns`` (subset to keep from the CSV).

    Steps run in order: load, reproject, filter, join.
    """
    import geopandas as gpd
    import pandas as pd

    if "dataset" in spec:
        from . import data as _data

        name = spec["dataset"]
        filename = _data.AVAILABLE_DATASETS.get(name)
        if filename is None:
            raise ValueError(
                f"Unknown built-in dataset {name!r}. Available datasets: "
                f"{sorted(_data.AVAILABLE_DATASETS)}. Use one of these, or a "
                f"'path:' to your own file."
            )
        gdf = gpd.read_file(_data.get_data_path(filename))
    elif "path" in spec:
        gdf = gpd.read_file(_resolve_path(spec["path"], base_dir))
    else:  # pragma: no cover - guarded by _has_source upstream
        raise ValueError(
            "A data source needs a 'dataset' or a 'path'. Got: "
            f"{sorted(spec)}."
        )

    if spec.get("crs") is not None:
        gdf = gdf.to_crs(spec["crs"])

    if spec.get("filter"):
        try:
            gdf = gdf.query(spec["filter"], engine="python")
        except Exception as e:
            raise ValueError(
                f"Could not apply filter {spec['filter']!r}: {e}. The filter "
                f"is a pandas query expression over the layer's columns."
            ) from e

    join = spec.get("join")
    if join:
        if "path" not in join:
            raise ValueError("A 'join' needs a 'path' to a CSV file.")
        csv_path = _resolve_path(join["path"], base_dir)
        df = pd.read_csv(csv_path, dtype=join.get("dtype"))
        if "columns" in join:
            keep = list(join["columns"])
            key = join.get("right_on") or join.get("on")
            if key and key not in keep:
                keep = [key] + keep
            df = df[keep]
        merge_kw: dict[str, Any] = {"how": join.get("how", "left")}
        if "on" in join:
            merge_kw["on"] = join["on"]
        else:
            merge_kw["left_on"] = join.get("left_on")
            merge_kw["right_on"] = join.get("right_on")
            if not merge_kw["left_on"] or not merge_kw["right_on"]:
                raise ValueError(
                    "A 'join' needs either 'on', or both 'left_on' and "
                    "'right_on'."
                )
        gdf = gdf.merge(df, **merge_kw)

    return gdf


def _require_yaml():
    try:
        import yaml
        return yaml
    except ImportError as e:  # pragma: no cover - exercised via message test
        raise ImportError(
            "YAML (de)serialisation requires the 'PyYAML' package, which is "
            "not installed. Install it with:\n    pip install PyYAML\n"
            "(PyYAML is a declared dependency of mappyng; reinstalling "
            "mappyng will also pull it in.)"
        ) from e


def _yaml_key(key: Any) -> Any:
    """Coerce a mapping key to a YAML scalar, keeping its type.

    Numbers and booleans stay what they are: a ``fill_map`` keyed by
    integer categories must still match the integers of the data once
    reloaded. Anything else becomes its string form.
    """
    if isinstance(key, (bool, int, float, str)):
        return key
    item = getattr(key, "item", None)  # numpy scalar to python scalar
    if callable(item):
        try:
            value = item()
        except (TypeError, ValueError):
            value = None
        if isinstance(value, (bool, int, float, str)):
            return value
    return str(key)


def _yaml_safe(obj: Any) -> Any:
    """Coerce a value to YAML-native types, or raise in plain language.

    Tuples become lists; dicts and lists are walked recursively; scalars
    pass through. NumPy scalars are converted via ``.item()``. Anything
    else (callables, custom objects, geometries) is rejected with a clear
    message rather than silently mangled.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {_yaml_key(k): _yaml_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_yaml_safe(v) for v in obj]
    item = getattr(obj, "item", None)  # numpy scalar to python scalar
    if callable(item):
        try:
            return _yaml_safe(item())
        except (TypeError, ValueError):
            pass
    raise TypeError(
        f"Cannot serialise a parameter of type {type(obj).__name__!r} to "
        f"YAML. mappyng serialises a map's intent, so layer parameters must "
        f"be plain values (numbers, strings, lists, dicts). Keep "
        f"non-serialisable objects out of layer params."
    )


def map_to_dict(m: Any) -> dict[str, Any]:
    """Serialise a :class:`Map` to a plain dict (the YAML document model)."""
    map_cfg: dict[str, Any] = {
        "width": "auto" if m._auto_width else m.width,
        "height": "auto" if m._auto_height else m.height,
        "style": _yaml_safe(m._style_arg),
        "seed": m._seed,
    }
    if not m._font_scale_auto:
        map_cfg["font_scale"] = m.font_scale
    # Carry simple appearance overrides when explicitly set.
    if m.facecolor is not None:
        map_cfg["facecolor"] = m.facecolor
    if m._background != D.DOCUMENT_BACKGROUND:
        map_cfg["background"] = m._background
    if m._coordinate_precision != D.DEFAULT_COORDINATE_PRECISION:
        map_cfg["coordinate_precision"] = m._coordinate_precision
    # Geometry framing and main-viewport effects, when set away from default.
    if m._bbox_arg is not None:
        map_cfg["bbox"] = _yaml_safe(m._bbox_arg)
    if m.padding != D.DOCUMENT_PADDING:
        map_cfg["padding"] = m.padding
    if m._main_border_radius != D.BORDER_RADIUS:
        map_cfg["border_radius"] = m._main_border_radius
    if m._main_box_shadow is not None:
        map_cfg["box_shadow"] = _yaml_safe(m._main_box_shadow)
    if m._main_glow is not None:
        map_cfg["glow"] = _yaml_safe(m._main_glow)
    if m.basemap_color is not None:
        map_cfg["basemap_color"] = m.basemap_color
    if m.cartouche_params:
        map_cfg["cartouche_params"] = _yaml_safe(m.cartouche_params)
    if m._cartouche_spacing_override is not None:
        map_cfg["cartouche_spacing"] = m._cartouche_spacing_override

    layers = []
    for lyr in m.layers:
        d = lyr.to_dict()
        d["params"] = _yaml_safe(d.get("params", {}))
        layers.append(d)

    doc: dict[str, Any] = {
        "mappyng": SCHEMA_VERSION,
        "map": map_cfg,
        "layers": layers,
    }
    if m._zoom_params is not None:
        doc["zoom"] = _yaml_safe(m._zoom_params)
    if m._state.chrome:
        doc["chrome"] = _yaml_safe(m._state.chrome)
    if m._tooltip is not None:
        interactive = {k: v for k, v in m._tooltip.to_kwargs().items()
                       if v is not None}
        if "tooltip" in interactive and not isinstance(
                interactive["tooltip"], dict):
            del interactive["tooltip"]
        doc["interactive"] = _yaml_safe(interactive)
    return doc


def map_from_dict(doc: dict[str, Any], gdf: Any = None,
                  data: dict[str, Any] | None = None,
                  base_dir: str | None = None) -> Any:
    """Rebuild a :class:`Map` from :func:`map_to_dict` output.

    Parameters
    ----------
    doc : dict
        The serialised document.
    gdf : GeoDataFrame, optional
        Base geometry for the map and the default geometry attached to
        every data layer. When given, declared ``data:`` sources in the
        document are ignored (the caller is supplying the geometry). When
        omitted, geometry is resolved from the sources declared in the
        document (``map.data`` and each layer's ``data:`` block); a map
        with no source anywhere then raises.
    data : dict, optional
        Per-layer geometry override, keyed by layer ``id``. Takes priority
        over both *gdf* and any declared source for that layer.
    base_dir : str, optional
        Directory that relative ``path:`` entries resolve against (the YAML
        file's directory). Defaults to the current directory.
    """
    from .elements import Tooltip, Zoom
    from .layers import Layer
    from .map import Map

    version = doc.get("mappyng")
    if version != SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported mappyng serialisation version {version!r}; this "
            f"build reads version {SCHEMA_VERSION}. The file may come from a "
            f"newer mappyng. Upgrade mappyng to read it."
        )

    data = data or {}
    cfg = dict(doc.get("map", {}))
    layer_docs = list(doc.get("layers", []))

    # Resolve declared sources only when the caller did not supply geometry.
    # A small cache avoids re-reading a file referenced by several layers.
    use_sources = gdf is None or getattr(gdf, "empty", True)
    _cache: dict[str, Any] = {}

    def _resolve(spec: dict[str, Any]) -> Any:
        key = repr(sorted(spec.items(), key=lambda kv: kv[0]))
        if key not in _cache:
            _cache[key] = _resolve_data_source(spec, base_dir=base_dir)
        return _cache[key]

    # Per-layer geometry: explicit override > declared source > base.
    layer_gdfs: list = []
    for ld in layer_docs:
        layer_id = ld.get("id")
        if layer_id in data:
            layer_gdfs.append(data[layer_id])
        elif use_sources and _has_source(ld.get("data")):
            layer_gdfs.append(_resolve(ld["data"]))
        else:
            layer_gdfs.append(None)  # fall back to the base below

    # Base geometry: explicit gdf > map.data source > first resolved layer.
    if not use_sources:
        base = gdf
    elif _has_source(cfg.get("data")):
        base = _resolve(cfg["data"])
    else:
        base = next((g for g in layer_gdfs if g is not None), None)

    if base is None or getattr(base, "empty", False):
        raise ValueError(
            "from_yaml has no geometry to build from. Either pass it in, "
            "e.g. Map.from_yaml(path, gdf=geopandas.read_file(...)), or "
            "declare a source in the YAML (a 'data:' block with a 'dataset:' "
            "or 'path:') on the map or a layer."
        )

    # Cartouche params carry integer indices, which YAML stores as strings.
    cartouche_params = cfg.get("cartouche_params")
    if cartouche_params is not None:
        cartouche_params = {int(k): v for k, v in cartouche_params.items()}

    map_kwargs: dict[str, Any] = dict(
        width=cfg.get("width", D.DOCUMENT_WIDTH),
        height=cfg.get("height", D.DOCUMENT_HEIGHT),
        style=cfg.get("style", "classic"),
        seed=cfg.get("seed", 42),
        facecolor=cfg.get("facecolor"),
        background=cfg.get("background"),
        coordinate_precision=cfg.get(
            "coordinate_precision", D.DEFAULT_COORDINATE_PRECISION),
    )
    # Forward the remaining constructor options only when present, so each
    # keeps its own default otherwise.
    for key in ("bbox", "padding", "border_radius", "box_shadow", "glow",
                "basemap_color", "cartouche_spacing", "font_scale"):
        if key in cfg:
            map_kwargs[key] = cfg[key]
    if cartouche_params is not None:
        map_kwargs["cartouche_params"] = cartouche_params

    m = Map(base, **map_kwargs)

    # Zoom window, created before the layers so they can draw into it.
    zoom = doc.get("zoom")
    if zoom:
        zoom = dict(zoom)
        if "bbox" not in zoom:
            raise ValueError(
                "The 'zoom' block needs a 'bbox': [minx, miny, maxx, maxy] "
                "in the map CRS."
            )
        m.add(Zoom(zoom.pop("bbox"), **zoom))

    for ld, layer_gdf in zip(layer_docs, layer_gdfs):
        layer = Layer.from_dict(ld, gdf=layer_gdf if layer_gdf is not None else base)
        m.add(layer)

    # Drop shadows: an imperative effect, declared here as a list of
    # {data: <source>, params: {query, dx, ...}}. Each resolves its own
    # geometry (or falls back to the base) and is replayed via add_shadow.
    for sh in doc.get("shadows", []):
        spec = sh.get("data") if isinstance(sh, dict) else None
        if use_sources and spec is not None and _has_source(spec):
            shadow_gdf = _resolve(spec)
        else:
            shadow_gdf = base
        m.add_shadow(shadow_gdf, dict(sh.get("params", {})))

    # Chrome: replay the convenience methods in document order, so element
    # ordering matches a hand-written map.
    chrome = doc.get("chrome", {})
    for name, params in chrome.items():
        params = dict(params)
        if name in ("title", "source"):
            getattr(m, name)(params.pop("text", ""), **params)
        elif name in ("scale_bar", "north_arrow"):
            getattr(m, name)(**params)
        else:
            raise ValueError(
                f"Unknown chrome entry {name!r}. Known entries: title, "
                f"source, scale_bar, north_arrow."
            )

    # Tooltips of the interactive export.
    interactive = doc.get("interactive")
    if interactive:
        interactive = dict(interactive)
        m.add(Tooltip(interactive.pop("columns", None),
                      aliases=interactive.pop("aliases", None),
                      style=interactive.pop("tooltip", None),
                      hover_opacity=interactive.pop("hover_opacity", None)))

    return m


def to_yaml(m: Any, path: str | None = None) -> str:
    """Serialise *m* to YAML. Writes to *path* if given; returns the text."""
    yaml = _require_yaml()
    text = yaml.safe_dump(
        map_to_dict(m), sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    if path is not None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return text


def _fingerprint(gdf: Any) -> dict[str, Any]:
    """Identify a GeoDataFrame: size, CRS, columns and a content hash.

    The SHA-256 covers, in row order: the CRS, every geometry (WKB, so
    coordinates at full precision), and every non-geometry column (name and
    values rendered as text). It does not cover the index labels, the column
    dtypes or the row/column order of another frame holding the same data
    (reordering the rows changes the hash). It verifies data; it cannot
    recover it.
    """
    import hashlib

    h = hashlib.sha256()
    h.update(str(gdf.crs.to_wkt() if gdf.crs is not None else None).encode())
    for geom in gdf.geometry:
        h.update(b"" if geom is None else geom.wkb)
    for col in gdf.columns:
        if col != gdf.geometry.name:
            h.update(str(col).encode())
            h.update(gdf[col].astype(str).str.cat(sep="\x1f").encode())
    return {
        "rows": int(len(gdf)),
        "crs": gdf.crs.to_string() if gdf.crs is not None else None,
        "columns": [str(c) for c in gdf.columns if c != gdf.geometry.name],
        "sha256": h.hexdigest(),
    }


def recipe(m: Any, path: str | None = None) -> dict[str, Any]:
    """Everything needed to reproduce *m*: parameters, data identity, versions.

    The recipe holds the map document (as :func:`map_to_dict`), the versions
    of mappyng and of the libraries that shape the result, a fingerprint of
    the main geometry and of each layer's data (rows, CRS, columns, SHA-256),
    and, once the map has been built, the classification report of every
    thematic layer. Compare two recipes to see why two renders differ.

    It is a provenance record, not a rebuild kit: the fingerprints check that
    data are the same, they do not contain it, and a faithful rebuild also
    needs the same data and compatible library versions. ``classification``
    is empty until the map has been built; a built map is frozen, and a map
    derived from it (``m + item``) starts again with no report.

    Written to *path* as YAML (``.yaml``/``.yml``) or JSON when given.
    """
    import platform
    from importlib import metadata

    def _ver(name: str) -> str | None:
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            return None

    from . import __version__

    layer_data = []
    for lyr in m.layers:
        gdf = getattr(lyr, "gdf", None)
        if gdf is not None:
            layer_data.append({"layer": lyr.kind, **_fingerprint(gdf)})
    doc: dict[str, Any] = {
        "mappyng_version": __version__,
        "python": platform.python_version(),
        "libraries": {n: _ver(n) for n in (
            "geopandas", "shapely", "pyproj", "mapclassify", "numpy",
            "pandas", "cairosvg")},
        "seed": m._seed,
        "map": map_to_dict(m),
        "data": {"main": _fingerprint(m.gdf), "layers": layer_data},
        "classification": {
            str(k): v.to_dict()
            for k, v in m._state.classification_reports.items()
        },
    }
    doc = _yaml_safe(doc)
    if path is not None:
        if str(path).lower().endswith((".yaml", ".yml")):
            text = _require_yaml().safe_dump(
                doc, sort_keys=False, allow_unicode=True)
        else:
            import json
            text = json.dumps(doc, indent=2, ensure_ascii=False)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
    return doc


def from_yaml(source: str, gdf: Any = None,
              data: dict[str, Any] | None = None,
              base_dir: str | None = None) -> Any:
    """Rebuild a :class:`Map` from a YAML *source* (file path or string).

    When *source* is a file path, relative ``path:`` entries in the
    document resolve against that file's directory unless *base_dir* is
    given explicitly.
    """
    yaml = _require_yaml()
    if isinstance(source, str) and ("\n" not in source) and os.path.exists(source):
        if base_dir is None:
            base_dir = os.path.dirname(os.path.abspath(source))
        with open(source, encoding="utf-8") as fh:
            text = fh.read()
    else:
        if (isinstance(source, str) and "\n" not in source
                and source.strip().lower().endswith((".yaml", ".yml"))):
            raise FileNotFoundError(
                f"from_yaml: no such file {source!r}. Check the path; a "
                f"relative one is resolved from the current directory "
                f"({os.getcwd()!r})."
            )
        text = source
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        raise ValueError(
            "The YAML source does not describe a mappyng map (expected a "
            "mapping with a 'mappyng' version key at the root)."
        )
    return map_from_dict(doc, gdf=gdf, data=data, base_dir=base_dir)
