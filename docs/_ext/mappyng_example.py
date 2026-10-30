"""``mappyng-example`` directive: show a code block and the map it builds.

The content is Python code executed with a shared preamble (``mp``, ``pd``,
``gpd``, ``europe``, ``regions``, ``deps``, ``BBOX``, ``DATA``). The ``Map``
bound to ``m`` is rendered as an inline SVG under the highlighted code.
"""

from __future__ import annotations

from pathlib import Path

from docutils import nodes
from docutils.parsers.rst import Directive

_PREAMBLE = """
from pathlib import Path
import geopandas as gpd
import pandas as pd
import mappyng as mp
from mappyng.data import load_europe, load_france_departments, load_france_regions

europe = load_europe().to_crs(2154)
regions = load_france_regions().to_crs(2154)
deps = load_france_departments().to_crs(2154)
BBOX = [90000, 6040000, 1280000, 7150000]   # mainland France, Lambert-93
"""

_base: dict | None = None


def _namespace(data_dir: Path) -> dict:
    global _base
    if _base is None:
        _base = {"DATA": data_dir}
        exec(compile(_PREAMBLE, "<mappyng-example preamble>", "exec"), _base)
    return dict(_base)


class MappyngExample(Directive):
    has_content = True
    option_spec = {"width": str}

    def run(self):
        env = self.state.document.settings.env
        code = "\n".join(self.content)
        data_dir = Path(env.srcdir) / "examples" / "data"
        ns = _namespace(data_dir)
        exec(compile(code, "<mappyng-example>", "exec"), ns)
        m = ns["m"]
        try:
            svg = m.to_interactive().svg
        except Exception:                       # noqa: BLE001
            svg = m.to_string()
        svg = svg.replace("<svg ", '<svg style="max-width:100%;height:auto" ', 1)
        literal = nodes.literal_block(code, code)
        literal["language"] = "python"
        raw = nodes.raw("", svg, format="html")
        return [literal, raw]


def setup(app):
    app.add_directive("mappyng-example", MappyngExample)
    return {"parallel_read_safe": False, "version": "1"}
