import os
import sys

sys.path.insert(0, os.path.abspath("../src"))
sys.path.insert(0, os.path.abspath("_ext"))

from mappyng import __version__ as _mappyng_version

project = "mappyng"
author = "fbxyz"
release = _mappyng_version
version = ".".join(_mappyng_version.split(".")[:2])
copyright = "2026, fbxyz"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx_autodoc_typehints",
    "sphinx_copybutton",
    "sphinx_gallery.gen_gallery",
    "mappyng_example",
]


def _mappyng_scraper(block, block_vars, gallery_conf):
    """Capture every Map built in a code block.

    Each :class:`~mappyng.Map` left in the example namespace is embedded
    on the page as an *interactive* inline SVG, so native SVG features
    (drop shadows, glows) render and hover tooltips work in the browser.
    A PNG is also rendered for the gallery thumbnail, since raster export
    cannot reproduce SVG filters.

    The tooltips come from the :class:`~mappyng.Tooltip` added to the map.
    """
    from mappyng import Map

    image_path_iterator = block_vars["image_path_iterator"]
    seen = block_vars.setdefault("_mappyng_seen_ids", set())
    globals_ = block_vars["example_globals"]
    rst_parts = []
    for obj in globals_.values():
        if isinstance(obj, Map) and id(obj) not in seen:
            seen.add(id(obj))
            png_path = next(image_path_iterator)
            obj.render(png_path, dpi=150)   # raster, for the thumbnail
            try:
                svg = obj.to_interactive().svg
            except Exception:               # noqa: BLE001 - fall back to static
                svg = obj.to_string()
            svg = svg.replace(
                "<svg ", '<svg style="max-width:100%;height:auto" ', 1)
            block_html = "\n".join("   " + line for line in svg.splitlines())
            rst_parts.append(".. raw:: html\n\n" + block_html + "\n")
    return "\n".join(rst_parts)


sphinx_gallery_conf = {
    "examples_dirs": "examples",
    "gallery_dirs": "gallery",
    "filename_pattern": r"plot_",
    "image_scrapers": (_mappyng_scraper,),
    "image_srcset": [],
    "remove_config_comments": True,
    "download_all_examples": False,
    "within_subsection_order": "FileNameSortKey",
    "default_thumb_file": None,
    "matplotlib_animations": False,
    # Les exemples rendent du SVG natif, pas de matplotlib : on desactive
    # le reset par defaut qui tenterait de l'importer (absent des deps).
    "reset_modules": (),
}

autodoc_mock_imports = ["rasterio"]

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "special-members": "__init__",
}

napoleon_numpy_docstring = True
napoleon_google_docstring = False
napoleon_use_param = False
napoleon_use_rtype = False

# The gallery scraper is a function, so the gallery config cannot be
# pickled for the build cache. The warning is harmless.
suppress_warnings = ["config.cache"]

html_theme = "furo"

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
