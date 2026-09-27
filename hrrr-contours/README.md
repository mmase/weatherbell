# HRRR 2 m temperature: 1° vector isotherms

A self-contained pipeline and web map that takes the latest NOAA HRRR analysis
(2 m temperature, one time step) and renders it as **vector** filled contours on a
MapLibre slippy map, with one contour per 1 °F.

```
./build.sh                         # fetch latest run, build tiles/glyphs/boundaries (~7 min on 4 cores)
npx http-server web -p 8080        # any static server works
```

## How it works

| Step | File | Notes |
|---|---|---|
| Fetch | `scripts/fetch_hrrr.py` | Finds the newest `hrrr.tHHz.wrfsfcf00.grib2` on the NOAA AWS bucket and uses the `.idx` sidecar to range-request only the `TMP:2 m above ground` message (~1.2 MB). |
| Contour + tile | `scripts/build_tiles.py` | Builds z2–z9 Mapbox Vector Tiles directly (own MVT encoder, no tippecanoe). |
| Labels font | `scripts/build_glyphs.py` | Builds a small SDF glyph range (digits, °) so the page needs no glyph server. |
| Basemap | `scripts/build_boundaries.mjs` | Land, coast, country and state lines from Natural Earth / US Census via `world-atlas` and `us-atlas`. |
| Map | `web/index.html` | MapLibre GL JS. Tiles come through a custom `hrrr://` protocol that reads them from pack files. |

### Smoothness

HRRR is a 3 km Lambert grid. Contouring it directly gives kinked polylines with a
vertex every 3 km. Instead, each tile evaluates the field on a finer **global
lattice** in grid-index space using separable Keys bicubic convolution, then contours
that lattice with `contourpy`:

* The lattice step is about 1.6 screen px at every zoom: 8 cells at z2, 1/16 cell at z8,
  and 1/32 cell (~94 m) at z9, which MapLibre overzooms up to z13.
* Bicubic convolution is C¹-continuous, so the isotherms are tangent-continuous curves.
* The kernel is local (4×4), and the lattice is global, so neighbouring tiles compute
  bit-identical values in their overlap. Contours meet exactly at tile seams.
* Low zooms (lattice step ≥ 1 cell) use a light Gaussian prefilter and decimation. The
  only features dropped are ones smaller than about a pixel.

Nothing is simplified or dropped from the fill geometry at any zoom.

### No gaps: stacked superlevel sets

Each tile stores, for every integer t, the polygon **{T ≥ t}**, plus a `base` footprint
polygon. These are painted in ascending t (one fill layer, data-driven colour), so the
visible colour at any point is the colour of the band floor(T) to floor(T)+1:

* Gaps between bands are impossible. Every point inside the domain is covered by the
  base polygon and by each level below its temperature.
* Each isotherm is stored once, not twice as with isobands, and the same polygons'
  outlines are drawn as the 1° contour lines. 32 °F is drawn in white.
* A separate, lightly simplified `labels` line layer is used only for text placement:
  every 10° at z<5.5, every 5° to z8, then every 1°.

### Delivery

Tiles are gzipped and grouped into 364 pack files: one per zoom for z2–z4, per z5
ancestor for z5–z6, and per z7 ancestor for z7–z9. The site is then just static files,
with no range requests and no tile server. The client fetches a pack once, then slices
and inflates tiles with `DecompressionStream`. The z2–z4 packs are prefetched. If
`meta.json` has `"encoding": "base64"`, the client fetches `.txt` base64 copies of the
packs and glyphs instead, for hosts that only serve text.

| zoom | tiles | avg tile (gz) |
|---|---|---|
| 2–4 | 16 | 50–100 KB |
| 5–6 | 122 | 75–120 KB |
| 7–8 | 1567 | 23–48 KB |
| 9 | 4754 | ~15 KB |

Total ≈ 130 MB for all of CONUS down to z9. A typical view loads 1–3 MB.
