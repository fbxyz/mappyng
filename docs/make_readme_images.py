"""Regenerate the README illustrations from the gallery examples.

Run from the repository root: ``python docs/make_readme_images.py``.
Each example is executed in ``docs/examples`` (so its relative data paths
resolve) and its ``m`` map is written to ``docs/_static/readme/<name>.svg``.
The README embeds the SVG itself, the library's native output.
"""

import os
import runpy
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "_static" / "readme"
SOURCES = {
    "choropleth": "plot_02_choropleth.py",
    "proportional": "plot_03_proportional.py",
    "cartouches": "plot_08_layout.py",
    "globe": "plot_13_globe.py",
}

OUT.mkdir(parents=True, exist_ok=True)
os.chdir(ROOT / "examples")
for name, script in SOURCES.items():
    ns = runpy.run_path(script)
    ns["m"].render(str(OUT / f"{name}.svg"))
    print("wrote", OUT / f"{name}.svg")
