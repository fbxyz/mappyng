"""Interactive SVG export with tooltip support.

Post-processes the SVG produced by :class:`~mappyng.map.Map` to inject
hover tooltips via embedded JavaScript.  No external dependency,
the result is a self-contained SVG (Jupyter-friendly) or HTML file.

Example
-------
>>> m = Map(gdf, bbox=bbox, facecolor="#B9D9EB")
>>> m.add(Basemap())
>>> m.add(Choropleth(gdf_dep, column="population"))
>>> interactive = m.to_interactive()
>>> interactive.save("carte.html")
>>>
>>> # Customize tooltips
>>> m.to_interactive(
...     columns=["NOM", "POP"],
...     aliases={"NOM": "Nom", "POP": "Population"},
...     tooltip={"background": "#1a1a2e", "font_size": 13},
... )
"""

import json
from dataclasses import dataclass, field
from typing import Any
from xml.etree import ElementTree as ET

import numpy as np

# SVG element tags that can carry tooltips
_VISUAL_TAGS = frozenset({"path", "circle", "rect", "ellipse", "polygon",
                          "polyline", "line", "use"})

# Columns to exclude from auto-detected tooltips
_INTERNAL_COLUMNS = frozenset({
    "geometry", "_class", "_color", "_sort_size",
})


# ============================================================================
# Tooltip style
# ============================================================================

@dataclass
class HoverEffect:
    """Hover visual effect configuration for interactive SVG elements.

    Effects are implemented via CSS transitions + SVG filters so they
    animate smoothly.  Set ``enabled=False`` to disable all hover
    visuals (tooltip still works).

    Parameters
    ----------
    enabled : bool
        Master switch for hover effects.
    transition : str
        CSS transition timing (applies to all animated properties).
    opacity : float
        Opacity on hover (< 1 = dim, > 1 ignored).
    scale : float
        Scale factor on hover (1.0 = no change).
    shadow : bool
        Show a drop-shadow on hover.
    shadow_color : str
        Shadow color.
    shadow_dx : float
        Shadow horizontal offset (SVG px).
    shadow_dy : float
        Shadow vertical offset (SVG px).
    shadow_blur : float
        Shadow blur radius (SVG px).
    stroke_width_boost : float
        Extra stroke-width on hover (added to existing, 0 = no change).
    stroke_color : str or None
        Override stroke color on hover (None = keep original).
    """

    enabled: bool = True
    transition: str = "all 0.25s cubic-bezier(0.25, 0.46, 0.45, 0.94)"
    opacity: float = 1.0
    scale: float = 1.0
    shadow: bool = False
    shadow_color: str = "rgba(0,0,0,0.35)"
    shadow_dx: float = 0.0
    shadow_dy: float = 4.0
    shadow_blur: float = 8.0
    stroke_width_boost: float = 1.0
    stroke_color: str | None = "#333333"


@dataclass
class TooltipStyle:
    """Tooltip appearance configuration.

    All fields map directly to CSS/SVG style properties injected
    into the tooltip ``<script>`` block.
    """

    background: str = "rgba(30,30,30,0.92)"
    text_color: str = "#fff"
    font_size: int = 11
    font_family: str = "-apple-system,BlinkMacSystemFont,sans-serif"
    border_radius: int = 4
    border_color: str = "rgba(255,255,255,0.15)"
    key_weight: str = "600"
    hover: Any = field(default_factory=HoverEffect)
    """Hover effect config: True (defaults), False (disabled), or dict."""


def _ensure_hover_effect(hover: Any) -> HoverEffect:
    """Normalize a hover input to :class:`HoverEffect`."""
    if hover is None or hover is True:
        return HoverEffect()
    if hover is False:
        return HoverEffect(enabled=False)
    if isinstance(hover, dict):
        return HoverEffect(**hover)
    if isinstance(hover, HoverEffect):
        return hover
    return HoverEffect()


def _ensure_tooltip_style(
    style: Any = None,
    aliases: dict[str, str] | None = None,
) -> "TooltipStyle":
    """Normalize *style* to a :class:`TooltipStyle`."""
    if style is None:
        style = TooltipStyle()
    elif isinstance(style, dict):
        hover_raw = style.pop("hover", None)
        style = TooltipStyle(**style)
        if hover_raw is not None:
            style.hover = hover_raw
    # Normalize hover sub-config
    style.hover = _ensure_hover_effect(style.hover)
    return style


# ============================================================================
# Value formatting
# ============================================================================

def _format_value(val: Any) -> str:
    """Format a single value for tooltip display."""
    if val is None:
        return ""
    if isinstance(val, float):
        if val != val:  # NaN
            return ""
        if val == int(val) and abs(val) < 1e15:
            return f"{int(val):,}".replace(",", "\u202f")
        return f"{val:g}"
    if isinstance(val, (int, np.integer)):
        return f"{int(val):,}".replace(",", "\u202f")
    return str(val)


# ============================================================================
# Tooltip data builders
# ============================================================================

def auto_detect_columns(gdf: Any) -> list[str]:
    """Select displayable columns from a GeoDataFrame."""
    return [
        c for c in gdf.columns
        if c not in _INTERNAL_COLUMNS and not c.startswith("_")
    ]


def _build_tooltip_map(
    gdf: Any,
    columns: list[str],
    aliases: dict[str, str] | None = None,
    id_prefix: str = "",
) -> dict[str, str]:
    """Build a mapping ``{svg_element_id: json_tooltip_data}``.

    Parameters
    ----------
    gdf : GeoDataFrame
        Source data (same GDF that was passed to ``Choropleth`` /
        ``Proportional``).
    columns : list of str
        Column names to include in each tooltip.
    aliases : dict, optional
        Column name to display label mapping.
    id_prefix : str
        SVG id prefix (e.g. ``"choro-1-"`` or ``"prop-2-"``).

    Returns
    -------
    dict
        ``{element_id: json_string}`` ready for ``data-tooltip``
        attribute injection.
    """
    aliases = aliases or {}
    result: dict[str, str] = {}

    for idx, row in gdf.iterrows():
        data = {}
        for col in columns:
            if col in row.index and col != "geometry":
                label = aliases.get(col, col)
                data[label] = _format_value(row[col])
        if not data:
            continue
        json_str = json.dumps(data, ensure_ascii=False)

        eid = f"{id_prefix}{idx}"
        result[eid] = json_str

    return result


# ============================================================================
# JavaScript template
# ============================================================================

def _build_hover_css(hover: HoverEffect) -> str:
    """Build ``<style>`` block for hover CSS transitions."""
    if not hover.enabled:
        return ""

    # Build the list of properties that actually change on hover,
    # so we only transition those, NOT "all" which can cause
    # fill/color artefacts when the DOM is reordered for z-order.
    transition_props = []
    hover_rules = []

    if hover.opacity < 1.0:
        transition_props.append("opacity")
        hover_rules.append(f"  opacity: {hover.opacity};")
    if hover.scale != 1.0:
        transition_props.append("transform")
        hover_rules.append(f"  transform: scale({hover.scale});")
        hover_rules.append("  transform-origin: center;")
        hover_rules.append("  transform-box: fill-box;")
    if hover.shadow:
        transition_props.append("filter")
        hover_rules.append(
            f"  filter: drop-shadow({hover.shadow_dx}px {hover.shadow_dy}px "
            f"{hover.shadow_blur}px {hover.shadow_color});"
        )
    if hover.stroke_width_boost > 0:
        transition_props.append("stroke-width")
        hover_rules.append(
            f"  stroke-width: calc(var(--orig-sw, 0.5) + {hover.stroke_width_boost});"
        )
    if hover.stroke_color:
        transition_props.append("stroke")
        hover_rules.append(f"  stroke: {hover.stroke_color};")

    if not hover_rules:
        return ""

    # Extract timing function from the user-provided transition string
    # (strip leading "all " if present)
    timing = hover.transition
    if timing.startswith("all "):
        timing = timing[4:]

    transition_value = ", ".join(f"{p} {timing}" for p in transition_props)

    css = f"""<style>
[data-tooltip] {{
  cursor: pointer;
  transition: {transition_value};
}}
[data-tooltip]:hover {{
{chr(10).join(hover_rules)}
}}
</style>"""
    return css


def _build_tooltip_script(style: TooltipStyle) -> str:
    """Build the embedded ``<script>`` and ``<style>`` blocks."""
    hover = style.hover
    hover_css = _build_hover_css(hover)

    # stroke-width-boost needs JS to read original stroke-width
    sw_init_js = ""
    if hover.enabled and hover.stroke_width_boost > 0:
        sw_init_js = """
    var sw=el.getAttribute('stroke-width')||'0.5';
    el.style.setProperty('--orig-sw',sw);"""

    return hover_css + f'''
<script type="text/ecmascript"><![CDATA[
(function(){{
var svg=document.currentScript.closest('svg')||document.querySelector('svg');
if(!svg)return;
var ns='http://www.w3.org/2000/svg';

// Tooltip group
var tt=document.createElementNS(ns,'g');
tt.setAttribute('visibility','hidden');
tt.setAttribute('pointer-events','none');

var bg=document.createElementNS(ns,'rect');
bg.setAttribute('fill','{style.background}');
bg.setAttribute('rx','{style.border_radius}');
bg.setAttribute('ry','{style.border_radius}');
bg.setAttribute('stroke','{style.border_color}');
bg.setAttribute('stroke-width','0.5');
tt.appendChild(bg);

var txt=document.createElementNS(ns,'text');
txt.setAttribute('fill','{style.text_color}');
txt.setAttribute('font-size','{style.font_size}');
txt.setAttribute('font-family','{style.font_family}');
tt.appendChild(txt);
svg.appendChild(tt);

// Position the tooltip under the cursor. Map client coords to SVG user
// (viewBox) coords via the bounding rect rather than getScreenCTM: the SVG
// scales uniformly (width/height match the viewBox aspect ratio) so the linear
// map is exact and behaves the same in Firefox and Chromium/Edge.
function place(e){{
  var rect=svg.getBoundingClientRect();
  if(!rect.width||!rect.height)return;
  var vb=svg.viewBox.baseVal;
  var vbW=(vb&&vb.width)?vb.width:rect.width;
  var vbH=(vb&&vb.height)?vb.height:rect.height;
  var vbX=(vb&&vb.width)?vb.x:0;
  var vbY=(vb&&vb.height)?vb.y:0;
  var spx=vbX+(e.clientX-rect.left)/rect.width*vbW;
  var spy=vbY+(e.clientY-rect.top)/rect.height*vbH;
  var offX=(spx>vbX+vbW*0.7)?-parseFloat(bg.getAttribute('width')||0)-15:15;
  tt.setAttribute('transform','translate('+(spx+offX)+','+(spy-25)+')');
}}

// Track the element currently raised to front so its z-order can be restored.
var raised=null;
function restoreZ(){{
  var r=raised;raised=null;
  if(r&&r.parent){{
    if(r.next)r.parent.insertBefore(r.el,r.next);
    else r.parent.appendChild(r.el);
  }}
}}
function hideTip(){{
  tt.setAttribute('visibility','hidden');
  restoreZ();
}}
// Container-level guards: hide when the pointer leaves the map entirely, or
// moves over any element that has no tooltip (e.g. sea/background). Per-element
// mouseleave alone is unreliable in Edge once a node is re-parented to front.
svg.addEventListener('mouseleave',hideTip);
svg.addEventListener('mouseover',function(e){{
  var t=e.target;
  if(!(t&&t.closest&&t.closest('[data-tooltip]')))hideTip();
}});

svg.querySelectorAll('[data-tooltip]').forEach(function(el){{
{sw_init_js}
  // Proportional symbols (circles/ellipses) are intentionally stacked
  // largest-first so smaller ones sit on top; bringing the hovered element to
  // front would hide the smaller circles behind the biggest. Only reorder
  // polygon-type shapes, where it keeps the highlighted border unclipped.
  var tag=(el.tagName||'').toLowerCase();
  var bringToFront=(tag!=='circle'&&tag!=='ellipse');

  el.addEventListener('mouseenter',function(e){{
    // Restore any previously raised element, then bring this one to front.
    restoreZ();
    if(bringToFront&&el.parentNode){{
      raised={{el:el,parent:el.parentNode,next:el.nextElementSibling}};
      el.parentNode.appendChild(el);
    }}

    var d;
    try{{d=JSON.parse(el.getAttribute('data-tooltip'));}}catch(e){{return;}}
    while(txt.firstChild)txt.removeChild(txt.firstChild);
    var keys=Object.keys(d);
    keys.forEach(function(k,i){{
      var tsK=document.createElementNS(ns,'tspan');
      tsK.setAttribute('font-weight','{style.key_weight}');
      tsK.textContent=k+' : ';
      if(i===0){{tsK.setAttribute('x','8');tsK.setAttribute('dy','15');}}
      else{{tsK.setAttribute('x','8');tsK.setAttribute('dy','17');}}
      txt.appendChild(tsK);
      var tsV=document.createElementNS(ns,'tspan');
      tsV.setAttribute('font-weight','400');
      tsV.textContent=d[k];
      txt.appendChild(tsV);
    }});
    var bb=txt.getBBox();
    bg.setAttribute('x',String(bb.x-8));
    bg.setAttribute('y',String(bb.y-6));
    bg.setAttribute('width',String(bb.width+16));
    bg.setAttribute('height',String(bb.height+12));
    // Position immediately so the tooltip never flashes at the map's top-left
    // corner: Chromium/Edge may not deliver a mousemove right after mouseenter
    // (the element is re-parented to front above), leaving it stuck at (0,0).
    place(e);
    tt.setAttribute('visibility','visible');
  }});

  el.addEventListener('mousemove',place);

  el.addEventListener('mouseleave',hideTip);
}});
}})();
]]></script>'''


# ============================================================================
# SVG post-processing
# ============================================================================

def inject_tooltips(
    svg_str: str,
    tooltip_maps: list[dict[str, str]],
    style: TooltipStyle | None = None,
) -> str:
    """Inject ``data-tooltip`` attributes and script into SVG markup.

    Parameters
    ----------
    svg_str : str
        Raw SVG string from ``Map.to_string()``.
    tooltip_maps : list of dict
        Each dict maps ``{element_id: json_tooltip_string}``.
    style : TooltipStyle, optional
        Tooltip appearance.

    Returns
    -------
    str
        Modified SVG with interactive tooltips.
    """
    style = style or TooltipStyle()

    # Merge all tooltip maps into one
    merged: dict[str, str] = {}
    for tm in tooltip_maps:
        merged.update(tm)

    if not merged:
        return svg_str

    # Register SVG namespace to avoid ns0: prefix in output
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")

    root = ET.fromstring(svg_str)

    # Walk all elements and attach data-tooltip where id matches
    _walk_and_attach(root, merged)

    # Serialize back
    svg_out = ET.tostring(root, encoding="unicode", xml_declaration=True)

    # Inject script before closing </svg> (handle namespace prefix)
    script = _build_tooltip_script(style)
    # ET may output </svg> or </ns0:svg> depending on namespace registration
    import re
    svg_out = re.sub(r'</(?:\w+:)?svg\s*>', script + "\n</svg>", svg_out)

    return svg_out


def _walk_and_attach(elem: ET.Element, tooltip_map: dict[str, str]) -> None:
    """Recursively walk the SVG tree and attach data-tooltip attributes."""
    eid = elem.get("id", "")
    if eid and eid in tooltip_map:
        elem.set("data-tooltip", tooltip_map[eid])
    for child in elem:
        _walk_and_attach(child, tooltip_map)


# ============================================================================
# InteractiveMap result
# ============================================================================

class InteractiveMap:
    """Interactive SVG map with hover tooltips.

    Auto-renders in Jupyter via ``_repr_html_()`` and can be
    saved as a standalone HTML file.
    """

    def __init__(self, svg_content: str):
        self._svg = svg_content

    def _repr_html_(self) -> str:
        """Jupyter notebook HTML display."""
        return (
            '<div style="display:inline-block;position:relative;">'
            f'{self._svg}</div>'
        )

    def save(self, path: str, title: str = "Interactive Map") -> None:
        """Save as standalone HTML file.

        Parameters
        ----------
        path : str
            Output file path.
        title : str
            HTML page title.
        """
        import html as html_module

        html_content = (
            "<!DOCTYPE html>\n<html>\n<head><meta charset='utf-8'>"
            f"<title>{html_module.escape(title)}</title>\n"
            "<style>"
            "body{margin:0;display:flex;justify-content:center;"
            "align-items:center;min-height:100vh;background:#f5f5f5}"
            "svg{max-width:95vw;height:auto}"
            "</style>\n</head>\n<body>\n"
            f"{self._svg}\n</body>\n</html>"
        )
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)

    @property
    def svg(self) -> str:
        """Raw SVG markup with embedded JavaScript."""
        return self._svg
