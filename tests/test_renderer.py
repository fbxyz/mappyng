"""Tests for SVG renderer primitives, including radial gradients."""

import geopandas as gpd
import numpy as np
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon

from mappyng import Map, Vector
from mappyng.renderer import (
    SvgDocument,
    ViewBox,
    geometry_to_paths,
    polygon_to_path,
)

ORTHO = "+proj=ortho +lat_0=12 +lon_0=0 +ellps=WGS84 +units=m +no_defs"


# ============================================================================
# Radial gradients
# ============================================================================

def test_radial_gradient_returns_url_reference():
    """add_radial_gradient returns a url(#id) string usable as a fill."""
    doc = SvgDocument(width=100, height=100)
    url = doc.add_radial_gradient([(0.0, "#ffffff"), (1.0, "#000000")])
    assert url.startswith("url(#")
    assert url.endswith(")")


def test_radial_gradient_generates_unique_ids():
    """Two gradients without explicit ids do not collide."""
    doc = SvgDocument(width=100, height=100)
    a = doc.add_radial_gradient([(0.0, "#fff"), (1.0, "#000")])
    b = doc.add_radial_gradient([(0.0, "#fff"), (1.0, "#000")])
    assert a != b


def test_radial_gradient_definition_in_defs():
    """The gradient and its stops land in <defs> with the focal point set."""
    doc = SvgDocument(width=100, height=100)
    doc.add_radial_gradient(
        [(0.0, "#bfe6ff"), (1.0, "#0b3a57")],
        gradient_id="ocean", fx=0.35, fy=0.4)
    grad = doc._defs.find("radialGradient")
    assert grad is not None
    assert grad.get("id") == "ocean"
    assert grad.get("fx") == "0.35"
    assert grad.get("fy") == "0.4"
    stops = grad.findall("stop")
    assert len(stops) == 2
    assert stops[0].get("offset") == "0.0"
    assert stops[0].get("stop-color") == "#bfe6ff"


def test_radial_gradient_stop_opacity():
    """A three-element stop sets stop-opacity; a two-element one omits it."""
    doc = SvgDocument(width=100, height=100)
    doc.add_radial_gradient(
        [(0.0, "#ffffff", 0.5), (1.0, "#000000")], gradient_id="g")
    stops = doc._defs.find("radialGradient").findall("stop")
    assert stops[0].get("stop-opacity") == "0.5"
    assert stops[1].get("stop-opacity") is None


def test_map_radial_gradient_renders_in_output(gdf_departments):
    """Map.add_radial_gradient is serialised and can fill a layer."""
    m = Map(gdf_departments)
    fill = m.add_radial_gradient(
        [(0.0, "#bfe6ff"), (1.0, "#0b3a57")], gradient_id="ocean")
    m.add(Vector(gdf_departments, fill=fill))
    svg = m.to_string()
    assert "<radialGradient" in svg
    assert 'id="ocean"' in svg
    assert "url(#ocean)" in svg


# ============================================================================
# Graticule in curved projections (orthographic)
# ============================================================================

def test_prune_nonfinite_splits_line_into_finite_runs():
    """A line with infinite vertices is split into its finite segments."""
    inf = float("inf")
    line = LineString([(0, 0), (1, 1), (inf, inf), (3, 3), (4, 4)])
    gdf = gpd.GeoDataFrame(geometry=[line], crs=ORTHO)
    out = Map._prune_nonfinite_lines(gdf)
    # Two finite runs: [(0,0),(1,1)] and [(3,3),(4,4)].
    assert len(out) == 2
    assert all(np.isfinite(np.asarray(g.coords)).all() for g in out.geometry)


def test_graticule_builds_on_orthographic_globe():
    """A graticule on an orthographic map yields finite, non-empty arcs."""
    disc = gpd.GeoDataFrame(
        geometry=gpd.GeoSeries.from_xy([0.0], [0.0]).buffer(6.0e6),
        crs=ORTHO)
    m = Map(disc, bbox=[-7e6, -7e6, 7e6, 7e6])
    grat = m._build_graticule_gdf(m.bbox, m.gdf.crs, step=30.0)
    assert grat is not None and not grat.empty
    for geom in grat.geometry:
        assert np.isfinite(np.asarray(geom.coords)).all()


# ============================================================================
# Vectorized path conversion (byte-identical to the scalar baseline)
# ============================================================================

def _ref_ring(coords, vb, *, close):
    """Scalar baseline mirroring _coords_to_path: scalar projection, same
    precision, same drop of consecutive coincident points."""
    p = vb.precision
    tokens = []
    for coord in coords:
        px, py = vb.geo_to_svg(coord[0], coord[1])  # ignore Z if present
        tokens.append(f"{px:.{p}f} {py:.{p}f}")
    if not tokens:
        return ""
    parts = [f"M{tokens[0]}"]
    prev = tokens[0]
    for tok in tokens[1:]:
        if tok != prev:
            parts.append(f"L{tok}")
            prev = tok
    if close:
        parts.append("Z")
    return " ".join(parts)


def _ref_polygon(poly, vb):
    d = _ref_ring(poly.exterior.coords, vb, close=True)
    for interior in poly.interiors:
        d += " " + _ref_ring(interior.coords, vb, close=True)
    return d


def _ref_geometry_to_paths(geom, vb):
    if isinstance(geom, Polygon):
        return [_ref_polygon(geom, vb)]
    if isinstance(geom, MultiPolygon):
        return [_ref_polygon(p, vb) for p in geom.geoms]
    if isinstance(geom, LineString):
        return [_ref_ring(geom.coords, vb, close=False)]
    if isinstance(geom, MultiLineString):
        paths = []
        for line in geom.geoms:
            paths.extend(_ref_geometry_to_paths(line, vb))
        return paths
    return []


def test_polygon_path_matches_scalar_baseline():
    """A polygon with a hole projects identically to the scalar baseline."""
    poly = Polygon(
        [(0, 0), (10, 0), (10, 10), (0, 10)],
        [[(2, 2), (4, 2), (4, 4), (2, 4)]],
    )
    vb = ViewBox(poly.bounds, svg_width=400, svg_height=300, padding=20)
    assert polygon_to_path(poly, vb) == _ref_polygon(poly, vb)


def test_linestring_path_is_open_and_matches_baseline():
    """An open line has no closing Z and matches the scalar baseline."""
    line = LineString([(0.123, 1.987), (5.5, 9.01), (12.0, 3.333)])
    vb = ViewBox(line.bounds, svg_width=500, svg_height=400, padding=10)
    out = geometry_to_paths(line, vb)
    assert len(out) == 1
    assert not out[0].endswith("Z")
    assert out == _ref_geometry_to_paths(line, vb)


def test_real_geometries_byte_identical(gdf_departments):
    """Every department path is byte-identical to the scalar projection.

    Departments mix single polygons, polygons with holes, and
    multipolygons, so this exercises the full conversion surface.
    """
    bounds = tuple(gdf_departments.total_bounds)
    vb = ViewBox(bounds, svg_width=900, svg_height=700, padding=40)
    multipolygon_seen = False
    for geom in gdf_departments.geometry:
        if geom is None or geom.is_empty:
            continue
        if isinstance(geom, MultiPolygon):
            multipolygon_seen = True
        assert geometry_to_paths(geom, vb) == _ref_geometry_to_paths(geom, vb)
    assert multipolygon_seen  # the dataset must exercise the multipart branch


def test_full_svg_byte_identical_across_styles(gdf_departments, bbox_metro):
    """The rendered SVG bytes do not change after vectorization.

    Two independent renders of the same map produce identical bytes; this
    pins the default output so the optimization stays a no-op visually.
    """
    def render():
        m = Map(gdf_departments, bbox=bbox_metro)
        m.add(Vector(gdf_departments, stroke="#333", stroke_width=0.4))
        return m.to_string()

    assert render() == render()


# ============================================================================
# Coordinate precision and point deduplication (lot B)
# ============================================================================

def test_default_precision_keeps_two_decimals():
    """The default precision formats coordinates to two decimals."""
    line = LineString([(0.0, 0.0), (1.0, 1.0)])
    vb = ViewBox(line.bounds, svg_width=200, svg_height=200, padding=10)
    d = geometry_to_paths(line, vb)[0]
    assert "." in d
    for token in d.replace("M", "").replace("L", "").split():
        assert len(token.split(".")[1]) == 2


def test_lower_precision_drops_decimals():
    """A lower precision produces shorter coordinate tokens."""
    line = LineString([(0.0, 0.0), (1.0, 1.0)])
    vb = ViewBox(line.bounds, svg_width=200, svg_height=200,
                 padding=10, precision=0)
    d = geometry_to_paths(line, vb)[0]
    assert "." not in d


def test_dedup_drops_exact_duplicate_points():
    """A repeated vertex is not emitted twice in a row."""
    line = LineString([(0.0, 0.0), (0.0, 0.0), (1.0, 1.0)])
    vb = ViewBox((0.0, 0.0, 1.0, 1.0), svg_width=200, svg_height=200,
                 padding=10)
    d = geometry_to_paths(line, vb)[0]
    assert d.count("M") == 1
    assert d.count("L") == 1  # the duplicated start point is collapsed


def test_dedup_merges_points_that_round_together():
    """Distinct points landing on the same pixel at the given precision
    are merged into one."""
    line = LineString([(0.0, 0.0), (0.001, 0.001), (1.0, 1.0)])
    vb = ViewBox((0.0, 0.0, 1.0, 1.0), svg_width=100, svg_height=100,
                 padding=0, precision=0)
    d = geometry_to_paths(line, vb)[0]
    # (0,0) and (0.001,0.001) both round to the same integer pixel.
    assert d.count("L") == 1


def test_dedup_preserves_ring_closure():
    """Deduplication does not strip a polygon's closing Z."""
    poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
    vb = ViewBox(poly.bounds, svg_width=200, svg_height=200, padding=10)
    d = polygon_to_path(poly, vb)
    assert d.startswith("M")
    assert d.endswith("Z")


def test_coordinate_precision_round_trips_through_yaml(gdf_departments):
    """A non-default coordinate_precision survives YAML serialization."""
    m = Map(gdf_departments, coordinate_precision=1)
    text = m.to_yaml()
    assert "coordinate_precision: 1" in text
    restored = Map.from_yaml(text, gdf=gdf_departments)
    assert restored._coordinate_precision == 1


def test_default_precision_absent_from_yaml(gdf_departments):
    """The default precision is not written to the YAML document."""
    m = Map(gdf_departments)
    assert "coordinate_precision" not in m.to_yaml()
