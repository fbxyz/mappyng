"""Command-line entry point: render a YAML map description to a file.

A YAML document that carries its own data sources (see
:meth:`mappyng.Map.from_yaml`) can be turned into a map with no Python::

    python -m mappyng map.yaml -o map.svg
    python -m mappyng map.yaml -o map.png --dpi 200
    python -m mappyng map.yaml -o map.html      # interactive

For an interactive HTML export, tooltip settings are read from an optional
top-level ``interactive:`` block in the document::

    interactive:
      columns: [LIB_GEO, taux_mortalite]
      aliases: {LIB_GEO: Department, taux_mortalite: Rate}
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m mappyng",
        description="Render a YAML map description to SVG, PNG, PDF or "
                    "interactive HTML.",
    )
    parser.add_argument("yaml", help="Path to the YAML map description.")
    parser.add_argument(
        "-o", "--output",
        help="Output file. Format is inferred from the extension "
             "(.svg, .png, .pdf, .html). Defaults to the input name with "
             "a .svg extension.",
    )
    parser.add_argument(
        "--dpi", type=int, default=None,
        help="Resolution for PNG export (ignored for other formats).",
    )
    parser.add_argument(
        "--gdf",
        help="Optional vector file to use as the geometry instead of the "
             "sources declared in the YAML.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    if not os.path.exists(args.yaml):
        print(f"error: YAML file not found: {args.yaml}", file=sys.stderr)
        return 2

    output = args.output or (os.path.splitext(args.yaml)[0] + ".svg")

    from .map import Map

    gdf = None
    if args.gdf:
        import geopandas as gpd
        gdf = gpd.read_file(args.gdf)

    try:
        m = Map.from_yaml(args.yaml, gdf=gdf)
    except Exception as e:  # noqa: BLE001 - report cleanly to the user
        print(f"error: could not build the map: {e}", file=sys.stderr)
        return 1

    try:
        if args.dpi is not None:
            m.render(output, dpi=args.dpi)
        else:
            m.render(output)
    except Exception as e:  # noqa: BLE001 - report cleanly to the user
        print(f"error: could not render to {output}: {e}", file=sys.stderr)
        return 1

    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
