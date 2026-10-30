"""Shared fixtures for mappyng tests."""

import pytest

from mappyng.data import load_europe, load_france_departments


@pytest.fixture
def gdf_europe():
    """European countries GeoDataFrame in EPSG:2154."""
    return load_europe().to_crs(2154)


@pytest.fixture
def gdf_departments():
    """French departments GeoDataFrame in EPSG:2154."""
    return load_france_departments().to_crs(2154)


@pytest.fixture
def bbox_metro():
    """Metropolitan France bounding box in EPSG:2154."""
    return [90000, 6040000, 1280000, 7150000]
