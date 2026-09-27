// Client-side vector contouring of a model grid into GPU-ready triangles.
//
// For one web-mercator tile this
//   1. picks a lattice in model-grid index space whose step is ~spacingPx
//      screen pixels (never coarser than the native grid).  The lattice is
//      global for a zoom level, so neighbouring tiles share lattice points;
//   2. evaluates the field there: native values when the step is one cell,
//      otherwise Keys bicubic convolution (C1-smooth, local 4x4 support, so
//      every tile computes identical values for shared points);
//   3. splits each lattice cell into two triangles and cuts each triangle into
//      1-degree bands (triangle ∩ slab is convex, so each piece is a fan).
//      Boundary points on a shared edge are always computed from the edge's
//      endpoints in the same order, so neighbouring triangles meet exactly:
//      no gaps, no overlaps, no triangulation library.
// Output: vertex positions (tile-local, 0..1), a band per vertex, and a
// triangle index list whose last vertex carries the triangle's band (WebGL2
// flat shading uses the last "provoking" vertex).

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
    return Math.min(allowCoarse ? 8 : 1, s) / this.k;
  }
}

// Keys (a = -0.5) cubic convolution weights
function keys(t, out, o) {
  const a = -0.5, t2 = t * t, t3 = t2 * t;
  const u = 1 + t, v = 1 - t, w = 2 - t;
  out[o] = a * u * u * u - 5 * a * u * u + 8 * a * u - 4 * a;
  out[o + 1] = (a + 2) * t3 - (a + 3) * t2 + 1;
  out[o + 2] = (a + 2) * v * v * v - (a + 3) * v * v + 1;
  out[o + 3] = a * w * w * w - 5 * a * w * w + 8 * a * w - 4 * a;
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
export function contourTile(grid, fields, w, z, x, y, spacingPx = 2, allowCoarse = false) {
  const { nx, ny } = grid, scale = grid.meta.scale;
  const tz = 2 ** z, tx0 = x / tz, ty0 = y / tz, ts = 1 / tz;
  const margin = ts / 64;
  // grid window covering the tile (sample its edges; mercator -> lon/lat -> ij)
  let i0 = Infinity, i1 = -Infinity, j0 = Infinity, j1 = -Infinity;
  for (let k = 0; k <= 16; k++) {
    for (const [mx, my] of [[tx0 + ts * k / 16, ty0], [tx0 + ts * k / 16, ty0 + ts], [tx0, ty0 + ts * k / 16], [tx0 + ts, ty0 + ts * k / 16]]) {
      const lon = (mx - 0.5) * 360, lat = Math.atan(Math.sinh(Math.PI * (1 - 2 * my))) / D2R;
      const [i, j] = grid.lonLatToIJ(lon, lat);
      if (i < i0) i0 = i; if (i > i1) i1 = i; if (j < j0) j0 = j; if (j > j1) j1 = j;
    }
  }
  const s = grid.step(z, spacingPx, allowCoarse);
  const pad = 2 * s + 0.1 / grid.k; // in this level's nodes; the same window at every pyramid level
  const PER = grid.period; // global: columns wrap, so the window may run past either end
  const ni0 = PER ? Math.ceil((i0 - pad) / s) : Math.max(0, Math.ceil((i0 - pad) / s));
  const ni1 = PER ? Math.floor((i1 + pad) / s) : Math.min(Math.floor((nx - 1) / s), Math.floor((i1 + pad) / s));
  const wrapCol = (c) => (PER ? ((c % PER) + PER) % PER : Math.min(nx - 1, Math.max(0, c)));
  const nj0 = Math.max(0, Math.ceil((j0 - pad) / s)), nj1 = Math.min(Math.floor((ny - 1) / s), Math.floor((j1 + pad) / s));
  const lw = ni1 - ni0 + 1, lh = nj1 - nj0 + 1;
  if (lw < 2 || lh < 2) return null;
  const np = lw * lh;

  // ---- field values on the lattice
  const val = new Float32Array(np);
  const A = fields[0], B = fields[1];
  const wa = B ? 1 - w : 1, wb = B ? w : 0;
  if (s >= 1) { // native grid values (s > 1: every s-th node, animation only)
    for (let r = 0; r < lh; r++) {
      const row = (nj0 + r) * s * nx;
      for (let c = 0; c < lw; c++) {
        const g = row + wrapCol((ni0 + c) * s);
        val[r * lw + c] = (B ? A[g] * wa + B[g] * wb : A[g]) / scale;
      }
    }
  } else {
    // separable bicubic: weights per lattice column/row, clamped at the edges
    const cw = new Float64Array(lw * 4), cb = new Int32Array(lw);
    for (let c = 0; c < lw; c++) { const u = (ni0 + c) * s, b = Math.floor(u); cb[c] = b; keys(u - b, cw, c * 4); }
    const rw = new Float64Array(lh * 4), rb = new Int32Array(lh);
    for (let r = 0; r < lh; r++) { const u = (nj0 + r) * s, b = Math.floor(u); rb[r] = b; keys(u - b, rw, r * 4); }
    const gr0 = Math.max(0, rb[0] - 1), gr1 = Math.min(ny - 1, rb[lh - 1] + 2);
    const hr = new Float64Array((gr1 - gr0 + 1) * lw); // rows interpolated horizontally
    for (let g = gr0; g <= gr1; g++) {
      const row = g * nx, o = (g - gr0) * lw;
      for (let c = 0; c < lw; c++) {
        let acc = 0; const b = cb[c], k = c * 4;
        for (let t = 0; t < 4; t++) {
          const gi = row + wrapCol(b - 1 + t);
          acc += cw[k + t] * (B ? A[gi] * wa + B[gi] * wb : A[gi]);
        }
        hr[o + c] = acc;
      }
    }
    for (let r = 0; r < lh; r++) {
      const b = rb[r], k = r * 4;
      for (let c = 0; c < lw; c++) {
        let acc = 0;
        for (let t = 0; t < 4; t++) {
          const jj = Math.min(gr1, Math.max(gr0, b - 1 + t));
          acc += rw[k + t] * hr[(jj - gr0) * lw + c];
        }
        val[r * lw + c] = acc / scale;
      }
    }
  }

  // ---- lattice positions (tile-local 0..1) and bands
  const P = new Buf(Float32Array, np * 2 + 4096), Bd = new Buf(Int16Array, np + 2048);
  const px = P.a, bd = Bd.a;
  const gp = grid.pos, gx = grid.px, gy = grid.py, ox = grid.ox - tx0, oy = grid.oy - ty0;
  for (let r = 0; r < lh; r++) {
    const vj = (nj0 + r) * s, j = Math.min(ny - 2, Math.floor(vj)), fj = vj - j;
    for (let c = 0; c < lw; c++) {
      let ui = (ni0 + c) * s, shift = 0;
      if (PER) { shift = Math.floor(ui / PER); ui -= shift * PER; } // world copy: +1 mercator width per period
      const i = Math.min(nx - 2, Math.floor(ui)), fi = ui - i;
      let mx, my;
      if (gx) { // lat/lon: separable, linear along each axis (exact at nodes)
        mx = gx[i] * (1 - fi) + gx[i + 1] * fi; my = gy[j] * (1 - fj) + gy[j + 1] * fj;
      } else { // bilinear between the four surrounding nodes (exact at nodes)
        const g00 = (j * nx + i) * 2, g10 = g00 + 2, g01 = g00 + nx * 2, g11 = g01 + 2;
        mx = (gp[g00] * (1 - fi) + gp[g10] * fi) * (1 - fj) + (gp[g01] * (1 - fi) + gp[g11] * fi) * fj;
        my = (gp[g00 + 1] * (1 - fi) + gp[g10 + 1] * fi) * (1 - fj) + (gp[g01 + 1] * (1 - fi) + gp[g11 + 1] * fi) * fj;
      }
      const p = r * lw + c;
      px[p * 2] = (mx + ox + shift) * tz; px[p * 2 + 1] = (my + oy) * tz;
      bd[p] = Math.floor(val[p]);
    }
  }
  P.n = np * 2; Bd.n = np;

  // ---- triangles
  const I = new Buf(Uint32Array, np * 6);
  const lo = -margin * tz, hi = 1 + margin * tz;
  const poly = new Int32Array(16);

  // boundary point of `level` on edge (a, b), computed canonically (lower index first)
  function cross(a, b, level) {
    if (a > b) { const t = a; a = b; b = t; }
    const t = (level - val[a]) / (val[b] - val[a]);
    P.grow(2); Bd.grow(1);
    const pa = P.a, k = P.n;
    pa[k] = pa[a * 2] + t * (pa[b * 2] - pa[a * 2]);
    pa[k + 1] = pa[a * 2 + 1] + t * (pa[b * 2 + 1] - pa[a * 2 + 1]);
    P.n += 2; Bd.a[Bd.n] = level;
    return Bd.n++;
  }

  function slice(a, b, c) {
    const ba = Bd.a[a], bb = Bd.a[b], bc = Bd.a[c];
    const kmin = Math.min(ba, bb, bc), kmax = Math.max(ba, bb, bc);
    const tri = [a, b, c];
    for (let k = kmin; k <= kmax; k++) {
      let m = 0, pivot = -1;
      for (let e = 0; e < 3; e++) {
        const p = tri[e], q = tri[(e + 1) % 3];
        const vp = val[p], vq = val[q];
        if (Bd.a[p] === k) { if (pivot < 0) pivot = m; poly[m++] = p; }
        if (vp === vq) continue;
        // crossings of levels k and k+1 on p->q, in order from p to q
        const up = vp < vq;
        for (let s2 = 0; s2 < 2; s2++) {
          const L = up ? k + s2 : k + 1 - s2; // in order from p to q
          const inside = up ? (vp < L && L <= vq) : (vq < L && L <= vp);
          if (inside) { const v = cross(p, q, L); if (L === k && pivot < 0) pivot = m; poly[m++] = v; }
        }
      }
      if (m < 3 || pivot < 0) continue;
      // fan around the pivot; the pivot goes last so it is the provoking vertex
      I.grow((m - 2) * 3);
      const ia = I.a;
      for (let t = 1; t < m - 1; t++) {
        ia[I.n++] = poly[(pivot + t) % m]; ia[I.n++] = poly[(pivot + t + 1) % m]; ia[I.n++] = poly[pivot];
      }
    }
  }

  // Merge cells that lie entirely inside one band with a quadtree.  A merged
  // block is emitted as a fan over *all* lattice points on its perimeter, so it
  // shares every edge vertex with its finer neighbours: no T-junction cracks.
  const cw_ = lw - 1, ch_ = lh - 1;
  const NONE = -32768;
  const levels = [new Int16Array(cw_ * ch_)];
  const dims = [[cw_, ch_]];
  const inTile = new Uint8Array(cw_ * ch_);
  for (let r = 0; r < ch_; r++) {
    for (let c = 0; c < cw_; c++) {
      const p00 = r * lw + c, p10 = p00 + 1, p01 = p00 + lw, p11 = p01 + 1, q = r * cw_ + c;
      const x0 = px[p00 * 2], x1 = px[p10 * 2], x2 = px[p01 * 2], x3 = px[p11 * 2];
      const y0_ = px[p00 * 2 + 1], y1_ = px[p10 * 2 + 1], y2_ = px[p01 * 2 + 1], y3_ = px[p11 * 2 + 1];
      inTile[q] = !(Math.max(x0, x1, x2, x3) < lo || Math.min(x0, x1, x2, x3) > hi ||
                    Math.max(y0_, y1_, y2_, y3_) < lo || Math.min(y0_, y1_, y2_, y3_) > hi);
      const b0 = bd[p00];
      levels[0][q] = (bd[p10] === b0 && bd[p01] === b0 && bd[p11] === b0) ? b0 : NONE;
    }
  }
  const OUT = -32767; // block entirely outside the tile
  for (let q = 0; q < cw_ * ch_; q++) if (!inTile[q]) levels[0][q] = levels[0][q] === NONE ? NONE : levels[0][q];
  const MAXK = 7;
  for (let k = 1; k <= MAXK; k++) {
    const [pw, ph] = dims[k - 1], w2 = Math.ceil(pw / 2), h2 = Math.ceil(ph / 2);
    const prev = levels[k - 1], cur = new Int16Array(w2 * h2);
    for (let r = 0; r < h2; r++) {
      for (let c = 0; c < w2; c++) {
        let v = null;
        for (let dr = 0; dr < 2 && v !== NONE; dr++) {
          for (let dc = 0; dc < 2; dc++) {
            const rr = 2 * r + dr, cc = 2 * c + dc;
            if (rr >= ph || cc >= pw) continue;
            const b = prev[rr * pw + cc];
            if (b === NONE || (v !== null && b !== v)) { v = NONE; break; }
            v = b;
          }
        }
        cur[r * w2 + c] = v;
      }
    }
    levels.push(cur); dims.push([w2, h2]);
  }

  function emitBlock(c0, r0, c1, r1) {
    // perimeter lattice points, counter-clockwise in lattice space
    const n = 2 * (c1 - c0) + 2 * (r1 - r0);
    I.grow((n - 2) * 3);
    const ia = I.a, first = r0 * lw + c0;
    let prevPt = -1;
    const put = (pt) => {
      if (prevPt >= 0 && prevPt !== first) { ia[I.n++] = first; ia[I.n++] = prevPt; ia[I.n++] = pt; }
      prevPt = pt;
    };
    for (let c = c0; c <= c1; c++) put(r0 * lw + c);
    for (let r = r0 + 1; r <= r1; r++) put(r * lw + c1);
    for (let c = c1 - 1; c >= c0; c--) put(r1 * lw + c);
    for (let r = r1 - 1; r > r0; r--) put(r * lw + c0);
  }

  function cellTouchesTile(c0, r0, c1, r1) {
    for (let r = r0; r < r1; r++) for (let c = c0; c < c1; c++) if (inTile[r * cw_ + c]) return true;
    return false;
  }

  function visit(k, bc, br) {
    const size = 1 << k;
    const c0 = bc * size, r0 = br * size;
    if (c0 >= cw_ || r0 >= ch_) return;
    const c1 = Math.min(cw_, c0 + size), r1 = Math.min(ch_, r0 + size);
    const band = levels[k][br * dims[k][0] + bc];
    if (band !== NONE) {
      if (k === 0 ? inTile[r0 * cw_ + c0] : cellTouchesTile(c0, r0, c1, r1)) emitBlock(c0, r0, c1, r1);
      return;
    }
    if (k === 0) {
      if (!inTile[r0 * cw_ + c0]) return;
      const p00 = r0 * lw + c0, p10 = p00 + 1, p01 = p00 + lw, p11 = p01 + 1;
      slice(p00, p10, p11);
      slice(p00, p11, p01);
      return;
    }
    for (let dr = 0; dr < 2; dr++) for (let dc = 0; dc < 2; dc++) visit(k - 1, bc * 2 + dc, br * 2 + dr);
  }
  const [tw, th] = dims[MAXK];
  for (let br = 0; br < th; br++) for (let bc = 0; bc < tw; bc++) visit(MAXK, bc, br);
  return { pos: P.out(), band: Bd.out(), index: I.out(), lattice: [lw, lh], step: s };
}

// value at lon/lat (bicubic, same kernel as the contours), for the readout
export function sample(grid, fields, w, lon, lat) {
  const [u, v] = grid.lonLatToIJ(lon, lat);
  const { nx, ny } = grid;
  if (u < 0 || v < 0 || u > nx - 1 || v > ny - 1) return null;
  const A = fields[0], B = fields[1];
  const bi = Math.floor(u), bj = Math.floor(v), wx = new Float64Array(4), wy = new Float64Array(4);
  keys(u - bi, wx, 0); keys(v - bj, wy, 0);
  let acc = 0;
  for (let r = 0; r < 4; r++) {
    const jj = Math.min(ny - 1, Math.max(0, bj - 1 + r));
    for (let c = 0; c < 4; c++) {
      const g = jj * nx + Math.min(nx - 1, Math.max(0, bi - 1 + c));
      acc += wy[r] * wx[c] * (B ? A[g] * (1 - w) + B[g] * w : A[g]);
    }
  }
  return acc / grid.meta.scale;
}

// Pyramid level k of a published grid: every k-th node (published as fHH-k.i16.gz
// for the k in meta.levels).  Contouring with a lattice step of s >= k nodes
// reads only these nodes, so the result is identical to using the full grid.
export function levelMeta(meta, k) {
  if (k === 1) return meta;
  return { ...meta, levelK: k, nx: (meta.nx - 1) / k + 1, ny: (meta.ny - 1) / k + 1, dx: meta.dx * k };
}
