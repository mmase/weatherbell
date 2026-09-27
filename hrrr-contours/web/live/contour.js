// Client-side vector contouring of a model grid into GPU-ready triangles.
//
// Storm's algorithm (mmase/storm, app/assets/javascripts/maps/gui/smooth.js):
// contour the model grid as-is, then smooth every contour ring with a uniform
// cubic B-spline, adding points along it.  For one web-mercator tile this
//   1. takes the grid nodes around the tile (every s-th node when zoomed out /
//      playing; the raw values, no interpolation), plus a margin;
//   2. traces the ring(s) of every 1-degree superlevel set {T >= t} with
//      marching squares (linear crossings; the window is closed by a border
//      treated as below every level, so every ring is closed);
//   3. smooths each ring with storm's B-spline (same basis, same segment
//      scheme) in screen space, one point every ~spacingPx pixels.  Points on
//      the window border stay fixed, so rings still close along it; that
//      border lies outside the tile, so neighbours match inside it;
//   4. nests the rings (each ring's parent is the smallest ring around it) and
//      fills every band once: a ring minus its children, with earcut, in the
//      band just inside the ring (t around a warm region, t - 1 in a hole); the
//      window minus the outermost rings is the lowest band.  Rings are shared
//      by parent and child, so neighbouring bands meet exactly: no gaps;
//   5. drops the triangles outside the tile.  The renderer masks each tile to
//      its own square with the stencil buffer (the triangulation is conforming,
//      so long triangles are fine on the globe too).
// Output: vertex positions (tile-local, 0..1), a band per vertex, and a
// triangle index list (WebGL2 flat shading; every vertex of a band carries it).
import earcut from "./earcut.js";

const WORLD = 40075016.68557849; // web mercator world width in metres
const D2R = Math.PI / 180;

export class Grid {
  constructor(meta, opts = {}) {
    this.meta = meta;
    const { nx, ny, dx, x0, y0, proj } = meta;
    this.nx = nx; this.ny = ny; this.dx = dx; this.x0 = x0; this.y0 = y0;
    this.latlon = proj.type === "latlon"; // x0/y0/dx in degrees, rows south -> north
    // nominal cell size in metres (sets the lattice density per zoom)
    this.cellM = this.latlon ? dx * 111320 * Math.cos(proj.lat0 * D2R) : dx;
    // pyramid level: this grid holds every k-th node of the published grid
    this.k = meta.levelK || 1;
    // global grids wrap east-west: column nx-1 repeats column 0, one period = nx-1 columns
    this.period = meta.global ? nx - 1 : 0;
    // Lambert conformal conic on a sphere (HRRR/NAM style); lat1 == lat2 is the tangent case.
    const R = proj.R, p1 = proj.lat1 * D2R, p2 = proj.lat2 * D2R, p0 = proj.lat0 * D2R;
    const n = Math.abs(p1 - p2) < 1e-10 ? Math.sin(p1)
      : Math.log(Math.cos(p1) / Math.cos(p2)) / Math.log(Math.tan(Math.PI / 4 + p2 / 2) / Math.tan(Math.PI / 4 + p1 / 2));
    const F = Math.cos(p1) * Math.pow(Math.tan(Math.PI / 4 + p1 / 2), n) / n;
    this.lcc = { R, n, F, rho0: R * F / Math.pow(Math.tan(Math.PI / 4 + p0 / 2), n), lon0: proj.lon0 * D2R };
    if (opts.positions === false) return;
    // web-mercator position of every grid node, stored as float32 offsets from
    // the first node (relative precision stays ~1e-8 of the world at any zoom)
    const [ox, oy] = this.nodeMerc(0, 0);
    this.ox = ox; this.oy = oy;
    if (this.latlon) { // separable: x depends only on the column, y only on the row
      this.px = Float32Array.from({ length: nx }, (_, i) => this.nodeMerc(i, 0)[0] - ox);
      this.py = Float32Array.from({ length: ny }, (_, j) => this.nodeMerc(0, j)[1] - oy);
      return;
    }
    const pos = new Float32Array(nx * ny * 2);
    let o = 0;
    for (let j = 0; j < ny; j++) {
      for (let i = 0; i < nx; i++) {
        const [mx, my] = this.nodeMerc(i, j);
        pos[o++] = mx - ox; pos[o++] = my - oy;
      }
    }
    this.pos = pos;
  }

  // grid node (fractional allowed) -> web mercator 0..1
  nodeMerc(i, j) {
    if (this.latlon) {
      const lon = this.x0 + i * this.dx, lat = this.y0 + j * this.dx;
      return [lon / 360 + 0.5, 0.5 - Math.log(Math.tan(Math.PI / 4 + lat * D2R / 2)) / (2 * Math.PI)];
    }
    const { R, n, F, rho0, lon0 } = this.lcc;
    const x = this.x0 + i * this.dx, y = this.y0 + j * this.dx;
    const dy = rho0 - y;
    const rho = Math.sign(n) * Math.hypot(x, dy);
    const theta = Math.atan2(Math.sign(n) * x, Math.sign(n) * dy);
    const lat = 2 * Math.atan(Math.pow(R * F / rho, 1 / n)) - Math.PI / 2;
    const lon = lon0 + theta / n;
    return [(lon / (2 * Math.PI)) + 0.5, 0.5 - Math.log(Math.tan(Math.PI / 4 + lat / 2)) / (2 * Math.PI)];
  }

  // lon/lat (degrees) -> fractional grid index
  lonLatToIJ(lon, lat) {
    if (this.latlon) {
      // any world copy (only wrap values outside the grid's own 360 degrees, so +180 stays at the east end)
      if (this.period && (lon < this.x0 || lon > this.x0 + 360)) lon = ((lon - this.x0) % 360 + 360) % 360 + this.x0;
      return [(lon - this.x0) / this.dx, (lat - this.y0) / this.dx];
    }
    const { R, n, F, rho0, lon0 } = this.lcc;
    const rho = R * F / Math.pow(Math.tan(Math.PI / 4 + lat * D2R / 2), n);
    let dl = lon * D2R - lon0;
    dl = Math.atan2(Math.sin(dl), Math.cos(dl));
    const x = rho * Math.sin(n * dl), y = rho0 - rho * Math.cos(n * dl);
    return [(x - this.x0) / this.dx, (y - this.y0) / this.dx];
  }

  // lattice step (in grid cells) for a tile zoom: ~spacingPx screen px at the
  // domain's reference latitude, rounded to a power of two, at most 1 cell
  step(z, spacingPx, allowCoarse = false) {
    const mPerPx = WORLD * Math.cos(this.meta.proj.lat0 * D2R) / (512 * 2 ** z);
    // in nodes of the full-resolution grid, then in this level's nodes
    const s = 2 ** Math.round(Math.log2(spacingPx * mPerPx / (this.cellM / this.k)));
    return Math.min(allowCoarse ? 16 : 1, s) / this.k; // playback: up to every 16th node
  }
}

// Uniform cubic B-spline basis for a point at t along the segment p1 -> p2 of
// control points p0..p3 (storm's k0..k3).
function bspline(t, out, o) {
  const t2 = t * t, t3 = t2 * t, v = 1 - t;
  out[o] = v * v * v / 6;
  out[o + 1] = (3 * t3 - 6 * t2 + 4) / 6;
  out[o + 2] = (-3 * t3 + 3 * t2 + 3 * t + 1) / 6;
  out[o + 3] = t3 / 6;
}

// growable typed arrays
class Buf {
  constructor(Type, n) { this.T = Type; this.a = new Type(n); this.n = 0; }
  grow(k) { if (this.n + k > this.a.length) { const b = new this.T(Math.max(this.a.length * 2, this.n + k)); b.set(this.a); this.a = b; } }
  out() { return this.a.slice(0, this.n); }
}

/**
 * Contour one tile.
 * fields: [Int16Array] or [Int16Array, Int16Array] (values = degF * scale);
 * w: blend weight toward the second field (morphing between forecast hours).
 */
export function contourTile(grid, fields, w, z, x, y, spacingPx = 2, allowCoarse = false, globe = false) {
  const { nx, ny } = grid, scale = grid.meta.scale;
  const tz = 2 ** z, tx0 = x / tz, ty0 = y / tz, ts = 1 / tz;
  // grid window covering the tile (sample its edges; mercator -> lon/lat -> ij)
  let i0 = Infinity, i1 = -Infinity, j0 = Infinity, j1 = -Infinity;
  for (let k = 0; k <= 16; k++) {
    for (const [mx, my] of [[tx0 + ts * k / 16, ty0], [tx0 + ts * k / 16, ty0 + ts], [tx0, ty0 + ts * k / 16], [tx0 + ts, ty0 + ts * k / 16]]) {
      const lon = (mx - 0.5) * 360, lat = Math.atan(Math.sinh(Math.PI * (1 - 2 * my))) / D2R;
      const [i, j] = grid.lonLatToIJ(lon, lat);
      if (i < i0) i0 = i; if (i > i1) i1 = i; if (j < j0) j0 = j; if (j > j1) j1 = j;
    }
  }
  const s = Math.max(1, grid.step(z, spacingPx, allowCoarse)); // raw nodes, never interpolated
  // margin beyond the tile, in this level's nodes: the smoothing near the fixed
  // window border (2 nodes) stays outside the tile (same window at every pyramid level)
  const pad = 4 * s + Math.max(i1 - i0, j1 - j0) * TILE_OVERLAP + 0.1 / grid.k; // + the drawn overlap
  const PER = grid.period; // global: columns wrap, so the window may run past either end
  const ni0 = PER ? Math.ceil((i0 - pad) / s) : Math.max(0, Math.ceil((i0 - pad) / s));
  const ni1 = PER ? Math.floor((i1 + pad) / s) : Math.min(Math.floor((nx - 1) / s), Math.floor((i1 + pad) / s));
  const wrapCol = (c) => (PER ? ((c % PER) + PER) % PER : Math.min(nx - 1, Math.max(0, c)));
  const nj0 = Math.max(0, Math.ceil((j0 - pad) / s)), nj1 = Math.min(Math.floor((ny - 1) / s), Math.floor((j1 + pad) / s));
  const lw = ni1 - ni0 + 1, lh = nj1 - nj0 + 1;
  if (lw < 2 || lh < 2) return null;
  const np = lw * lh;

  // ---- node values (band units) and tile-local positions
  const val = new Float64Array(np);
  const A = fields[0], B = fields[1];
  const wa = B ? 1 - w : 1, wb = B ? w : 0;
  let vmin = Infinity, vmax = -Infinity;
  for (let r = 0; r < lh; r++) {
    const row = (nj0 + r) * s * nx;
    for (let c = 0; c < lw; c++) {
      const g = row + wrapCol((ni0 + c) * s);
      const v = (B ? A[g] * wa + B[g] * wb : A[g]) / scale;
      val[r * lw + c] = v; if (v < vmin) vmin = v; if (v > vmax) vmax = v;
    }
  }
  const nxy = new Float64Array(np * 2);
  const gp = grid.pos, gx = grid.px, gy = grid.py, ox = grid.ox - tx0, oy = grid.oy - ty0;
  for (let r = 0; r < lh; r++) {
    const j = (nj0 + r) * s;
    for (let c = 0; c < lw; c++) {
      let i = (ni0 + c) * s, shift = 0;
      if (PER) { shift = Math.floor(i / PER); i -= shift * PER; } // world copy: +1 mercator width per period
      const mx = gx ? gx[i] : gp[(j * nx + i) * 2], my = gy ? gy[j] : gp[(j * nx + i) * 2 + 1];
      const p = (r * lw + c) * 2;
      nxy[p] = (mx + ox + shift) * tz; nxy[p + 1] = (my + oy) * tz;
    }
  }
  // lattice (x, y) -> tile-local (bilinear between nodes; crossings lie on edges, so linear)
  const toTile = (x, y, out, o) => {
    const c = Math.min(lw - 2, Math.max(0, Math.floor(x))), r = Math.min(lh - 2, Math.max(0, Math.floor(y)));
    const fx = x - c, fy = y - r, p00 = (r * lw + c) * 2, p10 = p00 + 2, p01 = p00 + lw * 2, p11 = p01 + 2;
    out[o] = (nxy[p00] * (1 - fx) + nxy[p10] * fx) * (1 - fy) + (nxy[p01] * (1 - fx) + nxy[p11] * fx) * fy;
    out[o + 1] = (nxy[p00 + 1] * (1 - fx) + nxy[p10 + 1] * fx) * (1 - fy) + (nxy[p01 + 1] * (1 - fx) + nxy[p11 + 1] * fx) * fy;
  };

  const lo = Math.floor(vmin + EPS), hi = Math.floor(vmax + EPS);
  const pxPerUnit = 512, delta = Math.max(1, spacingPx) / pxPerUnit; // one smoothed point per ~spacingPx px
  // rings, smoothed in tile space (border points pinned)
  const rings = hi > lo ? traceRings(val, lw, lh, lo + 1, hi) : [];
  // Rings that run along the window border share it with their parent; earcut
  // treats such overlapping edges as intersections (and slows down a lot).  So
  // border points move outward by a small step per level below the top: lower
  // levels (outer rings) further out, the window furthest.  This all lies in
  // the margin outside the tile.
  const eps = 0.2 / (hi - lo + 2); // lattice nodes per level
  const out = (x, y, d, o, xy) => {
    xy[o] = x <= 1e-9 ? x - d : x >= lw - 1 - 1e-9 ? x + d : x;
    xy[o + 1] = y <= 1e-9 ? y - d : y >= lh - 1 - 1e-9 ? y + d : y;
  };
  const toTileOut = (x, y, d, arr, o) => {
    // outside the window: extrapolate from the border nodes
    const c = Math.min(lw - 2, Math.max(0, Math.floor(x))), r = Math.min(lh - 2, Math.max(0, Math.floor(y)));
    const fx = x - c, fy = y - r, p00 = (r * lw + c) * 2, p10 = p00 + 2, p01 = p00 + lw * 2, p11 = p01 + 2;
    arr[o] = (nxy[p00] * (1 - fx) + nxy[p10] * fx) * (1 - fy) + (nxy[p01] * (1 - fx) + nxy[p11] * fx) * fy;
    arr[o + 1] = (nxy[p00 + 1] * (1 - fx) + nxy[p10 + 1] * fx) * (1 - fy) + (nxy[p01 + 1] * (1 - fx) + nxy[p11 + 1] * fx) * fy;
  };
  const tmp = [0, 0];
  const smooth = rings.map((rg) => {
    const n = rg.xy.length / 2, tile = new Float64Array(n * 2), pin = new Uint8Array(n);
    const d = eps * (hi - rg.level + 1);
    for (let q = 0; q < n; q++) {
      const x = rg.xy[q * 2], y = rg.xy[q * 2 + 1];
      pin[q] = x <= 1e-9 || y <= 1e-9 || x >= lw - 1 - 1e-9 || y >= lh - 1 - 1e-9 ? 1 : 0;
      if (pin[q]) { out(x, y, d, 0, tmp); toTileOut(tmp[0], tmp[1], d, tile, q * 2); } else toTile(x, y, tile, q * 2);
    }
    // samples within each spline segment are thinned to those the curve needs
    // (within 1/8 of the lattice spacing): fewer vertices to triangulate, and
    // decided per segment, so every tile gets the same curve
    return smoothRing(tile, pin, delta, Math.max(1, spacingPx) / 8 / pxPerUnit);
  });
  const parent = nestRings(rings, lw, lh);
  const children = Array.from({ length: rings.length + 1 }, () => []); // index rings.length = the window
  for (let i = 0; i < rings.length; i++) children[parent[i] < 0 ? rings.length : parent[i]].push(i);

  const P = new Buf(Float32Array, 65536), Bd = new Buf(Int16Array, 32768), I = new Buf(Uint32Array, 98304);
  const r0 = -TILE_OVERLAP, r1 = 1 + TILE_OVERLAP;
  const put = (ax, ay, bx, by, cx, cy, band) => {
    if (Math.max(ax, bx, cx) < r0 || Math.min(ax, bx, cx) > r1 || Math.max(ay, by, cy) < r0 || Math.min(ay, by, cy) > r1) return;
    P.grow(6); Bd.grow(3); I.grow(3);
    const k = Bd.n, pa = P.a;
    pa[P.n++] = ax; pa[P.n++] = ay; pa[P.n++] = bx; pa[P.n++] = by; pa[P.n++] = cx; pa[P.n++] = cy;
    Bd.a[Bd.n++] = band; Bd.a[Bd.n++] = band; Bd.a[Bd.n++] = band;
    I.a[I.n++] = k; I.a[I.n++] = k + 1; I.a[I.n++] = k + 2;
  };
  const emit = put;
  // one band: outer ring minus its holes
  const fillBand = (outer, holes, band) => {
    const flat = Array.from(outer), hi_ = [];
    for (const h of holes) { hi_.push(flat.length / 2); for (const v of h) flat.push(v); }
    const tri = earcut(flat, hi_.length ? hi_ : null);
    for (let t = 0; t < tri.length; t += 3) {
      const a = tri[t] * 2, b = tri[t + 1] * 2, c = tri[t + 2] * 2;
      emit(flat[a], flat[a + 1], flat[b], flat[b + 1], flat[c], flat[c + 1], band);
    }
  };
  // the window (lowest band) minus the outermost rings
  {
    const ring = [], d = eps * (hi - lo + 2);
    const put = (x, y) => { const o = ring.length; ring.push(0, 0); out(x, y, d, 0, tmp); toTileOut(tmp[0], tmp[1], d, ring, o); };
    for (let c = 0; c < lw; c++) put(c, 0);
    for (let r = 1; r < lh; r++) put(lw - 1, r);
    for (let c = lw - 2; c >= 0; c--) put(c, lh - 1);
    for (let r = lh - 2; r > 0; r--) put(0, r);
    fillBand(ring, children[rings.length].map((i) => smooth[i]), lo);
  }
  // each ring minus its children, in the band just inside it
  for (let i = 0; i < rings.length; i++) {
    fillBand(smooth[i], children[i].map((j) => smooth[j]), rings[i].area < 0 ? rings[i].level : rings[i].level - 1);
  }
  return { pos: P.out(), band: Bd.out(), index: I.out(), lattice: [lw, lh], step: s };
}

const TILE_OVERLAP = 1 / 64; // triangles within this of the tile are kept (the stencil trims them)

// Parent of every ring (index, or -1 for the window): the smallest ring that
// contains it.  Rings of a marching-squares trace never cross, so one vertex off
// the window border tells.  Rings that run only along the border have the same
// outline at several levels; they nest by level (a higher level's warm region
// inside a lower one's, a lower level's hole inside a higher one's).
// Candidates come from a coarse grid of ring bounding boxes.
function nestRings(rings, lw, lh) {
  const n = rings.length, parent = new Int32Array(n).fill(-1);
  if (n < 2) return parent;
  const box = new Float64Array(n * 4), area = new Float64Array(n), probe = new Float64Array(n * 2), border = new Uint8Array(n);
  const onB = (x, y) => x <= 1e-9 || y <= 1e-9 || x >= lw - 1 - 1e-9 || y >= lh - 1 - 1e-9;
  for (let i = 0; i < n; i++) {
    const xy = rings[i].xy;
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity, found = false;
    for (let q = 0; q < xy.length; q += 2) {
      const x = xy[q], y = xy[q + 1];
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y;
      if (!found && q + 3 < xy.length && !onB(x, y) && !onB(xy[q + 2], xy[q + 3])) {
        // midpoint of a segment: inside a cell, off every other ring, off row lines
        probe[i * 2] = (x + xy[q + 2]) / 2; probe[i * 2 + 1] = (y + xy[q + 3]) / 2; found = true;
      }
    }
    box.set([x0, x1, y0, y1], i * 4); area[i] = Math.abs(rings[i].area); border[i] = found ? 0 : 1;
  }
  // total order, inner first: area, then (same outline) by level as above
  const order = Array.from({ length: n }, (_, i) => i).sort((a, b) => {
    const d = area[a] - area[b];
    if (Math.abs(d) > 1e-9 * Math.max(area[a], area[b])) return d;
    const oa = rings[a].area < 0, ob = rings[b].area < 0;
    return (oa ? -rings[a].level : rings[a].level) - (ob ? -rings[b].level : rings[b].level);
  });
  const rank = new Int32Array(n), rowIndex = new Map();
  order.forEach((i, r) => { rank[i] = r; });
  // rings along the border only: each inside the next one of them in the order
  let prev = -1;
  for (const i of order) if (border[i]) { if (prev >= 0) parent[prev] = i; prev = i; }
  const G = 32, gx = (lw + 1) / G, gy = (lh + 1) / G;
  const cell = (x, y) => Math.min(G - 1, Math.max(0, Math.floor((x + 1) / gx))) + G * Math.min(G - 1, Math.max(0, Math.floor((y + 1) / gy)));
  const buckets = Array.from({ length: G * G }, () => []);
  for (const i of order) {
    const c0 = cell(box[i * 4], box[i * 4 + 2]), c1 = cell(box[i * 4 + 1], box[i * 4 + 3]);
    for (let cy = Math.floor(c0 / G); cy <= Math.floor(c1 / G); cy++) for (let cx = c0 % G; cx <= c1 % G; cx++) buckets[cy * G + cx].push(i);
  }
  for (let i = 0; i < n; i++) {
    if (border[i]) continue;
    const px = probe[i * 2], py = probe[i * 2 + 1];
    for (const j of buckets[cell(px, py)]) {
      if (rank[j] <= rank[i]) continue;
      if (px < box[j * 4] || px > box[j * 4 + 1] || py < box[j * 4 + 2] || py > box[j * 4 + 3]) continue;
      if (inRingRows(px, py, j)) { parent[i] = j; break; }
    }
  }
  return parent;

  // point-in-ring with the ring's edges bucketed by lattice row (built on first use):
  // marching-squares edges stay inside one cell, so one row's edges decide
  function inRingRows(x, y, j) {
    let rows = rowIndex.get(j);
    if (!rows) {
      rows = new Map();
      const xy = rings[j].xy, m = xy.length / 2;
      for (let q = 0, p = m - 1; q < m; p = q++) {
        const ya = xy[p * 2 + 1], yb = xy[q * 2 + 1];
        for (let r = Math.floor(Math.min(ya, yb)); r <= Math.floor(Math.max(ya, yb)); r++) {
          let a = rows.get(r); if (!a) rows.set(r, (a = [])); a.push(p, q);
        }
      }
      rowIndex.set(j, rows);
    }
    const e = rows.get(Math.floor(y));
    if (!e) return false;
    const xy = rings[j].xy;
    let c = false;
    for (let k = 0; k < e.length; k += 2) {
      const p = e[k], q = e[k + 1], xq = xy[q * 2], yq = xy[q * 2 + 1], xp = xy[p * 2], yp = xy[p * 2 + 1];
      if ((yq > y) !== (yp > y) && x < (xp - xq) * (y - yq) / (yp - yq) + xq) c = !c;
    }
    return c;
  }
}


const EPS = 1e-4; // contour levels sit this far below each integer (data are in 0.1-degree steps)
const GHOST = -1e30; // the border around the window: below every level

// Marching squares for every level t in [t0, t1] at once: closed rings of the
// superlevel set {v >= t - EPS}, in lattice coordinates, with the window closed by
// a GHOST border.  Segments keep the "above" side on their left (y down), so a
// ring around a warm region has negative area and a hole positive area.
// Edge ids: horizontal edge (i, j)-(i+1, j) = 2 (j W + i), vertical (i, j)-(i, j+1) = +1,
// in border-padded coordinates (W = lw + 2).
function traceRings(val, lw, lh, t0, t1) {
  const W = lw + 2, H = lh + 2, nl = t1 - t0 + 1;
  const V = (i, j) => (i < 1 || j < 1 || i > lw || j > lh ? GHOST : val[(j - 1) * lw + (i - 1)]);
  // segments of every level, as flat arrays (start edge, end edge, level)
  let cap = 1 << 16, sS = new Int32Array(cap), sE = new Int32Array(cap), sL = new Int32Array(cap), ns = 0;
  const seg = (a, b, q) => {
    if (ns === cap) { cap *= 2; const g = (x) => { const y = new Int32Array(cap); y.set(x); return y; }; sS = g(sS); sE = g(sE); sL = g(sL); }
    sS[ns] = a; sE[ns] = b; sL[ns++] = q;
  };
  for (let j = 0; j < H - 1; j++) {
    for (let i = 0; i < W - 1; i++) {
      const a = V(i, j), b = V(i + 1, j), c = V(i + 1, j + 1), d = V(i, j + 1);
      const mn = Math.min(a, b, c, d), mx = Math.max(a, b, c, d);
      const ta = Math.max(t0, Math.floor(mn + EPS) + 1), tb = Math.min(t1, Math.floor(mx + EPS));
      if (ta > tb) continue;
      const T = 2 * (j * W + i), Bm = 2 * ((j + 1) * W + i), Lf = T + 1, R = 2 * (j * W + i + 1) + 1;
      for (let t = ta; t <= tb; t++) {
        const L = t - EPS, q = t - t0;
        switch ((a >= L ? 1 : 0) | (b >= L ? 2 : 0) | (c >= L ? 4 : 0) | (d >= L ? 8 : 0)) {
          case 1: seg(Lf, T, q); break;
          case 2: seg(T, R, q); break;
          case 3: seg(Lf, R, q); break;
          case 4: seg(R, Bm, q); break;
          case 5: if ((a + b + c + d) / 4 >= L) { seg(R, T, q); seg(Lf, Bm, q); } else { seg(Lf, T, q); seg(R, Bm, q); } break;
          case 6: seg(T, Bm, q); break;
          case 7: seg(Lf, Bm, q); break;
          case 8: seg(Bm, Lf, q); break;
          case 9: seg(Bm, T, q); break;
          case 10: if ((a + b + c + d) / 4 >= L) { seg(T, Lf, q); seg(Bm, R, q); } else { seg(T, R, q); seg(Bm, Lf, q); } break;
          case 11: seg(Bm, R, q); break;
          case 12: seg(R, Lf, q); break;
          case 13: seg(R, T, q); break;
          case 14: seg(T, Lf, q); break;
        }
      }
    }
  }
  // group segments by level (counting sort), then chain each level through a
  // start-edge -> end-edge table (reset after each level)
  const cnt = new Int32Array(nl + 1);
  for (let k = 0; k < ns; k++) cnt[sL[k] + 1]++;
  for (let q = 0; q < nl; q++) cnt[q + 1] += cnt[q];
  const byL = new Int32Array(ns), fillp = cnt.slice(0, nl);
  for (let k = 0; k < ns; k++) byL[fillp[sL[k]]++] = k;
  const next = new Int32Array(2 * W * H).fill(-1);
  const rings = [];
  for (let q = 0; q < nl; q++) {
    const L = t0 + q - EPS;
    for (let k = cnt[q]; k < cnt[q + 1]; k++) next[sS[byL[k]]] = sE[byL[k]];
    for (let k = cnt[q]; k < cnt[q + 1]; k++) {
      const e0 = sS[byL[k]];
      if (next[e0] < 0) continue; // already used
      const xy = [];
      let e = e0, area = 0, guard = 0;
      do {
        const vert = e & 1, idx = e >> 1, i = idx % W, j = (idx - i) / W;
        const v0 = V(i, j), v1 = vert ? V(i, j + 1) : V(i + 1, j);
        const f = Math.min(1, Math.max(0, (L - v0) / (v1 - v0)));
        xy.push(vert ? i - 1 : i - 1 + f, vert ? j - 1 + f : j - 1);
        const nx = next[e]; next[e] = -1; e = nx;
      } while (e !== e0 && e >= 0 && ++guard < 1e7);
      const n = xy.length / 2;
      if (n < 3) continue;
      for (let p = 0; p < n; p++) { const r = (p + 1) % n; area += xy[p * 2] * xy[r * 2 + 1] - xy[r * 2] * xy[p * 2 + 1]; }
      if (Math.abs(area) < 1e-12) continue;
      rings.push({ level: t0 + q, xy, area: area / 2 });
    }
  }
  return rings;
}

// Storm's ring smoothing: for each segment p1 -> p2 of a closed ring, the uniform
// cubic B-spline of p0..p3, sampled every `delta` along the segment.  Pinned points
// (on the window border) are kept exactly: segments touching them stay straight,
// and a spline segment next to one uses a mirrored phantom point so it starts or
// ends exactly on it.  Rings under 4 points are kept as they are (like storm).
function smoothRing(ring, pin, delta, tol = 0) {
  const n = ring.length / 2;
  if (n < 4) return Array.from(ring);
  const out = [];
  const w = new Float64Array(4);
  for (let i = 0; i < n; i++) {
    const i0 = (i - 1 + n) % n, i2 = (i + 1) % n, i3 = (i + 2) % n;
    const x1 = ring[i * 2], y1 = ring[i * 2 + 1], x2 = ring[i2 * 2], y2 = ring[i2 * 2 + 1];
    if (pin[i] || pin[i2]) { out.push(x1, y1); continue; } // straight along the border
    let x0 = ring[i0 * 2], y0 = ring[i0 * 2 + 1], x3 = ring[i3 * 2], y3 = ring[i3 * 2 + 1];
    if (pin[i0]) { x0 = 2 * x1 - x2; y0 = 2 * y1 - y2; }
    if (pin[i3]) { x3 = 2 * x2 - x1; y3 = 2 * y2 - y1; }
    // one point per delta, at most 64 per segment (zoomed far in a segment spans
    // thousands of px; 64 chords of a cubic stay within ~0.2 px of the curve)
    const k = Math.min(64, Math.max(1, Math.ceil(Math.hypot(x2 - x1, y2 - y1) / delta)));
    const sx = new Float64Array(k + 1), sy = new Float64Array(k + 1);
    for (let q = 0; q <= k; q++) {
      bspline(q / k, w, 0);
      sx[q] = w[0] * x0 + w[1] * x1 + w[2] * x2 + w[3] * x3; sy[q] = w[0] * y0 + w[1] * y1 + w[2] * y2 + w[3] * y3;
    }
    // Douglas-Peucker within the segment (its end is the next segment's start)
    const keep = new Uint8Array(k + 1); keep[0] = keep[k] = 1;
    if (k > 1 && tol > 0) {
      const stack = [0, k], t2 = tol * tol;
      while (stack.length) {
        const e = stack.pop(), b = stack.pop(), dx = sx[e] - sx[b], dy = sy[e] - sy[b], L = dx * dx + dy * dy;
        let best = -1, bd = t2;
        for (let q = b + 1; q < e; q++) {
          const px = sx[q] - sx[b], py = sy[q] - sy[b], t = L ? Math.max(0, Math.min(1, (px * dx + py * dy) / L)) : 0;
          const d = (px - t * dx) ** 2 + (py - t * dy) ** 2;
          if (d > bd) { bd = d; best = q; }
        }
        if (best >= 0) { keep[best] = 1; stack.push(b, best, best, e); }
      }
    } else keep.fill(1);
    for (let q = 0; q < k; q++) if (keep[q]) out.push(sx[q], sy[q]);
  }
  return out;
}

// value at lon/lat for the readout: bilinear on the raw grid (what the rings are traced from)
export function sample(grid, fields, w, lon, lat) {
  const [u, v] = grid.lonLatToIJ(lon, lat);
  const { nx, ny } = grid;
  if (u < 0 || v < 0 || u > nx - 1 || v > ny - 1) return null;
  const A = fields[0], B = fields[1];
  const i = Math.min(nx - 2, Math.floor(u)), j = Math.min(ny - 2, Math.floor(v)), fx = u - i, fy = v - j;
  const at = (c, r) => { const g = r * nx + c; return B ? A[g] * (1 - w) + B[g] * w : A[g]; };
  const acc = (at(i, j) * (1 - fx) + at(i + 1, j) * fx) * (1 - fy) + (at(i, j + 1) * (1 - fx) + at(i + 1, j + 1) * fx) * fy;
  return acc / grid.meta.scale;
}

// Pyramid level k of a published grid: every k-th node (published as fHH-k.i16.gz
// for the k in meta.levels).  Contouring with a lattice step of s >= k nodes
// reads only these nodes, so the result is identical to using the full grid.
export function levelMeta(meta, k) {
  if (k === 1) return meta;
  return { ...meta, levelK: k, nx: (meta.nx - 1) / k + 1, ny: (meta.ny - 1) / k + 1, dx: meta.dx * k };
}

