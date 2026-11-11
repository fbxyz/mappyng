# Changelog

## 1.0.1 (2026-11-11)

### Fixed

- `autosize()` no longer drops the zoom window or the radial gradients added before it.
- `render("map.png", dpi=...)`: the resolution now scales the image (it had no effect).
- A layer added to a second map is copied instead of being silently skipped.
- Layers in another CRS than the map are reprojected instead of drawing nothing.
- `stroke_width=0` is honoured by `Choropleth`, `Category`, `Basemap` and `Vector`.
- Missing values: no more `nan` labels nor `fill-opacity="nan"`; a column without any value raises a plain error.
- Tooltips of a dissolved `Choropleth`/`Category` show the class, not an unrelated row; `Category` layers get their tooltips.
- `Choropleth` and `Category` no longer share report keys and element ids.
- YAML round-trip keeps `font_scale` and non-string `fill_map` keys; a missing file raises `FileNotFoundError`.
- `Proportional`: `legend=False` hides the legend, `reference_value` alone maps to `max_radius`.
- Custom breaks: data above the last break extends the last class (no more extra class or `IndexError`); any sequence is accepted.
- Numbered labels: `data-label` is escaped once.
- Tooltip styles holding quotes (font families) no longer break the script.
- Tile cache: URL templates sharing a prefix no longer share cached tiles.
- Rasters: data that is not 8-bit (elevation models, 16-bit images) is stretched to 0-255 instead of wrapping into noise; 2-band (grey + alpha) files no longer give a corrupt image; no-data pixels are transparent; `paths` accepts a single path; a missing file raises `FileNotFoundError`.
- A raster in another CRS than the map is skipped with a warning instead of silently drawing nothing.
- Scale bar: correct label on a map in degrees or in feet, and metres instead of `0.1 km` on a small map.
- `source(rotation=...)` with a negative angle no longer writes an invalid `rotate(--90, ...)`; `opacity=0` is honoured.
- Several legends without a `position` are stacked under the map instead of being drawn on top of each other, and their ids are unique (`choropleth-legend-2`...).
- Horizontal choropleth legend: custom `labels` are drawn, the frame encloses the no-data entry, and the canvas grows to show the histogram and rotated labels.
- Legend `title_offset_y` moved the subtitle twice.
- `frame={"enabled": False}` no longer raises; `hatch_style="\\\\\\"` leans backwards as documented.
- `blend_background` and `border_contrast` accept any CSS colour (`"white"`, `"#fff"`, `"rgb(...)"`, the 148 colour names).
- `Situation`: a float column matches integer keys of `symbol` (`1.0` and `1`).
- `ConfigManager.get_colormap` returns a copy, so editing the result no longer alters the palette.

### Changed

- A missing column raises a plain `ValueError` when the layer is created.
- `Label(max_displacement=...)` is measured from the label edge to the symbol edge, so wide labels can move; placements may differ from 1.0.0.
- Element ids of dissolved polygons are `choro-<id>-class<n>`; `Category` elements are numbered with the choropleths.
- Label placement is about twice as fast, with identical results.
- Rasters are resampled to the resolution of the viewport (`defaults.RASTER_PIXEL_RATIO`, 2 raster pixels per SVG pixel), which keeps the SVG small.
- Unknown options in `legend`, in a legend `frame` or in a `style` dict raise a `ValueError` naming the option (they raised a bare `TypeError`, or were ignored for styles). A `labels` list whose length differs from the number of classes is an error.
- `Situation` warns about unknown markers, missing marker files and values without an entry in `symbol`.
- The north arrow label follows `font_scale`, like the other texts.
- New legend options `range_format` (`"de {low} à {high}"`) and, for `FactorLegend`, `variance_label`.

## 1.0.0 (2026-10-30)

First public release.
