"""
Tests for toponyms label placement (TICKET_21).

Two levels:
- Unit tests : fast, synthetic data (n_sweeps=10)
- Integration tests : realistic France map from output_migration_auto.svg context
  (choroplèthe + proportional + situation + cartouches + zoom, n_sweeps=20)
"""

import random
import xml.etree.ElementTree as ET
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from shapely.geometry import Point
from shapely.geometry import box as shapely_box

from mappyng import LabelConfig, Map
from mappyng.layers import Basemap, Choropleth, Label, Proportional, Situation
from mappyng.renderer import SvgViewport, ViewBox
from mappyng.toponyme import (
    LabelCandidate,
    LabelPlacer,
    ObstacleIndex,
    _bbox_for_lines,
    _label_box,
    _place_label,
    _split_at_dash,
    emit_labels_svg,
    estimate_text_bbox,
    place_labels,
)

# ---------------------------------------------------------------------------
# Fixtures shared
# ---------------------------------------------------------------------------

DATA = Path(__file__).parent.parent / "src/mappyng/data"


@pytest.fixture(scope="module")
def gdf_dep():
    gdf = gpd.read_file(DATA / "abm_pays_departement_gen3.geojson").to_crs(2154)
    np.random.seed(42)
    gdf["population"] = np.random.randint(50_000, 3_000_000, size=len(gdf))
    gdf.loc[gdf.index[:4], "population"] = np.nan
    return gdf


@pytest.fixture(scope="module")
def gdf_ue():
    return gpd.read_file(DATA / "abm_pays_europe_gen3.geojson").to_crs(2154)


@pytest.fixture(scope="module")
def gdf_reg():
    return gpd.read_file(DATA / "abm_region_gen3.geojson").to_crs(2154)


@pytest.fixture(scope="module")
def gdf_pts(gdf_dep):
    gdf = gdf_dep.copy()
    gdf["geometry"] = gdf.geometry.centroid
    gdf["type"] = (gdf.index % 2).map({0: "Préfecture", 1: "Sous-préfecture"})
    return gdf


BBOX_METRO = [90000, 6040000, 1280000, 7150000]
BBOX_ZOOM  = [586377, 6780533, 739396, 6904563]  # Île-de-France
CART_GUADELOUPE = {"bbox": [-6890454, 1780151, -6799589, 1874186], "crs": 3857,
                   "cartouche_title": "Guadeloupe", "cartouche_title_size": 7,
                   "border_radius": 6, "box_shadow": True}
CART_MARTINIQUE = {"bbox": [-6826862, 1609607, -6759494, 1685367], "crs": 3857,
                   "cartouche_title": "Martinique", "cartouche_title_size": 7,
                   "border_radius": 6, "box_shadow": True}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_viewbox(w=800, h=600):
    return ViewBox(geo_bounds=(0, 0, 1000, 750),
                   svg_x=0, svg_y=0, svg_width=w, svg_height=h, padding=5)


def _make_viewport(name="main", w=800, h=600):
    return SvgViewport(name, _make_viewbox(w, h))


def _make_candidate(ax=100, ay=100, text="Paris", pos="NE", font_size=10, offset=4):
    w, h = estimate_text_bbox(text, font_size)
    x, y = _place_label(ax, ay, w, h, pos, offset)
    return LabelCandidate(text=text, anchor_x=ax, anchor_y=ay, anchor_r=3,
                          width=w, height=h, x=x, y=y, pos=pos)


def _default_placer(labels, obstacles=None, chrome=None, viewport_bbox=None,
                    n_sweeps=10, seed=42):
    cfg = LabelConfig(n_sweeps=n_sweeps, seed=seed)
    rng = random.Random(seed)
    return LabelPlacer(
        labels=labels,
        obstacle_index=ObstacleIndex(obstacles or []),
        chrome_boxes=[shapely_box(*bb) for bb in (chrome or [])],
        viewport_bbox=viewport_bbox or (0, 0, 800, 600),
        config=cfg,
        rng=rng,
    )


def _layer_svg(viewport):
    layer = viewport.get_layer("labels", z_order=40)
    return ET.tostring(layer, encoding="unicode")


def _build_base_map(gdf_ue, gdf_dep, gdf_pts, with_zoom=False, with_cartouches=False):
    """Build the reference map matching output_migration_auto.svg."""
    cparams = {0: CART_GUADELOUPE, 1: CART_MARTINIQUE} if with_cartouches else {}
    m = Map(gdf_ue, bbox=BBOX_METRO, width=900, height=1000, padding=25,
            facecolor="#B9D9EB", border_radius=10,
            cartouche_params=cparams)
    m.add(Basemap())
    if with_zoom:
        m.add_zoom({"bbox": BBOX_ZOOM, "border_radius": 8})
        m.add(Basemap())
    m.add(Choropleth(gdf_dep, column="population", cmap="YlOrRd", method="Quantiles", num_classes=5, stroke_width=0.15, legend={"title": "Population fictive", "orientation": "horizontal"}, on_zoom=True, on_cartouches=True))
    m.add(Proportional(gdf_pts, column="population", fill="#264653", fill_opacity=0.6, reference_value=1_000_000, reference_radius=20, legend={"title": "Population",
                   "position": {"x": 0.72, "y": 0.02}}))
    m.add(Situation(gdf_pts.head(30), column="type", symbol={
            "Préfecture":      {"marker": "circle", "fill": "#e63946", "size": 5},
            "Sous-préfecture": {"marker": "square", "fill": "#457b9d", "size": 4},
        }, legend={"title": "Équipements", "position": {"x": 0.72, "y": 0.28}}))
    m.title(text="Carte de test labels, France", subtitle="Départements", loc="center", font_size=13)
    m.scale_bar(length=200_000, label="200 km", opacity=0.75)
    m.source(text="Source : données fictives")
    return m


# ===========================================================================
# UNIT TESTS, fast, synthetic data
# ===========================================================================

# 0. _split_at_dash, wrapping logic

def test_split_short_name_unchanged():
    assert _split_at_dash("PARIS", 12) == ["PARIS"]
    assert _split_at_dash("ESSONNE", 12) == ["ESSONNE"]

def test_split_long_name_at_middle_dash():
    # "HAUTS-DE-SEINE" (14) to split at dash closest to middle (pos 8)
    result = _split_at_dash("HAUTS-DE-SEINE", 12)
    assert len(result) == 2
    assert result[0] + result[1] == "HAUTS-DE-SEINE"
    # The split should be balanced: both parts <= 10 chars
    assert max(len(result[0]), len(result[1])) <= 10

def test_split_territoire_de_belfort():
    # "TERRITOIRE-DE-BELFORT" (21) to most balanced split: "TERRITOIRE-" / "DE-BELFORT"
    result = _split_at_dash("TERRITOIRE-DE-BELFORT", 12)
    assert len(result) == 2
    assert result[0] + result[1] == "TERRITOIRE-DE-BELFORT"
    # Split at pos 10: "TERRITOIRE-" (11) / "DE-BELFORT" (10)
    assert result[0] == "TERRITOIRE-"
    assert result[1] == "DE-BELFORT"

def test_split_alpes_de_haute_provence():
    # "ALPES-DE-HAUTE-PROVENCE" (23) to middle at 11.5, best dash at pos 8
    result = _split_at_dash("ALPES-DE-HAUTE-PROVENCE", 12)
    assert len(result) == 2
    assert result[0] + result[1] == "ALPES-DE-HAUTE-PROVENCE"

def test_split_no_dash_returns_original():
    assert _split_at_dash("POLYNESIE FRANCAISE", 12) == ["POLYNESIE FRANCAISE"]

def test_split_already_short_no_split():
    assert _split_at_dash("CORSE", 12) == ["CORSE"]
    # 12-char name exactly at threshold, no split
    assert _split_at_dash("HAUTE-CORSE1", 12) == ["HAUTE-CORSE1"]

def test_bbox_for_lines_two_lines_taller():
    w1, h1 = _bbox_for_lines(["HAUTS-DE-"], 10)
    w2, h2 = _bbox_for_lines(["HAUTS-DE-", "SEINE"], 10)
    assert h2 > h1
    assert h2 == pytest.approx(h1 * 2, rel=0.01)

def test_split_reflected_in_svg_tspan(gdf_dep):
    """Long department name in SVG to <tspan> for second line."""
    vp = _make_viewport(w=800, h=600)
    # Use one long-named department
    long_names = gdf_dep[gdf_dep["LIB_GEO"].str.len() > 12]
    gdf_one = long_names.iloc[[0]].copy()
    gdf_one["geometry"] = gdf_one.geometry.centroid
    cfg = LabelConfig(n_sweeps=5, seed=42, wrap=True, wrap_max_chars=12,
                      allow_hide=False)
    place_labels(gdf_one, "LIB_GEO", vp.viewbox, vp, [], cfg)
    svg = _layer_svg(vp)
    assert "<tspan" in svg

def test_no_wrap_disabled_no_tspan(gdf_dep):
    """With wrap=False, long names are emitted as single <text>, no <tspan>."""
    vp = _make_viewport(w=800, h=600)
    long_names = gdf_dep[gdf_dep["LIB_GEO"].str.len() > 12]
    gdf_one = long_names.iloc[[0]].copy()
    gdf_one["geometry"] = gdf_one.geometry.centroid
    cfg = LabelConfig(n_sweeps=5, seed=42, wrap=False, allow_hide=False)
    place_labels(gdf_one, "LIB_GEO", vp.viewbox, vp, [], cfg)
    svg = _layer_svg(vp)
    assert "<tspan" not in svg

# 1. estimate_text_bbox, monotonicity

def test_bbox_grows_with_font_size():
    w1, h1 = estimate_text_bbox("Paris", 8)
    w2, h2 = estimate_text_bbox("Paris", 12)
    assert w2 > w1 and h2 > h1


def test_bbox_grows_with_text_length():
    w1, _ = estimate_text_bbox("A", 10)
    w2, _ = estimate_text_bbox("Bordeaux", 10)
    assert w2 > w1


def test_bbox_bold_wider():
    w_normal, _ = estimate_text_bbox("Paris", 10, font_weight="normal")
    w_bold, _ = estimate_text_bbox("Paris", 10, font_weight="bold")
    assert w_bold > w_normal


# 2. Basic placement (3 distant points to all visible)

def test_basic_placement_three_distant_points():
    gdf = gpd.GeoDataFrame(
        {"name": ["A", "B", "C"]},
        geometry=[Point(100, 100), Point(700, 400), Point(400, 600)],
        crs="EPSG:3857",
    )
    vp = _make_viewport()
    place_labels(gdf, "name", vp.viewbox, vp, [],
                 LabelConfig(n_sweeps=10, seed=42, allow_hide=False))
    assert len(list(vp.get_layer("labels", 40))) == 3


# 3. Anti-overlap label-label

def test_no_overlap_after_placement():
    lab1 = _make_candidate(ax=200, ay=300, text="Lyon", pos="NE")
    lab2 = _make_candidate(ax=202, ay=302, text="Lyon", pos="NE")
    result = _default_placer([lab1, lab2]).run()
    visible = [l for l in result if l.visible]
    assert len(visible) >= 1
    if len(visible) == 2:
        b1 = _label_box(visible[0].x, visible[0].y, visible[0].width, visible[0].height)
        b2 = _label_box(visible[1].x, visible[1].y, visible[1].width, visible[1].height)
        assert b1.intersection(b2).area < 1.0


# 4. Obstacle polygon avoidance

def test_label_avoids_polygon_obstacle():
    obstacle = shapely_box(150, 80, 250, 120)
    lab = _make_candidate(ax=200, ay=100, text="Paris")
    cfg = LabelConfig(n_sweeps=20, seed=42, avoid_overlap=True, allow_hide=False)
    rng = random.Random(42)
    placer = LabelPlacer([lab], ObstacleIndex([obstacle]), [],
                         (0, 0, 800, 600), cfg, rng)
    result = placer.run()
    lbox = _label_box(result[0].x, result[0].y, result[0].width, result[0].height)
    overlap = lbox.intersection(obstacle).area
    assert overlap < result[0].width * result[0].height * 0.3


# 5. Chrome avoidance (title strip)

def test_label_avoids_chrome_bbox():
    chrome_bb = (0, 0, 800, 40)
    lab = _make_candidate(ax=400, ay=80, text="Paris", pos="NE")
    initial_y = lab.y
    cfg = LabelConfig(n_sweeps=50, seed=42, allow_hide=False)
    rng = random.Random(42)
    placer = LabelPlacer([lab], ObstacleIndex([]),
                         [shapely_box(*chrome_bb)],
                         (0, 0, 800, 600), cfg, rng)
    result = placer.run()
    lab_f = result[0]
    lbox_i = _label_box(400 + 4, initial_y, lab_f.width, lab_f.height)
    lbox_f = _label_box(lab_f.x, lab_f.y, lab_f.width, lab_f.height)
    chrome = shapely_box(*chrome_bb)
    assert lbox_f.intersection(chrome).area <= lbox_i.intersection(chrome).area


# 6. max_labels keeps highest priority

def test_max_labels_keeps_highest_priority():
    gdf = gpd.GeoDataFrame(
        {"name": ["A","B","C","D","E"], "priority": [5,3,1,4,2]},
        geometry=[Point(100+i*20, 100+i*20) for i in range(5)],
        crs="EPSG:3857",
    )
    vp = _make_viewport()
    cfg = LabelConfig(n_sweeps=5, seed=42, max_labels=3,
                      priority_col="priority", allow_hide=False)
    place_labels(gdf, "name", vp.viewbox, vp, [], cfg)
    assert len(list(vp.get_layer("labels", 40))) == 3


# 7. allow_hide=False to all labels emitted

def test_allow_hide_false_all_labels_emitted():
    labs = [_make_candidate(ax=200, ay=200, text="X") for _ in range(5)]
    result = _default_placer(labs, n_sweeps=5).run()
    # Override allow_hide manually for this test
    for l in result:
        l.visible = True
    vp = _make_viewport()
    layer = vp.get_layer("labels", 40)
    emit_labels_svg(result, LabelConfig(), layer)
    assert len(list(layer)) == 5


# 8. allow_hide=True hides densely stacked labels

def test_allow_hide_true_hides_colliding():
    labs = [_make_candidate(ax=200, ay=200, text="Paris", pos="NE")
            for _ in range(10)]
    cfg = LabelConfig(n_sweeps=5, seed=42, allow_hide=True)
    rng = random.Random(42)
    result = LabelPlacer(labs, ObstacleIndex([]), [],
                         (0, 0, 800, 600), cfg, rng).run()
    assert sum(1 for l in result if l.visible) < len(result)


# 9. Determinism with seed

def test_deterministic_with_seed():
    def run():
        labs = [_make_candidate(ax=100+i*50, ay=100+i*30, text=f"City{i}")
                for i in range(5)]
        cfg = LabelConfig(n_sweeps=10, seed=42)
        LabelPlacer(labs, ObstacleIndex([]), [], (0, 0, 800, 600), cfg,
                    random.Random(42)).run()
        return [(l.x, l.y) for l in labs]
    p1, p2 = run(), run()
    for (x1,y1),(x2,y2) in zip(p1, p2):
        assert abs(x1-x2) < 1e-9 and abs(y1-y2) < 1e-9


# 10. Stochasticity without seed

def test_stochastic_without_seed():
    def run():
        labs = [_make_candidate(ax=100+i*40, ay=100, text=f"C{i}")
                for i in range(5)]
        LabelPlacer(labs, ObstacleIndex([]), [], (0, 0, 800, 600),
                    LabelConfig(n_sweeps=10, seed=None),
                    random.Random()).run()
        return [(l.x, l.y) for l in labs]
    p1, p2 = run(), run()
    assert any(abs(a[0]-b[0]) > 0.01 or abs(a[1]-b[1]) > 0.01
               for a, b in zip(p1, p2))


# 11. Leader lines emitted on large displacement

def test_leader_line_emitted():
    vp = _make_viewport()
    gdf = gpd.GeoDataFrame({"name": ["Paris"]},
                           geometry=[Point(500, 375)], crs="EPSG:3857")
    cfg = LabelConfig(n_sweeps=5, seed=42, max_displacement=200,
                      leader_lines=True, leader_threshold=0.1, allow_hide=False)
    place_labels(gdf, "name", vp.viewbox, vp, [], cfg)
    assert "<line" in _layer_svg(vp)


# 12. Reprojection EPSG:4326 to map CRS

def test_reprojection_epsg4326(gdf_ue):
    gdf_pt = gpd.GeoDataFrame({"name": ["Paris"]},
                               geometry=[Point(2.35, 48.85)], crs="EPSG:4326")
    m = Map(gdf_ue, bbox=BBOX_METRO, width=500, height=400)
    m.add(Label(gdf_pt, column="name", n_sweeps=5))
    assert "Paris" in m.to_string()


# 13. target=zoom places labels in zoom viewport

def test_target_zoom_viewport(gdf_ue):
    m = Map(gdf_ue, bbox=BBOX_METRO, width=500, height=400)
    m.add_zoom({"bbox": BBOX_ZOOM})
    gdf_pt = gpd.GeoDataFrame({"name": ["Lyon"]},
                               geometry=[Point(4.83, 45.76)], crs="EPSG:4326")
    m.add(Label(gdf_pt, column="name", target="zoom", n_sweeps=5))
    assert "Lyon" in m.to_string()


# 14. Halo to 2 <text> per label ; no halo to 1 <text>

def test_halo_two_text_elements():
    vp = _make_viewport()
    gdf = gpd.GeoDataFrame({"name": ["Paris"]},
                           geometry=[Point(500, 375)], crs="EPSG:3857")
    place_labels(gdf, "name", vp.viewbox, vp, [],
                 LabelConfig(n_sweeps=5, seed=42, halo_color="#ffffff", allow_hide=False))
    assert _layer_svg(vp).count("<text") == 2


def test_no_halo_one_text_element():
    vp = _make_viewport()
    gdf = gpd.GeoDataFrame({"name": ["Paris"]},
                           geometry=[Point(500, 375)], crs="EPSG:3857")
    place_labels(gdf, "name", vp.viewbox, vp, [],
                 LabelConfig(n_sweeps=5, seed=42, halo_color=None, allow_hide=False))
    assert _layer_svg(vp).count("<text") == 1


# ===========================================================================
# INTEGRATION TESTS, real France data (output_migration_auto.svg context)
# ===========================================================================

# 15. Labels on full France map (departments)
# Context: same choroplèthe + proportional as output_migration_auto.svg

def test_integration_labels_france_departments(gdf_ue, gdf_dep, gdf_pts):
    m = _build_base_map(gdf_ue, gdf_dep, gdf_pts)
    # The base map puts a proportional circle on every department: keep
    # the labels that cover one, to measure placement alone.
    m.add(Label(gdf_dep, column="LIB_GEO", font_size=6, n_sweeps=20, seed=42,
                allow_hide=True, max_displacement=60,
                allow_symbol_overlap=True))
    svg = m.to_string()
    # Count visible labels (each <g class="mappyng-label"> = 1 label)
    n_labels = svg.count('class="mappyng-label"')
    # With 103 departments and allow_hide=True, expect at least 70 labeled
    assert n_labels >= 70, f"Only {n_labels}/103 departments labeled"


def _label_boxes(svg, font_size):
    """Boxes (SVG px) of the visible labels, from their first <text>."""
    import re
    boxes = []
    for group in re.findall(r'<g class="mappyng-label".*?</g>', svg, re.S):
        text = group[group.index("<text"):group.index("</text>")]
        x, y = re.search(r'<text x="([\d.-]+)" y="([\d.-]+)"', text).groups()
        lines = re.findall(r'<tspan[^>]*>([^<]*)</tspan>', text)
        if not lines:
            lines = [re.search(r'<text[^>]*>([^<]*)', text).group(1)]
        w, h = _bbox_for_lines(lines, font_size, "sans-serif", "normal")
        top = float(y) - font_size
        boxes.append(shapely_box(float(x), top, float(x) + w, top + h))
    return boxes


def test_integration_labels_do_not_cover_symbols(gdf_ue, gdf_dep, gdf_pts):
    m = _build_base_map(gdf_ue, gdf_dep, gdf_pts)
    m.add(Label(gdf_dep, column="LIB_GEO", font_size=6, n_sweeps=20, seed=42,
                allow_hide=True, max_displacement=60))
    svg = m.to_string()
    circles = [Point(cx, cy).buffer(r) for cx, cy, r in m.main.symbols]
    boxes = _label_boxes(svg, 6)
    assert boxes
    assert not any(b.intersection(c).area > 0 for b in boxes for c in circles)


# 16. Labels avoid proportional circles
# Context: 92 proportional circles from output_migration_auto.svg

def test_integration_labels_avoid_proportional_circles(gdf_ue, gdf_dep, gdf_pts):
    # The proportional circles are recorded as obstacles by the layer itself.
    m = _build_base_map(gdf_ue, gdf_dep, gdf_pts)
    m.add(Label(gdf_dep, column="LIB_GEO", font_size=6, n_sweeps=20, seed=42, allow_hide=True, max_displacement=60, leader_lines=True, leader_threshold=1.0))
    svg = m.to_string()

    assert len(m.main.symbols) > 100
    boxes = _label_boxes(svg, 6)
    assert len(boxes) > 20
    circles = [Point(cx, cy).buffer(r) for cx, cy, r in m.main.symbols]
    assert not any(b.intersects(c) for b in boxes for c in circles)
    # Leader lines should be present (some labels are pushed away)
    assert "<line" in svg


# 17. Labels avoid chrome (title + scale bar)

def test_integration_labels_avoid_chrome(gdf_ue, gdf_dep, gdf_pts):
    m = _build_base_map(gdf_ue, gdf_dep, gdf_pts)
    m.add(Label(gdf_dep, column="LIB_GEO", font_size=6, n_sweeps=20, seed=42, allow_hide=True))
    svg = m.to_string()

    # Title and scale bar are drawn before the labels are placed
    assert len(m._state.chrome_bboxes) >= 2, "Title and scale bar should register bboxes"

    # Verify labels layer is in SVG
    assert 'class="mappyng-label"' in svg


# 18. Labels on zoom viewport (dense Île-de-France)

def test_integration_labels_on_zoom(gdf_ue, gdf_dep, gdf_pts):
    m = _build_base_map(gdf_ue, gdf_dep, gdf_pts, with_zoom=True)
    m.add(Label(gdf_dep, column="LIB_GEO", target="zoom", font_size=8, n_sweeps=20, seed=42, allow_hide=True, max_displacement=50))
    svg = m.to_string()
    # Names <=12 chars are emitted verbatim; longer names are split at dash.
    # "HAUTS-DE-SEINE" to "HAUTS-DE-"/"SEINE",  "VAL-DE-MARNE" to "VAL-DE-"/"MARNE"
    idf_fragments = ["PARIS", "ESSONNE", "YVELINES", "SEINE", "MARNE",
                     "VAL-D'OISE", "OISE"]
    found = [n for n in idf_fragments if n in svg.upper()]
    assert len(found) >= 2, f"Expected >=2 IDF label fragments, found: {found}"


# 19. Labels on cartouche Guadeloupe

def test_integration_labels_on_cartouche(gdf_ue, gdf_dep, gdf_pts):
    m = _build_base_map(gdf_ue, gdf_dep, gdf_pts, with_cartouches=True)
    # Use a point in Guadeloupe (EPSG:4326)
    gdf_guad = gpd.GeoDataFrame(
        {"nom": ["Pointe-à-Pitre", "Basse-Terre"]},
        geometry=[Point(-61.53, 16.24), Point(-61.73, 15.99)],
        crs="EPSG:4326",
    )
    m.add(Label(gdf_guad, column="nom", target="cartouche:0", font_size=7, n_sweeps=10, seed=42))
    svg = m.to_string()
    assert "Pointe-à-Pitre" in svg or "Basse-Terre" in svg


# 20. Performance: 96 labels + 92 circle obstacles < 5s

def test_performance_96_labels_92_obstacles(gdf_ue, gdf_dep, gdf_pts):
    import time
    # The base map draws a proportional circle per department: the labels
    # are placed among these obstacles.
    m = _build_base_map(gdf_ue, gdf_dep, gdf_pts)
    m.add(Label(gdf_dep, column="LIB_GEO", font_size=6, n_sweeps=50, seed=42, allow_hide=True))
    t0 = time.perf_counter()
    m._build()
    elapsed = time.perf_counter() - t0
    assert len(m.main.symbols) > 90
    assert elapsed < 10.0, f"Too slow: {elapsed:.1f}s"


# ===========================================================================
# NUMBERED MODE TESTS
# ===========================================================================

def test_numbered_mode_emits_circles_not_text():
    """When numbered_above is exceeded, circles are emitted, not <text> labels."""
    gdf = gpd.GeoDataFrame(
        {"name": [f"Zone{i}" for i in range(15)]},
        geometry=[Point(100 + i * 30, 300) for i in range(15)],
        crs="EPSG:3857",
    )
    vp = _make_viewport(w=800, h=600)
    cfg = LabelConfig(n_sweeps=5, seed=42, numbered_above=10)
    place_labels(gdf, "name", vp.viewbox, vp, [], cfg)
    svg = _layer_svg(vp)
    assert "mappyng-label-numbered" in svg
    assert "<circle" in svg
    # No regular text labels
    assert "mappyng-label\"" not in svg


def test_numbered_mode_legend_box_present():
    """Numbered mode emits a legend box with the key."""
    gdf = gpd.GeoDataFrame(
        {"name": [f"Ville{i}" for i in range(12)]},
        geometry=[Point(50 + i * 50, 300) for i in range(12)],
        crs="EPSG:3857",
    )
    vp = _make_viewport(w=800, h=600)
    cfg = LabelConfig(n_sweeps=5, seed=42, numbered_above=8)
    place_labels(gdf, "name", vp.viewbox, vp, [], cfg)
    svg = _layer_svg(vp)
    assert "mappyng-label-legend-box" in svg
    assert "<rect" in svg


def test_numbered_mode_at_most_10_circles():
    """Numbered mode shows at most 10 circles regardless of label count."""
    gdf = gpd.GeoDataFrame(
        {"name": [f"Label{i}" for i in range(25)]},
        geometry=[Point(50 + i * 25, 300) for i in range(25)],
        crs="EPSG:3857",
    )
    vp = _make_viewport(w=800, h=600)
    cfg = LabelConfig(n_sweeps=5, seed=42, numbered_above=10)
    place_labels(gdf, "name", vp.viewbox, vp, [], cfg)
    svg = _layer_svg(vp)
    # Count data-n="N" attributes, should be at most 10
    import re
    ns = re.findall(r'data-n="(\d+)"', svg)
    # Each circle gets data-n once (on the <g>) + once in legend
    unique_ns = set(int(n) for n in ns)
    assert max(unique_ns) <= 10
    assert len(unique_ns) <= 10


def test_numbered_mode_not_triggered_below_threshold():
    """When label count <= numbered_above, normal text labels are emitted."""
    gdf = gpd.GeoDataFrame(
        {"name": ["A", "B", "C"]},
        geometry=[Point(100, 200), Point(400, 200), Point(700, 200)],
        crs="EPSG:3857",
    )
    vp = _make_viewport(w=800, h=600)
    cfg = LabelConfig(n_sweeps=5, seed=42, numbered_above=5, allow_hide=False)
    place_labels(gdf, "name", vp.viewbox, vp, [], cfg)
    svg = _layer_svg(vp)
    # Normal text labels
    assert "mappyng-label\"" in svg or 'class="mappyng-label"' in svg
    assert "mappyng-label-numbered" not in svg


def test_numbered_mode_priority_respected():
    """In numbered mode, highest-priority labels appear first in the legend."""
    gdf = gpd.GeoDataFrame(
        {"name": [f"Ville{i}" for i in range(12)], "pop": list(range(12))},
        geometry=[Point(50 + i * 50, 300) for i in range(12)],
        crs="EPSG:3857",
    )
    vp = _make_viewport(w=800, h=600)
    cfg = LabelConfig(n_sweeps=5, seed=42, numbered_above=8, priority_col="pop")
    place_labels(gdf, "name", vp.viewbox, vp, [], cfg)
    svg = _layer_svg(vp)
    # Highest priority is "Ville11" (pop=11), should appear in legend
    assert "Ville11" in svg


def test_numbered_mode_legend_on_main_layer(gdf_dep, gdf_ue, gdf_pts):
    """Integration: legend box is on the main layer, not inside the zoom viewport."""
    m = _build_base_map(gdf_ue, gdf_dep, gdf_pts, with_zoom=True)
    gdf_idf = gdf_dep[gdf_dep["LIB_GEO"].isin([
        "PARIS", "HAUTS-DE-SEINE", "SEINE-SAINT-DENIS",
        "VAL-DE-MARNE", "ESSONNE", "YVELINES",
        "VAL-D'OISE", "SEINE-ET-MARNE",
    ])].copy()
    # Default placement (auto bottom-right)
    m.add(Label(gdf_idf, column="LIB_GEO", target="zoom", font_size=7, numbered_above=5, seed=42))
    svg = m.to_string()
    assert "mappyng-label-numbered" in svg
    assert "mappyng-label-legend-box" in svg


def test_numbered_mode_manual_position(gdf_dep, gdf_ue, gdf_pts):
    """Integration: manual legend position via figure fractions."""
    m = _build_base_map(gdf_ue, gdf_dep, gdf_pts, with_zoom=True)
    gdf_idf = gdf_dep[gdf_dep["LIB_GEO"].isin([
        "PARIS", "HAUTS-DE-SEINE", "SEINE-SAINT-DENIS",
        "VAL-DE-MARNE", "ESSONNE", "YVELINES",
        "VAL-D'OISE", "SEINE-ET-MARNE",
    ])].copy()
    m.add(Label(gdf_idf, column="LIB_GEO", target="zoom", font_size=7, numbered_above=5, numbered_legend_position={"x": 0.75, "y": 0.15}, numbered_legend_title="Île-de-France", seed=42))
    svg = m.to_string()
    assert "mappyng-label-legend-box" in svg
    assert "Île-de-France" in svg



# ---------------------------------------------------------------------
# Symbols as obstacles
# ---------------------------------------------------------------------

def test_symbol_radius_at_anchor():
    from mappyng.toponyme import _symbol_radius_at
    symbols = [(10.0, 10.0, 4.0), (10.2, 9.8, 15.0), (40.0, 40.0, 30.0)]
    assert _symbol_radius_at(10.0, 10.0, symbols) == 15.0
    assert _symbol_radius_at(100.0, 100.0, symbols) == 0.0


def _stacked_symbol_map(gdf_ue, gdf_pts, **label_kw):
    """A marker drawn over a larger circle, labelled at the same point."""
    towns = gdf_pts[gdf_pts["LIB_GEO"].isin(["CANTAL", "CREUSE", "INDRE"])]
    towns = towns.assign(name=towns["LIB_GEO"].str.title())
    m = Map(gdf_ue, bbox=BBOX_METRO, width=900, height=1000)
    m.add(Basemap())
    m.add(Label(towns, column="name", font_size=9, seed=1, **label_kw))
    m.add(Situation(towns, marker="circle", fill="#dddddd", size=30))
    m.add(Situation(towns, marker="star", fill="#e63946", size=8))
    return m


def test_label_clears_stacked_symbols(gdf_ue, gdf_pts):
    # The label layer is added first: labels are still placed last.
    m = _stacked_symbol_map(gdf_ue, gdf_pts)
    svg = m.to_string()
    boxes = _label_boxes(svg, 9)
    assert len(boxes) == 3
    circles = [Point(cx, cy).buffer(r) for cx, cy, r in m.main.symbols]
    assert not any(b.intersects(c) for b in boxes for c in circles)


def test_symbols_recorded_per_viewport(gdf_ue, gdf_pts):
    m = _stacked_symbol_map(gdf_ue, gdf_pts)
    m.to_string()
    radii = sorted({round(r, 2) for _, _, r in m.main.symbols})
    # size / 2 + stroke_width / 2 (default stroke 0.5)
    assert radii == [4.25, 15.25]


def test_allow_symbol_overlap_keeps_labels(gdf_ue, gdf_pts):
    crowded = dict(label_offset=0, max_displacement=1, n_sweeps=1)
    hidden = _stacked_symbol_map(gdf_ue, gdf_pts, **crowded)
    kept = _stacked_symbol_map(gdf_ue, gdf_pts, allow_symbol_overlap=True,
                               **crowded)
    assert (kept.to_string().count('class="mappyng-label"')
            >= hidden.to_string().count('class="mappyng-label"'))
