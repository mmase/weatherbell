# HRRR 2 m temperature: 1° vector isotherms

A self-contained pipeline and web map that takes the latest NOAA HRRR analysis
(2 m temperature, one time step) and renders it as **vector** filled contours on a
MapLibre slippy map, with one contour per 1 °F.

```
./build.sh                         # fetch latest run, build tiles/glyphs/boundaries (~2.5 min on 4 cores)
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

* The lattice step is about 1.6 screen px from z5 up (1 cell at z5, 1/16 cell at z8,
  and 1/32 cell, ~94 m, at z9, which MapLibre overzooms up to z13). It is never coarser
  than the native 3 km grid, so z2–z4 carry every model feature too.
* Bicubic convolution is C¹-continuous, so the isotherms are tangent-continuous curves.
* The kernel is local (4×4), and the lattice is global, so neighbouring tiles compute
  bit-identical values in their overlap. Contours meet exactly at tile seams.

Nothing is simplified or dropped from the fill geometry at any zoom.

### No gaps: stacked superlevel sets

Each tile stores, for every integer t, the polygon **{T ≥ t}**, plus a `base` footprint
polygon. These are painted in ascending t, so the visible colour at any point is the
colour of the band floor(T) to floor(T)+1:

* Gaps between bands are impossible. Every point inside the domain is covered by the
  base polygon and by each level below its temperature.
* Each isotherm is stored once, not twice as with isobands. The bands are drawn
  without outline strokes.
* Because levels are stacked, each ring can be simplified on its own without opening
  gaps. Rings are thinned with Douglas-Peucker at 0.3 px of their own zoom (in
  overzoomed px at z9); a ring that would collapse keeps its original shape, so no
  feature is ever removed.
* The client draws one fill layer per degree with a constant colour. MapLibre renders
  constant opaque fills in its opaque pass (top layer first, depth-tested), so hidden
  lower levels are rejected by the GPU instead of being blended once per degree.
* A separate, lightly simplified `labels` line layer is used only for text placement:
  every 10° at z<5.5, every 5° to z8, then every 1°.

### Delivery

Tiles are gzipped and grouped into 364 pack files: one per zoom for z2–z4, per z5
ancestor for z5–z6, and per z7 ancestor for z7–z9. The site is then just static files,
with no range requests and no tile server. The client fetches a pack once, then slices
and inflates tiles with `DecompressionStream`. If
`meta.json` has `"encoding": "base64"`, the client fetches `.txt` base64 copies of the
packs and glyphs instead, for hosts that only serve text.

| zoom | tiles | avg tile (gz) |
|---|---|---|
| 2–4 | 16 | 200–540 KB |
| 5–6 | 122 | 46–95 KB |
| 7–8 | 1567 | 13–30 KB |
| 9 | 4754 | ~9 KB |

Total ≈ 82 MB for all of CONUS down to z9. A whole-US view loads one 1.1–2.0 MB pack.

### Build speed

Tiles are independent, so `build_tiles.py` runs one process per core (biggest tiles
first). Each worker is pinned to one BLAS/OpenMP thread: letting every worker also
spawn a thread per core oversubscribed the CPU and more than doubled the build time.
Ring cleanup and MVT encoding are vectorised with numpy, so the remaining time is
mostly contourpy, GEOS and PROJ (C/C++).

## Live forecast map (`web/live/`, prototype)

A second page aimed at publishing a model run within seconds of its release and
animating it. The server does as little as possible; each device contours what
it is looking at.

```
python3 scripts/publish_grids.py --hours 0-12 --tiles-maxzoom 6   # latest run
npx http-server web -p 8080                                        # open /live/
```

**Server, per forecast hour** (`publish_grids.py`): range-fetch the 2 m temperature
message, store it as row-delta int16 tenths of °F, gzip (~1.4 MB, ~1–2 s), then build
the z2–z6 tiles from that same grid (~11 s on 4 cores, ~11 MB). Hours run as soon as
their `.idx` appears, so in production this hangs off NOAA's new-object notifications.

**Browser** (`contour.js`, `worker.js`):

* z2–z6: the server tiles, one constant-colour MapLibre fill layer per degree.
* z7 and up: a WebGL2 custom layer. A pool of module workers contours each visible
  tile from the grid with the same lattice rule as the server (never coarser than the
  native grid, Keys bicubic below it). Each lattice cell is split into two triangles
  and each triangle is cut into 1° slabs (convex, so each piece is a fan). The output
  is triangles directly, so there is no polygon assembly or earcut step. Boundary
  points on a shared edge are computed from the edge's endpoints in a fixed order, so
  neighbours meet exactly. Uniform areas are merged with a quadtree whose blocks keep
  every perimeter vertex (no T-junction cracks). Bands use WebGL2 `flat` shading, and
  the palette is shared with the tile layers so there is no colour jump at z7. There
  is no zoom cap.
* Playback: every zoom switches to the WebGL layer with a coarser lattice (4 px), and
  the two neighbouring forecast hours are blended before contouring, so bands morph
  between hours. A new frame is requested only after the previous one has been
  drawn, so slower devices show fewer in-between frames instead of falling behind.
* The readout samples the grid (bicubic), so it shows the actual value, e.g. 62.4 °F.

Measured in this repo's container (Node / headless Chromium, 4 vCPU):

| | |
|---|---|
| Publish one hour (grid) | 1–2 s |
| Publish one hour (grid + z2–z6 tiles) | ~13 s |
| Worker time per tile, z12 / z8 / z4 during playback | 11 / 31 / 58 ms |
| GPU data per tile at z9 / z12 | ~5 / ~3 MB |

Not done yet: contour labels above z6, real-device GPU frame-rate measurements (the
container only has a software rasteriser), and tuning for low-memory phones.
