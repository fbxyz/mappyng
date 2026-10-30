"""Tests for A7, ConfigManager styles, add_style, get_colormap."""

import pytest

from mappyng import ConfigManager
from mappyng.config import STYLE_CONFIGS, StyleConfig
from mappyng.layers import Basemap

# ============================================================================
# get_style, classic vs modern
# ============================================================================

class TestGetStyle:
    def test_classic_returns_style(self):
        s = ConfigManager.get_style("classic")
        assert s["title_color"] is not None

    def test_modern_returns_style(self):
        s = ConfigManager.get_style("modern")
        assert s["title_color"] is not None

    def test_classic_and_modern_differ(self):
        classic = ConfigManager.get_style("classic")
        modern = ConfigManager.get_style("modern")
        # Colors differ between styles
        assert classic["title_color"] != modern["title_color"]
        assert classic["edge_color"] != modern["edge_color"]

    def test_title_fontweight_accessible(self):
        """style['title_fontweight'] must be a valid key."""
        s = ConfigManager.get_style("classic")
        w = s["title_fontweight"]
        assert isinstance(w, str) and len(w) > 0

    def test_get_style_with_dict_override(self):
        """Dict override should produce a style with the overridden value."""
        s = ConfigManager.get_style({"base": "classic", "title_color": "#ff0000"})
        assert s["title_color"] == "#ff0000"

    def test_unknown_style_raises(self):
        with pytest.raises((KeyError, ValueError)):
            ConfigManager.get_style("nonexistent_style_xyz")


# ============================================================================
# add_style, StyleConfig and dict
# ============================================================================

class TestAddStyle:
    def test_add_style_with_style_config(self):
        cfg = StyleConfig(name="test_cfg")
        ConfigManager.add_style("test_cfg", cfg)
        assert "test_cfg" in STYLE_CONFIGS
        # Cleanup
        del STYLE_CONFIGS["test_cfg"]

    def test_add_style_with_dict(self):
        """add_style should accept a flat dict of overrides (new feature)."""
        ConfigManager.add_style("test_dict", {"title_color": "#123456"})
        assert "test_dict" in STYLE_CONFIGS
        s = ConfigManager.get_style("test_dict")
        assert s["title_color"] == "#123456"
        # Cleanup
        del STYLE_CONFIGS["test_dict"]

    def test_add_style_dict_merges_with_classic(self):
        """Dict style inherits unspecified fields from 'classic'."""
        ConfigManager.add_style("test_merge", {"title_color": "#abcdef"})
        s = ConfigManager.get_style("test_merge")
        classic = ConfigManager.get_style("classic")
        # Unspecified fields should match classic
        assert s["legend_fontsize"] == classic["legend_fontsize"]
        del STYLE_CONFIGS["test_merge"]

    def test_add_style_invalid_raises(self):
        with pytest.raises(TypeError):
            ConfigManager.add_style("bad", 42)

    def test_custom_style_usable_in_map(self, gdf_departments):
        """A registered custom style can be passed to Map."""
        ConfigManager.add_style("test_map_style", {"title_color": "#ff6600"})
        from mappyng import Map
        with Map(gdf_departments, width=400, height=300,
                 style="test_map_style") as m:
            m.add(Basemap())
            m.title(text="Test")
        svg = m.to_string()
        assert "#ff6600" in svg
        del STYLE_CONFIGS["test_map_style"]


# ============================================================================
# get_colormap
# ============================================================================

class TestGetColormap:
    def test_ylorrd_5_classes(self):
        colors = ConfigManager.get_colormap("YlOrRd", 5)
        assert len(colors) == 5
        assert all(c.startswith("#") for c in colors)

    def test_blues_4_classes(self):
        colors = ConfigManager.get_colormap("Blues", 4)
        assert len(colors) == 4

    def test_unknown_colormap_raises(self):
        with pytest.raises(ValueError):
            ConfigManager.get_colormap("NotAColormap", 5)

    def test_invalid_num_classes_raises(self):
        with pytest.raises(ValueError):
            ConfigManager.get_colormap("YlOrRd", 99)
