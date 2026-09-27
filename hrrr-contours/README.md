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
python3 scripts/publish_grids.py --var t2m  --hours 0-12   # 2 m temperature, 1 °F bands
python3 scripts/publish_grids.py --var pwat --hours 0-12   # precipitable water, 0.1 in bands
npx http-server web -p 8080                                # open /live/ (or /live/#pwat)
```

**Fields** are declared in `VARIABLES` in `publish_grids.py`: the GRIB index line to
fetch, a unit conversion, the band interval, int16 counts per band, and a colour ramp.
Grids are stored in *band units* (value / interval), so the tiler and the browser
contouring code never change when a field is added; the page reads colours, units,
interval and legend ticks from the field's `meta.json`. Precipitable water publishes in
~4.6 s per hour for z2–z6 (2 MB), since it is much smoother than temperature.

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

**Global models (GFS)** are published on the 0.25° lat/lon grid cropped to ±85.25°
(one row past web mercator), with the −180° column repeated at +180° so the field
closes at the date line:

```
python3 scripts/publish_gfs_t2m.py --run 2026092706 --hours 72 --step 6   # 2 m temperature, 0.25°
python3 scripts/publish_gfs_t2m.py --grid t1534 --run 2026092706          # native T1534 grid (13 km)
python3 scripts/publish_gfs_snow.py --run 2026022200 --hours 72            # 10:1 snowfall
```

GFS temperature takes ~4 s for 13 grids (6 MB) and ~3 s per hour for z0–z2 tiles; the
device contours from z3. The page shows global models on a globe that flattens to
Mercator as you zoom in and wraps east–west. Around the globe is space: a star field on
a celestial sphere fixed to the Earth (~6,000 stars with a steep brightness power law
and spectral tints, plus the Milky Way along the real galactic plane, brightest toward
Sagittarius), drawn in a 2D canvas under the transparent map canvas and redrawn only
when the view moves. MapLibre's atmosphere adds the blue limb. The polar caps above the
data (85.25° to 90°) are filled by the WebGL layer with the nearest data row, smoothed
progressively toward the pole, using MapLibre's pole vertices (y = −32768 / 40960).

**GFS T1534 (native 13 km).** NOAA still publishes GFS on the model's own T1534
Gaussian grid (`sfluxgrbfFFF.grib2`, 3072 × 1536, 0.117°), 4.6× the points of the 0.25°
product. Gaussian latitudes are within 1% of evenly spaced, so rows are resampled
(cubic) onto an even 0.1171875° grid and nothing downstream changes. What it costs:

| per forecast hour | 0.25° | T1534 |
|---|---|---|
| grid points (cropped to ±85°) | 1.0 M | 4.5 M |
| full grid, gzipped | 0.6 MB | 2.4 MB |
| every 8th node (pyramid level) | – | 69 KB |
| server: grid + pyramid / z0–z2 tiles | 0.4 s / 3 s | 1.8 s / 12 s |
| device, one z3 tile static / playback | 80 / 25 ms | 69 / 8 ms |
| device, one z7 tile | 12 ms, 2.2 MB GPU | 4 ms, 0.9 MB GPU |

Device contouring is not the bottleneck: the lattice spacing is set in screen pixels,
so a finer grid only replaces the bicubic upsampling the 0.25° grid needed. The costs
that grow with resolution are download and memory, handled by:

* **A grid pyramid.** Each hour is also published at every 2nd, 4th and 8th node
  (`fHH-k.i16.gz`, `meta.levels`). When the lattice step is s nodes (zoomed out, and
  all playback), the device fetches the coarsest level k ≤ s. The lattice reads only
  those nodes, so the contours are identical (checked tile by tile), from 1/4–1/64
  of the data. A globe animation streams 69 KB per hour instead of 2.4 MB.
* **Byte budgets instead of "keep everything".** The page keeps decoded hours in an
  LRU capped at 160 MB (64 MB on ≤4 GB devices), each worker at 48 MB, and playback
  prefetches only the next four hours, so a 300-frame run streams through.
* **Separable node positions.** For lat/lon grids a node's Mercator x depends only on
  its column and y only on its row: two arrays (18 KB) instead of a table per node
  (36 MB per worker at T1534).
* The value readout uses the full grid when paused and the displayed level while
  playing.

Still to do for very large runs: split the full-resolution grid into regional chunks
so zoomed-in playback downloads only the visible area (today it streams whole 2.4 MB
hours at z5+), and move contouring to WebAssembly or the GPU.

Not done yet: contour labels above z6, real-device GPU frame-rate measurements (the
container only has a software rasteriser), and tuning for low-memory phones.
