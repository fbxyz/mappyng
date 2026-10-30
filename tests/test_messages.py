"""Enriched, self-contained error/warning messages (TICKET_79).

These lock the user-facing wording: messages name the public API
(``Layer`` subclasses, current method names), explain the cause, and
point to a way out, without referencing removed or renamed internals.
"""

import pytest

from mappyng import Map
from mappyng.layers import Basemap, Label


def test_empty_gdf_message_is_actionable(gdf_departments):
    with pytest.raises(ValueError, match="non-empty GeoDataFrame"):
        Map(gdf_departments.iloc[0:0])
    with pytest.raises(ValueError, match="non-empty GeoDataFrame"):
        Map(None)


def test_label_unknown_target_names_public_options(gdf_departments):
    """The label target error names Label and the valid targets,
    not the removed add_labels method."""
    m = Map(gdf_departments)
    m.add(Label(gdf_departments, column="LIB_GEO", target="bogus"))
    with pytest.raises(ValueError) as exc:
        m.to_string()
    msg = str(exc.value)
    assert "Label" in msg
    assert "add_labels:" not in msg
    assert "'main'" in msg


def test_label_zoom_without_viewport_points_to_add_zoom(gdf_departments):
    m = Map(gdf_departments)
    m.add(Label(gdf_departments, column="LIB_GEO", target="zoom"))
    with pytest.raises(ValueError, match="add_zoom"):
        m.to_string()


def test_add_after_build_message_uses_current_methods(gdf_departments):
    m = Map(gdf_departments)
    m.add(Basemap())
    m.to_string()
    with pytest.raises(RuntimeError) as exc:
        m.add(Basemap())
    msg = str(exc.value)
    assert "m.render(" in msg
    # the deprecated save() is no longer advertised as the canonical path
    assert "render/save/to_string" not in msg
