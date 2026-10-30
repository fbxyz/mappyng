"""
Example GeoJSON datasets for mappyng.

This module provides easy access to regional and European GeoJSON data
that can be used as examples and for testing.

Available datasets:
- French regions (abm_region_gen3.geojson)
- French departments (abm_pays_departement_gen3.geojson)
- European countries with ISO codes (abm_pays_europe_gen3.geojson)
- European countries cartographic simplified (abm_pays_europe_carto_gen3.geojson)
- EFS regions (efs_regionefs_gen3.geojson)

Example usage:
    >>> from mappyng.data import load_france_regions, load_europe
    >>> regions = load_france_regions()
    >>> europe = load_europe()
"""

from pathlib import Path

import geopandas as gpd

# Get the path to the data directory
_DATA_DIR = Path(__file__).parent


def get_data_path(filename: str) -> Path:
    """
    Get the absolute path to a data file.

    Parameters
    ----------
    filename : str
        Name of the data file

    Returns
    -------
    Path
        Absolute path to the data file
    """
    return _DATA_DIR / filename


def load_france_regions() -> gpd.GeoDataFrame:
    """
    Load French regions GeoDataFrame.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame containing French regions

    Examples
    --------
    >>> from mappyng.data import load_france_regions
    >>> regions = load_france_regions()
    >>> print(regions.head())
    """
    return gpd.read_file(get_data_path("abm_region_gen3.geojson"))


def load_france_departments() -> gpd.GeoDataFrame:
    """
    Load French departments GeoDataFrame.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame containing French departments

    Examples
    --------
    >>> from mappyng.data import load_france_departments
    >>> departments = load_france_departments()
    >>> print(departments.head())
    """
    return gpd.read_file(get_data_path("abm_pays_departement_gen3.geojson"))


def load_europe() -> gpd.GeoDataFrame:
    """
    Load European countries GeoDataFrame with ISO codes.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame containing European countries with ISO codes

    Examples
    --------
    >>> from mappyng.data import load_europe
    >>> europe = load_europe()
    >>> print(europe.head())
    """
    return gpd.read_file(get_data_path("abm_pays_europe_gen3.geojson"))


def load_europe_simplified() -> gpd.GeoDataFrame:
    """
    Load simplified European countries GeoDataFrame (cartographic version).

    This is a simplified version optimized for cartographic display.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame containing simplified European countries

    Examples
    --------
    >>> from mappyng.data import load_europe_simplified
    >>> europe_simple = load_europe_simplified()
    >>> print(europe_simple.head())
    """
    return gpd.read_file(get_data_path("abm_pays_europe_carto_gen3.geojson"))


def load_efs_regions() -> gpd.GeoDataFrame:
    """
    Load EFS (European Forest Sectors) regions GeoDataFrame.

    Returns
    -------
    geopandas.GeoDataFrame
        GeoDataFrame containing EFS regions

    Examples
    --------
    >>> from mappyng.data import load_efs_regions
    >>> efs = load_efs_regions()
    >>> print(efs.head())
    """
    return gpd.read_file(get_data_path("efs_regionefs_gen3.geojson"))


# List of all available datasets
AVAILABLE_DATASETS: dict[str, str] = {
    "france_regions": "abm_region_gen3.geojson",
    "france_departments": "abm_pays_departement_gen3.geojson",
    "europe": "abm_pays_europe_gen3.geojson",
    "europe_simplified": "abm_pays_europe_carto_gen3.geojson",
    "efs_regions": "efs_regionefs_gen3.geojson",
}


def list_datasets() -> dict[str, str]:
    """
    List all available datasets.

    Returns
    -------
    dict
        Dictionary mapping dataset names to filenames
    """
    return AVAILABLE_DATASETS.copy()


__all__ = [
    "get_data_path",
    "load_france_regions",
    "load_france_departments",
    "load_europe",
    "load_europe_simplified",
    "load_efs_regions",
    "list_datasets",
    "AVAILABLE_DATASETS",
]
