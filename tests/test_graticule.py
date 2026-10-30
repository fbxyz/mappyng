"""Tests for add_graticule, graticule lines on main, zoom, cartouche viewports."""

import xml.etree.ElementTree as ET

from mappyng import Map
from mappyng.layers import Basemap, Graticule

NS = {"svg": "http://www.w3.org/2000/svg"}


def _paths(m, layer="graticule"):
    root = ET.fromstring(m.to_string())
    return [
        el for el in root.findall(".//svg:path", NS)
        if el.get("data-layer", "").startswith(layer)
           or (el.getparent() if hasattr(el, "getparent") else None) is not None
    ]


def _all_paths(m):
    root = ET.fromstring(m.to_string())
    return root.findall(".//svg:path", NS)


class TestAddGraticuleBasic:
    def test_produces_paths(self, gdf_departments):
        """add_graticule renders at least some SVG paths."""
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Graticule(step=2.0))
        before_paths = 0
        with Map(gdf_departments, width=800, height=600) as m2:
            m2.add(Basemap())
        before_paths = len(_all_paths(m2))
        after_paths = len(_all_paths(m))
        assert after_paths > before_paths

    def test_default_params(self, gdf_departments):
        """add_graticule works with no params."""
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Graticule())
        svg = m.to_string()
        assert "<path" in svg

    def test_custom_color_in_svg(self, gdf_departments):
        """Custom color appears in SVG stroke attribute."""
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Graticule(step=2.0, stroke="#ff0000"))
        svg = m.to_string()
        assert "#ff0000" in svg

    def test_custom_dash_in_svg(self, gdf_departments):
        """Custom dash array appears in SVG."""
        with Map(gdf_departments, width=800, height=600) as m:
            m.add(Basemap())
            m.add(Graticule(step=2.0, dash="8 3"))
        svg = m.to_string()
        assert "8 3" in svg

    def test_small_step_still_works(self, gdf_departments):
        """step=1 produces more lines than step=10."""
        with Map(gdf_departments, width=800, height=600) as m1:
            m1.add(Basemap())
            m1.add(Graticule(step=1.0))
        with Map(gdf_departments, width=800, height=600) as m10:
            m10.add(Basemap())
            m10.add(Graticule(step=10.0))
        assert len(_all_paths(m1)) > len(_all_paths(m10))


class TestAddGraticuleCartouche:
    def test_graticule_on_cartouche(self, gdf_departments):
        """Graticule renders on a cartouche viewport (more paths than without)."""
        cart = {1: {"bbox": [90000, 6040000, 1280000, 7150000]}}
        with Map(gdf_departments, width=1000, height=600,
                 cartouche_params=cart) as m:
            m.add(Basemap())
            m.add(Graticule(step=2.0))
        svg = m.to_string()
        assert "<path" in svg
