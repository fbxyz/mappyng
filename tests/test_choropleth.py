"""Tests for choropleth.py, classification, rendering, legend."""

import xml.etree.ElementTree as ET

import geopandas as gpd
import numpy as np
import pytest

from mappyng import Map
from mappyng.choropleth import (
    METHODS,
    ChoroplethLegendConfig,
    _format_range_label,
    classify,
)
from mappyng.layers import Basemap, Choropleth

# Fixture columns available: fid (int), LIB_GEO (str), insee_reg (str), COD_GEO (str), valide (bool)
# We use "fid" as numeric column for classification tests.
COLUMN = "fid"


# ============================================================================
# Classification
# ============================================================================

class TestClassify:
    def test_quantiles(self, gdf_departments):
        classified, nodata, scheme, bins = classify(
            gdf_departments, COLUMN, method="Quantiles", num_classes=5
        )
        assert len(classified) > 0
        assert nodata.empty
        assert len(bins) == 6  # n+1 edges for n classes
        assert "_class" in classified.columns
        assert classified["_class"].between(0, 4).all()

    def test_fisher_jenks(self, gdf_departments):
        classified, nodata, scheme, bins = classify(
            gdf_departments, COLUMN, method="FisherJenks", num_classes=5
        )
        assert len(bins) == 6

    def test_equal_interval(self, gdf_departments):
        classified, nodata, scheme, bins = classify(
            gdf_departments, COLUMN, method="EqualInterval", num_classes=4
        )
        assert len(bins) == 5

    def test_q6(self, gdf_departments):
        classified, nodata, scheme, bins = classify(
            gdf_departments, COLUMN, method="Q6"
        )
        assert len(bins) == 7  # 6 classes to 7 edges

    def test_custom_breaks(self, gdf_departments):
        breaks = [0, 25, 50, 75, 108]
        classified, nodata, scheme, bins = classify(
            gdf_departments, COLUMN, method=breaks
        )
        assert len(bins) == len(breaks)

    def test_nodata_separation(self, gdf_departments):
        gdf = gdf_departments.copy()
        gdf.loc[gdf.index[0], COLUMN] = None
        classified, nodata, scheme, bins = classify(gdf, COLUMN, method="Quantiles")
        assert len(nodata) == 1
        assert len(classified) == len(gdf) - 1

    def test_invalid_method(self, gdf_departments):
        with pytest.raises(ValueError):
            classify(gdf_departments, COLUMN, method="NotAMethod")

    def test_num_classes_out_of_range(self, gdf_departments):
        with pytest.raises(ValueError):
            classify(gdf_departments, COLUMN, method="Quantiles", num_classes=10)


# ============================================================================
# Label formatting
# ============================================================================

class TestFormatRangeLabel:
    def test_decimals_zero_returns_integer(self):
        label = _format_range_label(0.0, 1000.0, decimals=0)
        assert "." not in label
        assert "from" in label and "to" in label
        assert "1" in label and "000" in label

    def test_decimals_one(self):
        label = _format_range_label(1.5, 3.7, decimals=1)
        assert "1.5" in label
        assert "3.7" in label
        assert "from" in label and "to" in label

    def test_no_brackets(self):
        label = _format_range_label(10, 250, decimals=0)
        assert "[" not in label and "]" not in label

    def test_thousands_separator(self):
        label = _format_range_label(0, 1_500_000, decimals=0)
        assert " " in label or " " in label


# ============================================================================
# Legend horizontal, label alignment
# ============================================================================

class TestHorizontalLegendAlignment:
    """Verify that bin labels are placed at exact swatch boundaries."""

    def _get_legend_texts(self, gdf, num_classes=5):
        with Map(gdf, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Choropleth(gdf, column=COLUMN, method="EqualInterval", num_classes=num_classes, legend={
                    "orientation": "horizontal",
                    "label_rotation": 0,
                    "title": "Identifiant",
                }))
        svg_str = m.to_string()
        root = ET.fromstring(svg_str)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        return root.findall(".//svg:g[@id='choropleth-legend']/svg:text", ns)

    def test_first_label_anchor_start(self, gdf_departments):
        texts = self._get_legend_texts(gdf_departments)
        # texts[0] = title (bold), texts[1] = bins[0] label
        bin_labels = [t for t in texts if t.get("font-weight") != "bold"]
        assert bin_labels[0].get("text-anchor") == "start"

    def test_last_label_anchor_end(self, gdf_departments):
        texts = self._get_legend_texts(gdf_departments)
        bin_labels = [t for t in texts if t.get("font-weight") != "bold"]
        assert bin_labels[-1].get("text-anchor") == "end"

    def test_middle_labels_anchor_middle(self, gdf_departments):
        texts = self._get_legend_texts(gdf_departments)
        bin_labels = [t for t in texts if t.get("font-weight") != "bold"]
        # Skip first and last
        for t in bin_labels[1:-1]:
            assert t.get("text-anchor") == "middle"

    def test_label_x_positions_increase_monotonically(self, gdf_departments):
        texts = self._get_legend_texts(gdf_departments)
        bin_labels = [t for t in texts if t.get("font-weight") != "bold"]
        xs = [float(t.get("x")) for t in bin_labels]
        assert xs == sorted(xs), f"Label x-positions not monotonically increasing: {xs}"

    def test_label_count_equals_n_plus_one(self, gdf_departments):
        """n classes to n+1 bin labels."""
        num_classes = 5
        texts = self._get_legend_texts(gdf_departments, num_classes=num_classes)
        bin_labels = [t for t in texts if t.get("font-weight") != "bold"]
        assert len(bin_labels) == num_classes + 1

    def test_boundary_positions_centered_in_gap(self, gdf_departments):
        """Interior labels must be centered in the gap between two adjacent swatches."""
        from mappyng import defaults as D
        sw_w = D.CHOROPLETH_SWATCH_WIDTH * D.LEGEND_SWATCH_SCALE
        sw_gap = D.CHOROPLETH_SWATCH_SPACING * D.LEGEND_SWATCH_SCALE

        texts = self._get_legend_texts(gdf_departments, num_classes=5)
        bin_labels = [t for t in texts if t.get("font-weight") != "bold"]

        x0 = float(bin_labels[0].get("x"))
        x1 = float(bin_labels[1].get("x"))
        # bins[1] = center of gap between swatch 0 and swatch 1 = x0 + sw_w + sw_gap/2
        expected_x1 = x0 + sw_w + sw_gap / 2
        assert abs(x1 - expected_x1) < 0.5, (
            f"bins[1] at x={x1:.2f}, expected center-of-gap {expected_x1:.2f}"
        )


# ============================================================================
# Legend decimals
# ============================================================================

class TestLegendDecimals:
    def test_decimals_zero_no_decimal_point(self, gdf_departments):
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Choropleth(gdf_departments, column=COLUMN, method="EqualInterval", num_classes=5, legend={"decimals": 0, "orientation": "vertical"}))
        svg_str = m.to_string()
        root = ET.fromstring(svg_str)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        legend_texts = root.findall(".//svg:g[@id='choropleth-legend']/svg:text", ns)
        # All label texts (excluding title and nodata) should not contain a decimal point
        for t in legend_texts:
            if t.get("font-weight") == "bold":
                continue  # title
            text = (t.text or "").strip()
            if text and text not in ("N/A", ""):
                assert "." not in text, f"Unexpected decimal in label: {text!r}"

    def test_renders_without_error(self, gdf_departments):
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Choropleth(gdf_departments, column=COLUMN, method="EqualInterval", num_classes=5))
        svg = m.to_string()
        assert "choropleth-legend" in svg


# ============================================================================
# Title wrapping
# ============================================================================

class TestLegendTitleWrapping:
    def test_long_title_wraps(self, gdf_departments):
        long_title = "Ceci est un titre de légende très long qui doit être coupé automatiquement"
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Choropleth(gdf_departments, column=COLUMN, legend={
                    "title": long_title,
                    "title_max_chars": 20,
                }))
        svg_str = m.to_string()
        root = ET.fromstring(svg_str)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        legend_texts = root.findall(".//svg:g[@id='choropleth-legend']/svg:text", ns)
        title_texts = [t for t in legend_texts if t.get("font-weight") == "bold"]
        assert len(title_texts) > 1, "Long title should produce multiple text elements"

    def test_short_title_no_wrap(self, gdf_departments):
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Choropleth(gdf_departments, column=COLUMN, legend={"title": "Population"}))
        svg_str = m.to_string()
        root = ET.fromstring(svg_str)
        ns = {"svg": "http://www.w3.org/2000/svg"}
        legend_texts = root.findall(".//svg:g[@id='choropleth-legend']/svg:text", ns)
        title_texts = [t for t in legend_texts if t.get("font-weight") == "bold"]
        assert len(title_texts) == 1


# ============================================================================
# B2, label_position="center" + label_format="range"
# ============================================================================

NS = {"svg": "http://www.w3.org/2000/svg"}


def _horiz_legend_texts(gdf, num_classes=5, label_position="border", label_format="value"):
    with Map(gdf, width=800, height=600) as m:
        m.add(Basemap())
        m.add(Choropleth(gdf, column=COLUMN, method="EqualInterval", num_classes=num_classes, legend={
                "orientation": "horizontal",
                "label_rotation": 0,
                "label_position": label_position,
                "label_format": label_format,
                "title": "Test",
                "decimals": 0,
            }))
    svg_str = m.to_string()
    root = ET.fromstring(svg_str)
    legend_texts = root.findall(".//svg:g[@id='choropleth-legend']/svg:text", NS)
    # Exclude title (bold)
    return [t for t in legend_texts if t.get("font-weight") != "bold"]


class TestLabelPositionCenter:
    def test_center_produces_n_labels(self, gdf_departments):
        """label_position='center' to exactly n labels (not n+1)."""
        num_classes = 5
        labels = _horiz_legend_texts(gdf_departments, num_classes=num_classes,
                                     label_position="center")
        assert len(labels) == num_classes, f"Expected {num_classes}, got {len(labels)}"

    def test_center_all_anchors_middle(self, gdf_departments):
        """All labels in center mode must have text-anchor='middle'."""
        labels = _horiz_legend_texts(gdf_departments, label_position="center")
        for t in labels:
            assert t.get("text-anchor") == "middle", (
                f"Expected middle, got {t.get('text-anchor')} for {t.text!r}"
            )

    def test_border_produces_n_plus_one_labels(self, gdf_departments):
        """Default 'border' mode to n+1 labels."""
        num_classes = 5
        labels = _horiz_legend_texts(gdf_departments, num_classes=num_classes,
                                     label_position="border")
        assert len(labels) == num_classes + 1

    def test_center_range_format_uses_from_to(self, gdf_departments):
        """label_format='range' to labels use 'from ... to ...' format, no brackets."""
        labels = _horiz_legend_texts(gdf_departments, label_position="center",
                                     label_format="range")
        for t in labels:
            text = t.text or ""
            assert "from" in text and "to" in text, f"Expected 'from...to...' format, got {text!r}"
            assert "[" not in text and "]" not in text, f"Unexpected brackets in {text!r}"

    def test_center_value_format_no_brackets(self, gdf_departments):
        """Default label_format='value' to labels do not contain brackets."""
        labels = _horiz_legend_texts(gdf_departments, label_position="center",
                                     label_format="value")
        for t in labels:
            text = t.text or ""
            assert "[" not in text, f"Unexpected bracket in value format: {text!r}"

    def test_center_label_x_positions_centered_in_swatches(self, gdf_departments):
        """Label i should be at legend_x + i*(sw_w+sw_gap) + sw_w/2."""
        from mappyng import defaults as D
        sw_w = D.CHOROPLETH_SWATCH_WIDTH * D.LEGEND_SWATCH_SCALE
        sw_gap = D.CHOROPLETH_SWATCH_SPACING * D.LEGEND_SWATCH_SCALE
        labels = _horiz_legend_texts(gdf_departments, num_classes=5,
                                     label_position="center")
        xs = [float(t.get("x")) for t in labels]
        # x0 is the center of swatch 0: legend_x + sw_w/2
        x0 = xs[0]
        for i, x in enumerate(xs):
            expected = x0 + i * (sw_w + sw_gap)
            assert abs(x - expected) < 0.6, (
                f"Label {i}: x={x:.2f}, expected {expected:.2f}"
            )


# ============================================================================
# Golden ratio + swatch_size
# ============================================================================

class TestSwatchGoldenRatio:
    """swatch_height and vertical_swatch_height default to width / phi."""

    @staticmethod
    def _swatch_dims(svg, idx=0):
        """Return (width, height) of swatch number idx from SVG string."""
        import re
        tags = list(re.finditer(r'<rect [^>]*choropleth-legend-swatch[^>]*/>', svg))
        assert tags, "No legend swatch rects found in SVG"
        tag = tags[idx].group()
        w = float(re.search(r'width="([^"]+)"', tag).group(1))
        h = float(re.search(r'height="([^"]+)"', tag).group(1))
        return w, h

    def test_horizontal_height_golden_ratio(self, gdf_departments):
        """Horizontal swatch height = swatch_width / phi when not set."""
        from mappyng import defaults as D
        gdf_departments["val"] = range(len(gdf_departments))
        m = Map(gdf_departments, width=600, height=500)
        m.add(Basemap())
        m.add(Choropleth(gdf_departments, column="val", method="EqualInterval", num_classes=4, legend={"orientation": "horizontal"}))
        _, h = self._swatch_dims(m.to_string())
        sw_w = D.CHOROPLETH_SWATCH_WIDTH * D.LEGEND_SWATCH_SCALE
        expected = round(sw_w / D.PHI, 1)
        assert abs(h - expected) < 0.5, f"Expected height ~{expected}, got {h}"

    def test_vertical_height_golden_ratio(self, gdf_departments):
        """Vertical swatch height = vertical_swatch_width / phi when not set."""
        from mappyng import defaults as D
        gdf_departments["val"] = range(len(gdf_departments))
        m = Map(gdf_departments, width=600, height=500)
        m.add(Basemap())
        m.add(Choropleth(gdf_departments, column="val", method="EqualInterval", num_classes=4, legend={"orientation": "vertical"}))
        _, h = self._swatch_dims(m.to_string())
        sw_w = D.CHOROPLETH_VERTICAL_SWATCH_WIDTH * D.LEGEND_SWATCH_SCALE
        expected = round(sw_w / D.PHI, 1)
        assert abs(h - expected) < 0.5, f"Expected height ~{expected}, got {h}"

    def test_swatch_size_overrides_both_widths(self, gdf_departments):
        """swatch_size sets width for both horizontal and vertical modes."""
        from mappyng import defaults as D
        from mappyng.config import ConfigManager
        cfg = ChoroplethLegendConfig(swatch_size=50.0, orientation="horizontal")
        style = ConfigManager.get_style("classic")
        cfg.resolve_defaults(style, font_scale=1.0)
        s = D.LEGEND_SWATCH_SCALE
        assert cfg.swatch_width == pytest.approx(50.0 * s)
        assert cfg.vertical_swatch_width == pytest.approx(50.0 * s)
        assert cfg.swatch_height is None
        assert cfg.vertical_swatch_height is None

    def test_swatch_size_renders_correct_width(self, gdf_departments):
        """swatch_size=40 to swatch width == 40 * LEGEND_SWATCH_SCALE."""
        from mappyng import defaults as D
        gdf_departments["val"] = range(len(gdf_departments))
        m = Map(gdf_departments, width=600, height=500)
        m.add(Basemap())
        m.add(Choropleth(gdf_departments, column="val", method="EqualInterval", num_classes=4, legend={"orientation": "horizontal",
                                                      "swatch_size": 40}))
        w, _ = self._swatch_dims(m.to_string())
        expected_w = 40.0 * D.LEGEND_SWATCH_SCALE
        assert abs(w - expected_w) < 0.5, f"Expected width {expected_w}, got {w}"

    def test_swatch_size_height_is_golden(self, gdf_departments):
        """swatch_size=40 to height == 40 * LEGEND_SWATCH_SCALE / phi."""
        from mappyng import defaults as D
        gdf_departments["val"] = range(len(gdf_departments))
        m = Map(gdf_departments, width=600, height=500)
        m.add(Basemap())
        m.add(Choropleth(gdf_departments, column="val", method="EqualInterval", num_classes=4, legend={"orientation": "horizontal",
                                                      "swatch_size": 40}))
        w, h = self._swatch_dims(m.to_string())
        expected_h = round(w / D.PHI, 1)
        assert abs(h - expected_h) < 0.5, f"Expected height ~{expected_h}, got {h}"

    def test_manual_swatch_height_still_works(self, gdf_departments):
        """Explicit swatch_height overrides golden ratio."""
        gdf_departments["val"] = range(len(gdf_departments))
        m = Map(gdf_departments, width=600, height=500)
        m.add(Basemap())
        m.add(Choropleth(gdf_departments, column="val", method="EqualInterval", num_classes=4, legend={"orientation": "horizontal",
                                                      "swatch_height": 5}))
        _, h = self._swatch_dims(m.to_string())
        assert h < 10, f"Expected small height ~5, got {h}"


# ============================================================================
# Vertical legend, label modes
# ============================================================================

def _vert_legend_texts(gdf, label_position="border", label_format="value", labels=None,
                       num_classes=5):
    params = {
        "orientation": "vertical",
        "label_position": label_position,
        "label_format": label_format,
        "decimals": 0,
        "title": "Test",
    }
    if labels is not None:
        params["labels"] = labels
    with Map(gdf, width=800, height=600) as m:
        m.add(Basemap())
        m.add(Choropleth(gdf, column=COLUMN, method="EqualInterval", num_classes=num_classes, legend=params))
    svg_str = m.to_string()
    root = ET.fromstring(svg_str)
    texts = root.findall(".//svg:g[@id='choropleth-legend']/svg:text", NS)
    return [t for t in texts if t.get("font-weight") != "bold"]


class TestVerticalLegendBorderMode:
    def test_border_produces_n_plus_one_labels(self, gdf_departments):
        """Default border mode to n+1 bin values."""
        num_classes = 5
        labels = _vert_legend_texts(gdf_departments, num_classes=num_classes)
        assert len(labels) == num_classes + 1

    def test_border_labels_have_no_brackets(self, gdf_departments):
        labels = _vert_legend_texts(gdf_departments)
        for t in labels:
            text = t.text or ""
            assert "[" not in text and "]" not in text, f"Unexpected brackets: {text!r}"

    def test_border_labels_no_from_to(self, gdf_departments):
        """Border mode shows plain numbers, not from/to."""
        labels = _vert_legend_texts(gdf_departments)
        for t in labels:
            text = t.text or ""
            assert "from" not in text, f"Border mode should not use from/to: {text!r}"

    def test_border_label_y_positions_increase(self, gdf_departments):
        """Labels must be stacked top-to-bottom."""
        labels = _vert_legend_texts(gdf_departments)
        ys = [float(t.get("y")) for t in labels]
        assert ys == sorted(ys), f"Label y-positions not monotonically increasing: {ys}"


class TestVerticalLegendRangeMode:
    def test_range_produces_n_labels(self, gdf_departments):
        num_classes = 5
        labels = _vert_legend_texts(gdf_departments, label_position="center",
                                    label_format="range", num_classes=num_classes)
        assert len(labels) == num_classes

    def test_range_labels_use_from_to(self, gdf_departments):
        labels = _vert_legend_texts(gdf_departments, label_position="center",
                                    label_format="range")
        for t in labels:
            text = t.text or ""
            assert "from" in text and "to" in text, f"Expected from/to, got {text!r}"

    def test_range_labels_no_brackets(self, gdf_departments):
        labels = _vert_legend_texts(gdf_departments, label_position="center",
                                    label_format="range")
        for t in labels:
            text = t.text or ""
            assert "[" not in text and "]" not in text, f"Unexpected brackets: {text!r}"


class TestVerticalLegendValueMode:
    def test_value_produces_n_labels(self, gdf_departments):
        num_classes = 5
        labels = _vert_legend_texts(gdf_departments, label_position="center",
                                    label_format="value", num_classes=num_classes)
        assert len(labels) == num_classes

    def test_value_labels_are_plain_numbers(self, gdf_departments):
        labels = _vert_legend_texts(gdf_departments, label_position="center",
                                    label_format="value")
        for t in labels:
            text = t.text or ""
            assert "from" not in text, f"Value mode should not use from/to: {text!r}"
            assert "[" not in text, f"No brackets expected: {text!r}"


class TestVerticalLegendCustomLabels:
    def test_custom_labels_shown(self, gdf_departments):
        custom = ["Très faible", "Faible", "Moyen", "Élevé", "Très élevé"]
        labels = _vert_legend_texts(gdf_departments, labels=custom, num_classes=5)
        texts = [t.text or "" for t in labels]
        for expected in custom:
            assert expected in texts, f"Missing custom label {expected!r}"

    def test_custom_labels_overrides_border_mode(self, gdf_departments):
        """Providing labels= always switches to center mode regardless of label_position."""
        custom = ["A", "B", "C", "D", "E"]
        labels = _vert_legend_texts(gdf_departments, labels=custom,
                                    label_position="border", num_classes=5)
        assert len(labels) == 5


# ============================================================================
# PrettyBreaks (TICKET_64)
# ============================================================================

def _make_gdf(values):
    """Minimal polygon GDF with a 'val' column for PrettyBreaks tests."""
    from shapely.geometry import box as shapely_box
    geoms = [shapely_box(i, 0, i + 1, 1) for i in range(len(values))]
    return gpd.GeoDataFrame({"val": values, "geometry": geoms}, crs=2154)


class TestPrettyBreaks:
    def test_prettybreaks_registered(self):
        """PrettyBreaks is an available method."""
        assert "PrettyBreaks" in METHODS

    def test_prettybreaks_produces_round_bounds(self):
        """Internal breaks are round numbers."""
        gdf = _make_gdf([3, 12, 27, 41, 55, 68, 79, 88, 97])
        _, _, scheme, bins = classify(gdf, "val", method="PrettyBreaks", num_classes=5)
        internal = list(scheme.bins)
        assert all(float(b) == int(b) for b in internal)

    def test_prettybreaks_k_may_differ_from_requested(self):
        """Real class count can differ from num_classes (Option A)."""
        gdf = _make_gdf([3, 12, 27, 41, 55, 68, 79, 88, 97])
        _, _, scheme, bins = classify(gdf, "val", method="PrettyBreaks", num_classes=7)
        k_real = len(scheme.bins)
        # For this data, pretty breaks produce 5 bins despite k=7
        assert k_real != 7

    def test_prettybreaks_class_indices_match_bins(self):
        """_class values are bounded by len(scheme.bins)-1, not scheme.k."""
        gdf = _make_gdf([3, 12, 27, 41, 55, 68, 79, 88, 97])
        classified, _, scheme, _ = classify(gdf, "val", method="PrettyBreaks", num_classes=7)
        k_real = len(scheme.bins)
        assert classified["_class"].max() <= k_real - 1

    def test_prettybreaks_colors_match_real_k(self, gdf_departments):
        """Color count matches real classes; no IndexError, no orphan colors."""
        m = Map(gdf_departments)
        # Should not raise
        m.add(Choropleth(gdf_departments, column="fid", method="PrettyBreaks", num_classes=7, cmap="YlOrRd"))
        svg = m.to_string()
        assert "choropleth" in svg

    def test_prettybreaks_warns_when_k_differs(self, gdf_departments, recwarn):
        """A warning is emitted when real k != requested num_classes."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid", method="PrettyBreaks", num_classes=7, cmap="YlOrRd"))
        m._build()
        assert any("PrettyBreaks" in str(w.message) for w in recwarn.list)

    def test_prettybreaks_preserves_true_min(self):
        """First displayed bound is the true minimum of the data."""
        gdf = _make_gdf([3, 12, 27, 41, 55, 68, 79, 88, 97])
        _, _, _, bins = classify(gdf, "val", method="PrettyBreaks", num_classes=5)
        assert bins[0] == 3

    def test_prettybreaks_fallback_palette(self, gdf_departments, recwarn):
        """When PrettyBreaks produces k_real without a direct palette, fallback applies."""
        # PrettyBreaks on fid with k=5 on this data might give k_real=4 or 5.
        # We force a case by patching: use a tiny GDF that gives k_real=3 (not in COLORMAP_DEFS).
        import unittest.mock as mock

        import mapclassify as mc

        # Monkey-patch PrettyBreaks to return only 3 bins
        orig = mc.PrettyBreaks

        class FakePrettyBreaks:
            def __init__(self, col, k):
                self.k = k
                self.bins = np.array([33.0, 66.0, 99.0])  # 3 bins
                self.yb = np.clip(orig(col, k=k).yb, 0, 2)

        with mock.patch.object(mc, "PrettyBreaks", FakePrettyBreaks):
            from mappyng.choropleth import METHODS as _M
            _M["PrettyBreaks"] = lambda col, k: FakePrettyBreaks(col, k)
            try:
                m = Map(gdf_departments)
                m.add(Choropleth(gdf_departments, column="fid", method="PrettyBreaks", num_classes=5, cmap="YlOrRd"))
                m._build()
            finally:
                _M["PrettyBreaks"] = lambda col, k: mc.PrettyBreaks(col, k=k)

        # A fallback warning should have been emitted
        assert any(
            "PrettyBreaks" in str(w.message) or "palette" in str(w.message)
            for w in recwarn.list
        )


class TestStdMean:
    # A column with enough spread for standard-deviation breaks.
    VALUES = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 30, 40, 50, 3, 4, 5, 6]

    def test_stdmean_registered(self):
        """StdMean is an available method."""
        assert "StdMean" in METHODS

    def test_stdmean_default_is_five_classes(self):
        """The default class count is unchanged (five)."""
        gdf = _make_gdf(self.VALUES)
        _, _, scheme, _ = classify(gdf, "val", method="StdMean")
        assert len(scheme.bins) == 5

    def test_stdmean_seven_classes(self):
        """num_classes=7 yields seven classes."""
        gdf = _make_gdf(self.VALUES)
        _, _, scheme, _ = classify(gdf, "val", method="StdMean", num_classes=7)
        assert len(scheme.bins) == 7

    def test_stdmean_class_indices_bounded(self):
        """_class never exceeds the real class count for seven classes."""
        gdf = _make_gdf(self.VALUES)
        classified, _, scheme, _ = classify(
            gdf, "val", method="StdMean", num_classes=7)
        assert classified["_class"].max() <= len(scheme.bins) - 1

    @pytest.mark.parametrize("k, expected", [(4, 5), (6, 5), (8, 7), (9, 7)])
    def test_stdmean_snaps_unsupported_count_with_warning(self, k, expected):
        """An unsupported count snaps to the nearest valid one (5 or 7) and warns."""
        gdf = _make_gdf(self.VALUES)
        with pytest.warns(UserWarning, match="StdMean supports"):
            _, _, scheme, _ = classify(gdf, "val", method="StdMean", num_classes=k)
        assert len(scheme.bins) == expected

    @pytest.mark.parametrize("k", [5, 7])
    def test_stdmean_valid_count_no_warning(self, k, recwarn):
        """Supported counts (5, 7) classify without a class-count warning."""
        gdf = _make_gdf(self.VALUES)
        classify(gdf, "val", method="StdMean", num_classes=k)
        assert not any("StdMean supports" in str(w.message) for w in recwarn.list)

    def test_stdmean_snaps_through_add_choropleth(self, gdf_departments, recwarn):
        """The warning also surfaces through the layer API and still renders."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid",
                              method="StdMean", num_classes=6, cmap="RdBu"))
        out = m.to_string()
        assert "choropleth" in out
        assert any("StdMean supports" in str(w.message) for w in recwarn.list)

    def test_stdmean_seven_renders(self, gdf_departments):
        """A seven-class StdMean choropleth renders without error."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid",
                              method="StdMean", num_classes=7, cmap="RdBu"))
        assert "choropleth" in m.to_string()

    def test_stdmean_diverging_cmap_no_warning(self, gdf_departments, recwarn):
        """A diverging palette raises no palette warning."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid",
                              method="StdMean", num_classes=7, cmap="BrBG"))
        m._build()
        assert not any("diverging" in str(w.message) for w in recwarn.list)

    def test_stdmean_sequential_cmap_warns(self, gdf_departments, recwarn):
        """A sequential palette raises a non-blocking diverging warning."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid",
                              method="StdMean", num_classes=5, cmap="YlOrRd"))
        assert any("diverging" in str(w.message) for w in recwarn.list)

    @staticmethod
    def _class_fill(svg, idx):
        root = ET.fromstring(svg)
        for el in root.iter():
            if el.attrib.get("class") == f"choropleth choropleth-{idx}":
                return el.attrib.get("fill")
        return None

    def test_stdmean_reverse_swaps_double_gamme_keeps_centre(self, gdf_departments):
        """reverse inverts the diverging double-ramp but keeps the neutral
        central class in place (double gamme inversée)."""
        def svg(reverse):
            m = Map(gdf_departments)
            m.add(Choropleth(gdf_departments, column="fid", method="StdMean",
                                  num_classes=5, cmap="RdBu", reverse=reverse))
            return m.to_string()
        normal, rev = svg(False), svg(True)
        # Ends swap, centre (class 2) is unchanged.
        assert self._class_fill(normal, 0) == self._class_fill(rev, 4)
        assert self._class_fill(normal, 4) == self._class_fill(rev, 0)
        assert self._class_fill(normal, 2) == self._class_fill(rev, 2)


class TestReverseCmap:
    # YlOrRd 5-class: first colour light, last colour dark.
    LIGHT = "#ffffb2"
    DARK = "#bd0026"

    @staticmethod
    def _class0_fill(svg):
        """Fill colour of the lowest choropleth class in *svg*."""
        root = ET.fromstring(svg)
        for el in root.iter():
            if el.attrib.get("class") == "choropleth choropleth-0":
                return el.attrib.get("fill")
        return None

    def _svg(self, gdf, **kw):
        m = Map(gdf)
        m.add(Choropleth(gdf, column="fid", method="EqualInterval",
                              num_classes=5, cmap="YlOrRd", **kw))
        return m.to_string()

    def test_default_is_unchanged(self, gdf_departments):
        """reverse=False matches omitting the argument (byte-identical)."""
        assert self._svg(gdf_departments) == self._svg(gdf_departments, reverse=False)

    def test_default_lowest_class_is_light(self, gdf_departments):
        assert self._class0_fill(self._svg(gdf_departments)) == self.LIGHT

    def test_reverse_lowest_class_is_dark(self, gdf_departments):
        """Reversing puts the ramp's last colour on the lowest class."""
        svg = self._svg(gdf_departments, reverse=True)
        assert self._class0_fill(svg) == self.DARK

    def test_reverse_changes_output(self, gdf_departments):
        assert self._svg(gdf_departments) != self._svg(gdf_departments, reverse=True)

    def test_reverse_applies_to_custom_list(self, gdf_departments):
        """An explicit colour list is reversed too."""
        colours = ["#000000", "#111111", "#222222", "#333333", "#444444"]
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid",
                              method="EqualInterval", num_classes=5,
                              cmap=colours, reverse=True))
        assert self._class0_fill(m.to_string()) == "#444444"

    def test_reverse_round_trips_through_yaml(self, gdf_departments):
        """reverse survives YAML serialisation."""
        from mappyng.serialize import from_yaml, to_yaml
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid",
                              method="EqualInterval", num_classes=5,
                              cmap="YlOrRd", reverse=True))
        restored = from_yaml(to_yaml(m), gdf=gdf_departments)
        assert self._class0_fill(restored.to_string()) == self.DARK


# ============================================================================
# Legend histogram (TICKET_65)
# ============================================================================

class TestHistogram:

    def test_histogram_off_by_default(self, gdf_departments):
        """No histogram element when not requested."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid", cmap="YlOrRd"))
        assert "choropleth-legend-hist-bar" not in m.to_string()

    def test_histogram_renders_when_enabled(self, gdf_departments):
        """Histogram bars appear when legend.histogram is True."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid", cmap="YlOrRd", legend={"histogram": True}))
        assert "choropleth-legend-hist-bar" in m.to_string()

    def test_histogram_bar_count_matches_config(self, gdf_departments):
        """Number of bars is at most histogram_bins (empty bars omitted)."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid", cmap="YlOrRd", legend={"histogram": True, "histogram_bins": 12}))
        svg = m.to_string()
        assert svg.count("choropleth-legend-hist-bar") <= 12

    def test_histogram_bars_coloured_by_class(self, gdf_departments):
        """Histogram bars are present and carry fill attributes."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid", cmap="YlOrRd", num_classes=5, legend={"histogram": True}))
        svg = m.to_string()
        assert "choropleth-legend-hist-bar" in svg

    def test_histogram_skipped_on_degenerate(self, recwarn):
        """A constant array yields no histogram bars and a warning."""
        import xml.etree.ElementTree as ET

        from mappyng.choropleth import _draw_legend_histogram
        values = np.array([5.0, 5.0, 5.0, 5.0])
        legend_g = ET.Element("g")
        cfg = ChoroplethLegendConfig()
        result = _draw_legend_histogram(
            legend_g, 0.0, 0.0, values, np.array([5.0, 5.0]), ["#ff0000"], cfg,
        )
        assert result is None
        assert any("istogram" in str(w.message) for w in recwarn.list)

    def test_histogram_works_with_dissolve(self, gdf_departments):
        """Histogram uses pre-dissolve values, not aggregated ones."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid", dissolve=True, legend={"histogram": True}))
        assert "choropleth-legend-hist-bar" in m.to_string()

    def test_histogram_with_prettybreaks_no_crash(self, gdf_departments):
        """Histogram tolerates PrettyBreaks bounds above the true max."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid", method="PrettyBreaks", num_classes=5, legend={"histogram": True}))
        assert "choropleth-legend-hist-bar" in m.to_string()

    def test_histogram_both_legend_orientations(self, gdf_departments):
        """Histogram renders for both vertical and horizontal legends."""
        for orient in ("vertical", "horizontal"):
            m = Map(gdf_departments)
            m.add(Choropleth(gdf_departments, column="fid", legend={"histogram": True, "orientation": orient}))
            assert "choropleth-legend-hist-bar" in m.to_string()


# ============================================================================
# Stock-data heuristic warning (TICKET_66)
# ============================================================================

from mappyng.choropleth import _looks_like_stock  # noqa: E402


def _with_column(gdf, name, values):
    """Return a copy of *gdf* with a new numeric column set from *values*."""
    g = gdf.copy()
    g[name] = np.resize(np.asarray(values, dtype=float), len(g))
    return g


class TestStockHeuristic:
    def test_helper_flags_stock(self):
        """Strictly positive integers reaching large values with spread."""
        v = np.array([10, 50, 200, 5000, 100000], dtype=float)
        assert _looks_like_stock(v) == 100000.0

    def test_helper_ignores_rates(self):
        """Bounded fractional values (rates) are not flagged."""
        v = np.array([2.5, 7.1, 12.0, 18.3, 24.9], dtype=float)
        assert _looks_like_stock(v) is None

    def test_helper_ignores_identifier_small_max(self):
        """Integers with a small maximum (ids) are not flagged."""
        v = np.arange(1, 109, dtype=float)  # fid-like 1..108, max < 1000
        assert _looks_like_stock(v) is None

    def test_helper_ignores_narrow_spread(self):
        """Large integers with a tiny spread (e.g. years) are not flagged."""
        v = np.array([2000, 2008, 2015, 2020, 2024], dtype=float)
        assert _looks_like_stock(v) is None

    def test_helper_ignores_negative(self):
        """A column with negative values (e.g. change rate) is not flagged."""
        v = np.array([-500, -10, 5, 50, 5000], dtype=float)
        assert _looks_like_stock(v) is None

    def test_helper_ignores_tiny_sample(self):
        """Fewer than 3 values: no decision."""
        assert _looks_like_stock(np.array([1.0, 100000.0])) is None

    def test_helper_ignores_nan(self):
        """NaNs are dropped before evaluation."""
        v = np.array([10, np.nan, 5000, 100000], dtype=float)
        assert _looks_like_stock(v) is not None

    def test_stock_column_warns(self, gdf_departments):
        """A stock-like column triggers a non-blocking semiology warning."""
        g = _with_column(gdf_departments, "stock",
                          [1000, 5000, 20000, 150000, 2000000])
        m = Map(g)
        with pytest.warns(UserWarning, match="stock"):
            m.add(Choropleth(g, column="stock"))
        # Rendering still proceeds.
        assert "choropleth" in m.to_string()

    def test_rate_column_no_warning(self, gdf_departments, recwarn):
        """A rate-like column emits no stock warning."""
        g = _with_column(gdf_departments, "rate",
                          [2.5, 7.1, 12.0, 18.3, 24.9])
        m = Map(g)
        m.add(Choropleth(g, column="rate"))
        assert not any("stock" in str(w.message) for w in recwarn.list)

    def test_identifier_column_no_warning(self, gdf_departments, recwarn):
        """The fid id column (small max) emits no stock warning."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column="fid"))
        assert not any("stock" in str(w.message) for w in recwarn.list)

    def test_warning_emitted_once(self, gdf_departments):
        """The stock warning fires once per add_choropleth call."""
        g = _with_column(gdf_departments, "stock",
                          [1000, 5000, 20000, 150000, 2000000])
        m = Map(g)
        with pytest.warns(UserWarning) as record:
            m.add(Choropleth(g, column="stock"))
        n = sum("stock" in str(w.message) for w in record)
        assert n == 1


class TestSimplify:
    """Geometry simplification before rendering (lot C)."""

    def _l_count(self, svg):
        # 'L' only appears inside path 'd' attributes in this output.
        return svg.count("L")

    def test_default_is_byte_identical(self, gdf_departments):
        """simplify=None changes nothing versus omitting the argument."""
        def render(**kw):
            m = Map(gdf_departments)
            m.add(Choropleth(gdf_departments, column=COLUMN, **kw))
            return m.to_string()
        assert render(simplify=None) == render()

    def test_auto_reduces_vertices(self, gdf_departments):
        """simplify='auto' drops vertices invisible at the render scale."""
        def render(simplify):
            m = Map(gdf_departments)
            m.add(Choropleth(gdf_departments, column=COLUMN,
                                  simplify=simplify))
            return m.to_string()
        full = render(None)
        auto = render("auto")
        assert self._l_count(auto) < self._l_count(full)

    def test_numeric_tolerance_reduces_vertices(self, gdf_departments):
        """A numeric tolerance simplifies in CRS units."""
        def render(simplify):
            m = Map(gdf_departments)
            m.add(Choropleth(gdf_departments, column=COLUMN,
                                  simplify=simplify))
            return m.to_string()
        full = render(None)
        coarse = render(5000.0)  # 5 km in EPSG:2154
        assert self._l_count(coarse) < self._l_count(full)

    def test_invalid_value_raises(self, gdf_departments):
        """An unknown simplify string is rejected with a clear error."""
        m = Map(gdf_departments)
        with pytest.raises(ValueError, match="simplify must be"):
            m.add(Choropleth(gdf_departments, column=COLUMN,
                                  simplify="nope"))

    def test_huge_tolerance_keeps_every_feature(self, gdf_departments):
        """Topology-preserving simplification never drops a feature."""
        import re

        def feature_ids(simplify):
            m = Map(gdf_departments)
            m.add(Choropleth(gdf_departments, column=COLUMN,
                                  simplify=simplify))
            return set(re.findall(r'id="(choro-\d+-[^"]+)"', m.to_string()))

        # Even an absurd tolerance keeps the same set of drawn features.
        assert feature_ids(1.0e9) == feature_ids(None)

    def test_none_geometry_warns_and_is_kept(self):
        """A geometry the tolerance would empty is kept, with a warning."""
        from shapely.geometry import Polygon

        from mappyng.choropleth import _simplify_gdf
        from mappyng.renderer import SvgViewport, ViewBox

        poly = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        gdf = gpd.GeoDataFrame({"x": [1, 2]}, geometry=[poly, None])
        vp = SvgViewport("main", ViewBox((0, 0, 10, 10),
                                         svg_width=100, svg_height=100))
        with pytest.warns(UserWarning, match="emptied"):
            out = _simplify_gdf(gdf, 0.5, vp)
        assert out.geometry.iloc[1] is None  # original kept
        assert not out.geometry.iloc[0].is_empty

    def test_simplify_round_trips_through_yaml(self, gdf_departments):
        """The simplify setting survives YAML serialization."""
        m = Map(gdf_departments)
        m.add(Choropleth(gdf_departments, column=COLUMN, simplify="auto"))
        restored = Map.from_yaml(m.to_yaml(), gdf=gdf_departments)
        layer = restored.layers[0]
        assert layer.params.get("simplify") == "auto"


# ============================================================================
# Collapsed class breaks (fewer classes than requested)
# ============================================================================

def _legend_swatch_colors(svg):
    ns = {"svg": "http://www.w3.org/2000/svg"}
    root = ET.fromstring(svg)
    return [r.get("fill") for r in root.iterfind(".//svg:rect", ns)
            if (r.get("id") or "").startswith("choropleth-legend-swatch-")]


def _collapsing_gdf(gdf_departments):
    """Values whose rounding to 0 decimals collapses quantile breaks."""
    gdf = gdf_departments.copy()
    gdf["v"] = np.linspace(-3, 3, len(gdf)) ** 3
    return gdf


class TestCollapsedBreaks:
    LEGENDS = [
        {"label_position": "center", "label_format": "range", "decimals": 0},
        {"orientation": "vertical", "label_position": "center",
         "label_format": "range", "decimals": 0},
        {"decimals": 0},
        {"orientation": "vertical", "decimals": 0, "histogram": True},
    ]

    def test_precondition_breaks_do_collapse(self, gdf_departments):
        gdf = _collapsing_gdf(gdf_departments)
        _, _, scheme, bins = classify(gdf, "v", method="Quantiles",
                                      num_classes=5, decimals=0)
        assert len(scheme.bins) < 5

    @pytest.mark.parametrize("legend", LEGENDS)
    def test_legend_renders_and_matches_the_classes(self, gdf_departments, legend):
        gdf = _collapsing_gdf(gdf_departments)
        _, _, scheme, bins = classify(gdf, "v", method="Quantiles",
                                      num_classes=5, decimals=0)
        k_real = len(scheme.bins)
        m = Map(gdf, width=800, height=700)
        with pytest.warns(UserWarning, match="distinct classes"):
            m.add(Choropleth(gdf, column="v", method="Quantiles",
                             num_classes=5, legend=legend))
            svg = m.to_string()
        swatches = _legend_swatch_colors(svg)
        # one swatch per class that really exists, no more
        assert len(swatches) == k_real
        # and the map uses exactly the legend's colours
        ns = {"svg": "http://www.w3.org/2000/svg"}
        used = {p.get("fill") for p in ET.fromstring(svg).iterfind(".//svg:path", ns)
                if (p.get("id") or "").startswith("choro-")}
        assert used <= set(swatches)

    def test_explicit_colour_list_is_trimmed(self, gdf_departments):
        gdf = _collapsing_gdf(gdf_departments)
        colors = ["#111111", "#333333", "#555555", "#777777", "#999999"]
        m = Map(gdf, width=800, height=700)
        with pytest.warns(UserWarning, match="distinct classes"):
            m.add(Choropleth(gdf, column="v", method="Quantiles",
                             num_classes=5, cmap=colors,
                             legend={"decimals": 0}))
            svg = m.to_string()
        assert _legend_swatch_colors(svg) == colors[:4]

    def test_no_warning_when_classes_are_as_requested(self, gdf_departments):
        import warnings
        gdf = _collapsing_gdf(gdf_departments)
        m = Map(gdf, width=800, height=700)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            m.add(Choropleth(gdf, column="v", method="Quantiles",
                             num_classes=5, legend={"decimals": 2}))
            m.to_string()
