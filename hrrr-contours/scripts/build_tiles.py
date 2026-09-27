#!/usr/bin/env python3
"""Build vector tiles of 1-degree filled temperature contours from an HRRR GRIB2 field.

Pipeline (per tile, per zoom):

  1. Take the model grid itself (the raw values, no interpolation) in a window
     around the tile, with a margin of 4 cells.
  2. contourpy computes, for every integer degree t, the superlevel polygon
     {T >= t} (layer "levels", plus the data footprint in "base").  Painted in
     ascending t, these stack into 1-degree bands that cannot have gaps, and
     their outlines are the isotherms.  A lightly simplified copy of the
     isolines (layer "labels") is used only for text placement.
  3. Storm's smoothing (mmase/storm, maps/gui/smooth.js): every ring is replaced
     by the uniform cubic B-spline through its vertices, sampled every ~1.5 px.
     Points on the window border are kept exactly (rings close along it), and
     that border is outside the buffered tile, so neighbouring tiles match.
     The browser does the same for zooms above the tiles.
  4. Reproject LCC -> Web Mercator, clip to the buffered tile, quantise to a
     8192 extent and encode Mapbox Vector Tile protobuf directly (no
     simplification of fills, no feature dropping -- every contour at every zoom).

Tiles are gzipped and grouped into a small number of "pack" files so the result
can be served from any static host (no range requests, few files).
"""
import os

# One BLAS/OpenMP thread per worker: parallelism comes from the process pool,
# and letting each worker also spawn a thread per core oversubscribes the CPU
# (measured: 5.5 min -> 2.3 min on 4 cores).  Must be set before numpy loads.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import gzip
import json
import math
import struct
import sys
import time
from multiprocessing import Pool

import contourpy
import eccodes as ec
import numpy as np
import shapely
from pyproj import Transformer

EXTENT = 8192
BUFFER = 96  # tile units of overlap beyond the tile edge
MINZOOM, MAXZOOM = 2, 9
LEVEL_EPS = 1e-4  # contour levels sit this far below each integer (see build_tile)
TOPZOOM = 9  # the zoom MapLibre overzooms to z13 when tiles are the only renderer
LABEL_ALL_ZOOM = 7  # from this zoom every 1-degree isoline gets a label line
LABEL_LEVELS = None  # optional set of band levels to label (overrides the rule above)
LABEL_TOLERANCE = 40  # tile units (~2.5 px) for the label-only line layer
# Fill simplification, in screen px at the tile's own zoom.  Levels are stacked
# (see below), so each polygon can be simplified independently without opening
# gaps; rings are never removed (topology-preserving), only thinned.  The top
# zoom is overzoomed up to 16x, so its tolerance is set in overzoomed px.
SIMPLIFY_PX = 0.3
SMOOTH_PX = 1.5  # storm smoothing: one point per this many screen px along each ring
ORIGIN = 20037508.342789244

# --------------------------------------------------------------------------- field


def load_field(path):
    with open(path, "rb") as f:
        g = ec.codes_grib_new_from_file(f)
        nx, ny = ec.codes_get(g, "Nx"), ec.codes_get(g, "Ny")
        assert ec.codes_get(g, "jScansPositively") == 1 and ec.codes_get(g, "iScansNegatively") == 0
        proj = ec.codes_get(g, "projString")
        lat0 = ec.codes_get(g, "latitudeOfFirstGridPointInDegrees")
        lon0 = ec.codes_get(g, "longitudeOfFirstGridPointInDegrees")
        dx = ec.codes_get(g, "DxInMetres")
        k = ec.codes_get_values(g).reshape(ny, nx)
        ec.codes_release(g)
    tf = (k - 273.15) * 9.0 / 5.0 + 32.0  # Fahrenheit
    ll2lcc = Transformer.from_crs("+proj=longlat +R=6371229 +no_defs", proj, always_xy=True)
    x0, y0 = ll2lcc.transform(lon0 - 360 if lon0 > 180 else lon0, lat0)
    return tf.astype(np.float64), proj, x0, y0, dx


class WebMercator:
    """LCC <-> spherical Web Mercator (EPSG:3857 maths; lat/lon taken as-is,
    the usual convention for NWP grids on a sphere). Avoids needing the PROJ DB."""

    R = 6378137.0

    def __init__(self, proj, inverse):
        self.inverse = inverse
        self.ll = Transformer.from_crs("+proj=longlat +R=6371229 +no_defs", proj, always_xy=True)

    def transform(self, x, y):
        x, y = np.asarray(x, dtype=np.float64), np.asarray(y, dtype=np.float64)
        if self.inverse:  # mercator -> lcc
            lon = np.degrees(x / self.R)
            lat = np.degrees(2 * np.arctan(np.exp(y / self.R)) - np.pi / 2)
            return self.ll.transform(lon, lat)
        lon, lat = self.ll.transform(x, y, direction="INVERSE")
        lon = np.asarray(lon)
        return (np.radians(lon) * self.R,
                self.R * np.log(np.tan(np.pi / 4 + np.radians(np.asarray(lat)) / 2)))


def cubic_weights(u, n):
    """Uniform cubic B-spline weights for sample positions u (in cells).

    Returns (W, first) where W[k, :] are weights over padded-grid columns
    first..first+W.shape[1]-1 (the grid is padded by 2 on each side).
    """
    base = np.floor(u).astype(np.int64)
    t = u - base
    v = 1 - t
    w = np.stack([v**3, 3 * t**3 - 6 * t**2 + 4, -3 * t**3 + 3 * t**2 + 3 * t + 1, t**3], axis=1) / 6
    first = base.min() - 1
    width = base.max() + 3 - first
    W = np.zeros((len(u), width))
    rows = np.arange(len(u))[:, None]
    cols = (base - 1 - first)[:, None] + np.arange(4)[None, :]
    W[rows, cols] = w
    return W, first + 2  # +2 for padding offset


def load_grid(path):
    """A grid published by publish_grids.py: row-delta int16 (tenths of degF),
    gzipped, with meta.json alongside.  Same numbers the browser contours."""
    meta = json.load(open(os.path.join(os.path.dirname(path), "meta.json")))
    d = np.frombuffer(gzip.decompress(open(path, "rb").read()), dtype="<i2").reshape(meta["ny"], meta["nx"])
    q = np.cumsum(d, axis=1, dtype=np.int16)  # undo row deltas (wrapping int16 arithmetic)
    p = meta["proj"]
    if p["type"] == "latlon":  # x0/y0/dx in degrees; "projected" coords are lon/lat
        proj = f"+proj=longlat +R={p['R']} +no_defs"
        Field.cell_m = meta["dx"] * 111320 * math.cos(math.radians(p["lat0"]))
    else:
        proj = (f"+proj=lcc +lon_0={p['lon0']} +lat_0={p['lat0']} +lat_1={p['lat1']} +lat_2={p['lat2']} "
                f"+R={p['R']}")
        Field.cell_m = meta["dx"]
    Field.wrap = bool(meta.get("global"))
    return q.astype(np.float64) / meta["scale"], proj, meta["x0"], meta["y0"], meta["dx"]


class Field:
    def __init__(self, path):
        load = load_field if path.endswith(".grib2") else load_grid
        self.F, self.proj, self.x0, self.y0, self.dx = load(path)
        self.ny, self.nx = self.F.shape
        self.Fp = np.pad(self.F, 2, mode="edge")
        if self.wrap:  # global: the last column repeats the first, so neighbours wrap across it
            self.Fp[:, :2] = np.pad(self.F[:, -3:-1], ((2, 2), (0, 0)), mode="edge")
            self.Fp[:, -2:] = np.pad(self.F[:, 1:3], ((2, 2), (0, 0)), mode="edge")
        self.to_merc = WebMercator(self.proj, inverse=False)
        self.to_lcc = WebMercator(self.proj, inverse=True)

    cell_m = 3000.0  # nominal grid cell size in metres (set per source)
    wrap = False     # global grid (columns wrap; set per source)

    def spacing(self, z):
        # the raw grid at every zoom: contours are traced on the model's own
        # nodes and smoothed as curves afterwards (storm's algorithm)
        return 1.0

    def lattice(self, z, i0, i1, j0, j1):
        """Field values on the global lattice restricted to grid-index box."""
        s = self.spacing(z)
        ni = np.arange(max(0, math.ceil(i0 / s)), min(math.floor((self.nx - 1) / s), math.floor(i1 / s)) + 1)
        nj = np.arange(max(0, math.ceil(j0 / s)), min(math.floor((self.ny - 1) / s), math.floor(j1 / s)) + 1)
        if len(ni) < 2 or len(nj) < 2:
            return None
        ui, uj = ni * s, nj * s
        if s < 1:
            Wx, fx = cubic_weights(ui, self.nx)
            Wy, fy = cubic_weights(uj, self.ny)
            sub = self.Fp[fy:fy + Wy.shape[1], fx:fx + Wx.shape[1]]
            Z = Wy @ sub @ Wx.T
        else:  # coarser than the grid (not used by the tiler's spacing rule)
            Z = self.F[np.ix_(nj, ni)]
        X = self.x0 + ui * self.dx
        Y = self.y0 + uj * self.dx
        return X, Y, Z


# --------------------------------------------------------------------------- MVT encoding


def varint_bytes(vals):
    """Vectorised protobuf varint encoding of a non-negative int array."""
    v = np.asarray(vals, dtype=np.uint64)
    if v.size == 0:
        return b""
    nb = np.ones(v.shape, dtype=np.int64)
    for k in range(1, 10):
        nb += v >= (np.uint64(1) << np.uint64(7 * k))
    total = int(nb.sum())
    out = np.empty(total, dtype=np.uint8)
    starts = np.concatenate([[0], np.cumsum(nb)[:-1]])
    for k in range(int(nb.max())):
        m = nb > k
        byte = (v[m] >> np.uint64(7 * k)) & np.uint64(0x7F)
        byte = byte | np.where(nb[m] - 1 > k, np.uint64(0x80), np.uint64(0))
        out[starts[m] + k] = byte.astype(np.uint8)
    return out.tobytes()


def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def field_bytes(num, wt, payload):
    return varint((num << 3) | wt) + (varint(len(payload)) + payload if wt == 2 else payload)


def zigzag(a):
    a = a.astype(np.int64)
    return ((a << 1) ^ (a >> 63)).astype(np.uint64)


def encode_layer(name, features, extent=EXTENT):
    """features: list of (t_value, geom_type, packed_geometry_bytes)."""
    values = sorted({f[0] for f in features})
    vindex = {v: i for i, v in enumerate(values)}
    body = field_bytes(15, 0, varint(2))
    body += field_bytes(1, 2, name.encode())
    for t, gtype, geom in features:
        fb = field_bytes(2, 2, varint_bytes([0, vindex[t]]))
        fb += field_bytes(3, 0, varint(gtype))
        fb += field_bytes(4, 2, geom)
        body += field_bytes(2, 2, fb)
    body += field_bytes(3, 2, b"t")
    for v in values:
        body += field_bytes(4, 2, field_bytes(6, 0, varint(int(zigzag(np.array([v]))[0]))))
    body += field_bytes(5, 0, varint(extent))
    return field_bytes(3, 2, body)


# --------------------------------------------------------------------------- tile building


def encode_rings(coords, ring_off, groups, polygon):
    """Vectorised MVT geometry encoding for many features at once.

    coords: (n, 2) float tile coordinates; ring_off: ring start offsets into
    coords (len nrings + 1); groups: ring offsets per output feature
    (len nfeatures + 1).  Polygons additionally need the exterior flag per ring
    (passed via polygon=(is_exterior array)).  Rings are quantised, closing and
    consecutive duplicate points dropped, degenerate rings removed (a polygon
    whose exterior degenerates is removed with its holes), orientation fixed to
    the MVT winding rule, then encoded with commands and zigzag deltas.
    Returns a list of packed-geometry bytes (b"" for empty features).
    """
    q = np.round(coords).astype(np.int64)
    nring = len(ring_off) - 1
    counts = np.diff(ring_off)
    rid = np.repeat(np.arange(nring), counts)
    keep = np.ones(len(q), dtype=bool)
    if polygon is not None:
        keep[ring_off[1:][counts > 0] - 1] = False  # closing point
    same = np.zeros(len(q), dtype=bool)
    same[1:] = (rid[1:] == rid[:-1]) & np.all(q[1:] == q[:-1], axis=1)
    keep &= ~same
    idx = np.nonzero(keep)[0]
    rid_k = rid[idx]
    n = np.bincount(rid_k, minlength=nring)
    start = np.concatenate([[0], np.cumsum(n)[:-1]])
    pts = q[idx]
    if polygon is not None:
        # quantisation can make the last kept point equal the first
        last = start + n - 1
        dup = (n > 1) & np.all(pts[np.maximum(last, 0)] == pts[start], axis=1)
        drop = np.zeros(len(pts), dtype=bool)
        drop[last[dup]] = True
        pts, rid_k = pts[~drop], rid_k[~drop]
        n = np.bincount(rid_k, minlength=nring)
        start = np.concatenate([[0], np.cumsum(n)[:-1]])
        # signed area (x2) per ring
        nxt = np.arange(len(pts)) + 1
        ends = start + n
        nxt[ends[n > 0] - 1] = start[n > 0]
        cross = pts[:, 0] * pts[nxt, 1] - pts[nxt, 0] * pts[:, 1]
        area = np.bincount(rid_k, weights=cross, minlength=nring)
        is_ext = polygon
        valid = (n >= 3) & (area != 0)
        # a hole survives only if its polygon's exterior does
        poly_id = np.cumsum(is_ext) - 1
        ext_ok = valid[is_ext]
        valid &= ext_ok[poly_id]
        rev = valid & (is_ext != (area > 0))
    else:
        valid = n >= 2
        rev = np.zeros(nring, dtype=bool)
    # final point order per kept ring (reversed where needed)
    kept = valid[rid_k]
    pos = np.arange(len(pts)) - start[rid_k]
    newpos = np.where(rev[rid_k], n[rid_k] - 1 - pos, pos)
    order = (start[rid_k] + newpos)[kept]
    pts, rid_k = pts[order], rid_k[kept]
    n = np.where(valid, n, 0)
    # feature id per ring / point; deltas restart at 0 for each feature
    feat_of_ring = np.repeat(np.arange(len(groups) - 1), np.diff(groups))
    fid = feat_of_ring[rid_k]
    d = np.diff(pts, axis=0, prepend=[[0, 0]])
    first_of_feat = np.ones(len(pts), dtype=bool)
    first_of_feat[1:] = fid[1:] != fid[:-1]
    d[first_of_feat] = pts[first_of_feat]
    zz = ((d << 1) ^ (d >> 63)).astype(np.uint64)
    # command stream: MoveTo(1) x y LineTo(n-1) ... [ClosePath]
    extra = 3 if polygon is not None else 2
    per = np.where(n > 0, 2 * n + extra, 0)
    rs = np.concatenate([[0], np.cumsum(per)[:-1]])
    out = np.empty(int(per.sum()), dtype=np.uint64)
    live = n > 0
    out[rs[live]] = 9
    out[rs[live] + 3] = 2 | ((n[live] - 1) << 3)
    if polygon is not None:
        out[rs[live] + per[live] - 1] = 15
    p = np.arange(len(pts)) - np.concatenate([[0], np.cumsum(n)[:-1]])[rid_k]
    base = rs[rid_k] + np.where(p == 0, 1, 2 + 2 * p)
    out[base] = zz[:, 0]
    out[base + 1] = zz[:, 1]
    # varint-encode once, then slice per feature
    nb = np.ones(len(out), dtype=np.int64)
    for k in range(1, 10):
        nb += out >= (np.uint64(1) << np.uint64(7 * k))
    blob = varint_bytes(out)
    ring_bytes = np.bincount(np.repeat(np.arange(nring), per), weights=nb[:], minlength=nring) if len(out) else np.zeros(nring)
    fb = np.concatenate([[0], np.cumsum(np.bincount(feat_of_ring, weights=ring_bytes, minlength=len(groups) - 1))]).astype(np.int64)
    return [blob[fb[i]:fb[i + 1]] for i in range(len(groups) - 1)]


def simplify_rings(coords, ring_off, tol):
    """Douglas-Peucker each ring independently (vectorised in GEOS).

    Rings that would collapse (fewer than 4 coordinates) keep their original
    shape, so no feature is ever removed -- only redundant vertices are.
    """
    rings = shapely.from_ragged_array(shapely.GeometryType.LINESTRING, coords, (ring_off,))
    simp = shapely.simplify(rings, tol, preserve_topology=False)
    ok = shapely.get_num_coordinates(simp) >= 4
    simp = np.where(ok, simp, rings)
    _, c, (off,) = shapely.to_ragged_array(simp)
    return c, off


def bspline_weights(t):
    """Uniform cubic B-spline basis at t (storm's k0..k3), shape (len(t), 4)."""
    v = 1 - t
    return np.stack([v**3, 3 * t**3 - 6 * t**2 + 4, -3 * t**3 + 3 * t**2 + 3 * t + 1, t**3], axis=1) / 6


def smooth_rings(c, pin, offs, closed, delta):
    """Storm's ring smoothing, vectorised over every ring of a tile.

    c: (N, 2) points; ring k is c[offs[k]:offs[k+1]] (a closed ring repeats its
    first point at the end).  For each segment p1 -> p2 the uniform cubic B-spline
    of p0..p3 is sampled every `delta`.  Pinned points (window border; ends of open
    lines) are kept exactly: segments touching them stay straight, and a spline
    next to one uses a mirrored phantom point so it starts/ends on it.  Rings under
    4 points are kept as they are.  Returns (points, offsets).
    """
    offs = np.asarray(offs, np.int64)
    lens = np.diff(offs)
    m = np.where(closed, lens - 1, lens)                  # distinct points per ring
    tot = int(m.sum())
    if tot == 0:
        return c, offs
    ring = np.repeat(np.arange(len(m)), m)
    local = np.arange(tot) - np.repeat(np.cumsum(m) - m, m)
    mm, st, cl = m[ring], offs[:-1][ring], closed[ring]
    pinx = pin.copy()
    op = ~closed & (m > 0)
    pinx[offs[:-1][op]] = True                              # open lines: both ends fixed
    pinx[(offs[:-1] + m - 1)[op]] = True

    def nb(d):
        l_ = local + d
        return st + np.where(cl, l_ % np.maximum(mm, 1), np.clip(l_, 0, mm - 1))
    i1, i0, i2, i3 = st + local, nb(-1), nb(1), nb(2)
    p0, p1, p2, p3 = c[i0], c[i1], c[i2], c[i3]
    linear = pinx[i1] | pinx[i2] | (m[ring] < 4) | (~cl & (local == mm - 1))
    p0 = np.where(pinx[i0][:, None], 2 * p1 - p2, p0)
    p3 = np.where(pinx[i3][:, None], 2 * p2 - p1, p3)
    n = np.where(linear, 1, np.maximum(1, np.ceil(np.hypot(*(p2 - p1).T) / delta))).astype(np.int64)
    rep = np.repeat(np.arange(tot), n)
    t = (np.arange(int(n.sum())) - np.repeat(np.cumsum(n) - n, n)) / n[rep]
    W = bspline_weights(t)
    out = (W[:, :1] * p0[rep] + W[:, 1:2] * p1[rep] + W[:, 2:3] * p2[rep] + W[:, 3:] * p3[rep])
    out = np.where(linear[rep][:, None], p1[rep], out)
    # per-ring counts; closed rings repeat their first point
    cnt = np.bincount(ring[rep], minlength=len(m))
    first = np.concatenate([[0], np.cumsum(cnt)[:-1]])
    new_cnt = cnt + closed.astype(np.int64)
    new_offs = np.concatenate([[0], np.cumsum(new_cnt)])
    res = np.empty((int(new_offs[-1]), 2))
    dest = np.arange(len(out)) + np.repeat(new_offs[:-1] - first, cnt)
    res[dest] = out
    cr = np.nonzero(closed & (cnt > 0))[0]
    res[new_offs[1:][cr] - 1] = out[first[cr]]
    return res, new_offs


def drop_short_rings(offs, outer):
    """Remove rings with < 4 points (a polygon whose exterior is short goes too)."""
    n = np.diff(offs)
    if (n >= 4).all():
        return offs, outer  # common case: nothing to drop
    keep_poly = n[outer[:-1]] >= 4
    ring_poly = np.repeat(np.arange(len(outer) - 1), np.diff(outer))
    keep = (n >= 4) & keep_poly[ring_poly]
    # rebuild offsets into the original points array via index gathering
    idx = np.concatenate([np.arange(offs[r], offs[r + 1]) for r in np.nonzero(keep)[0]]) if keep.any() else np.zeros(0, int)
    new_offs = np.concatenate([[0], np.cumsum(n[keep])])
    new_outer = np.concatenate([[0], np.cumsum(np.bincount(ring_poly[keep], minlength=len(outer) - 1)[keep_poly])])
    return (new_offs, new_outer, idx)


def ragged(geoms, kind):
    """Array of (Multi)Polygons or (Multi)LineStrings -> coords, ring offsets,
    per-geometry ring offsets and (polygons) the exterior flag per ring."""
    single = shapely.GeometryType.POLYGON if kind == "polygon" else shapely.GeometryType.LINESTRING
    multi = shapely.MultiPolygon if kind == "polygon" else shapely.MultiLineString
    norm = []
    for g in geoms:
        if g is None or g.is_empty:
            norm.append(multi())
            continue
        parts = shapely.get_parts(g)
        parts = parts[shapely.get_type_id(parts) == single]
        norm.append(multi(list(parts)) if len(parts) else multi())
    if all(g.is_empty for g in norm):
        return None
    _, coords, offs = shapely.to_ragged_array(norm)
    if kind == "polygon":
        ring_off, poly_off, geom_off = offs
        is_ext = np.zeros(len(ring_off) - 1, dtype=bool)
        is_ext[poly_off[:-1][np.diff(poly_off) > 0]] = True
        return coords, ring_off, poly_off[geom_off], is_ext
    line_off, geom_off = offs
    return coords, line_off, geom_off, None


FIELD = None


MIN_BAND = None  # bands below this are transparent: not emitted, and empty tiles skipped


def init_worker(path, label_levels=None, min_band=None):
    global FIELD, LABEL_LEVELS, MIN_BAND
    FIELD = Field(path)
    LABEL_LEVELS = label_levels
    MIN_BAND = min_band


def tile_bounds(z, x, y):
    size = 2 * ORIGIN / 2**z
    minx = -ORIGIN + x * size
    maxy = ORIGIN - y * size
    return minx, maxy, size


def build_tile(zxy):
    z, x, y = zxy
    fld = FIELD
    minx, maxy, size = tile_bounds(z, x, y)
    b = BUFFER / EXTENT * size
    # window in grid-index space covering the buffered tile
    e = np.linspace(0, 1, 17)
    bx = np.concatenate([e, np.ones(17), e[::-1], np.zeros(17)]) * (size + 2 * b) + minx - b
    by = maxy + b - np.concatenate([np.zeros(17), e, np.ones(17), e[::-1]]) * (size + 2 * b)
    lx, ly = fld.to_lcc.transform(bx, by)
    gi, gj = (np.array(lx) - fld.x0) / fld.dx, (np.array(ly) - fld.y0) / fld.dx
    s = fld.spacing(z)
    pad = 4 * s  # the smoothing near the (fixed) window border stays outside the tile
    if MIN_BAND is not None:
        # nothing visible here? (checked on the raw grid, with room for bicubic overshoot)
        r0, r1 = max(0, int(gj.min() - 3)), min(fld.ny, int(gj.max() + 4))
        c0, c1 = max(0, int(gi.min() - 3)), min(fld.nx, int(gi.max() + 4))
        if r1 <= r0 or c1 <= c0 or fld.F[r0:r1, c0:c1].max() < MIN_BAND - 0.5:
            return zxy, None
    lat = fld.lattice(z, gi.min() - pad, gi.max() + pad, gj.min() - pad, gj.max() + pad)
    if lat is None:
        return zxy, None
    X, Y, Z = lat
    gen = contourpy.contour_generator(X, Y, Z, fill_type="ChunkCombinedOffsetOffset",
                                      line_type="ChunkCombinedOffset")
    scale = EXTENT / size
    lo, hi = int(math.floor(Z.min())), int(math.floor(Z.max()))
    top = float(Z.max()) + 1.0

    # Superlevel set {T >= t} for every integer t.  Painted in ascending t the
    # visible colour of any point is floor(T), and the ring boundaries are
    # exactly the t-degree isolines (each isoline is stored once).  The t == lo
    # polygon is the data footprint, so the stack covers the domain with no gaps.
    fills, lines = [], []
    if MIN_BAND is not None:
        if hi < MIN_BAND:
            return zxy, None
        lo = max(lo, MIN_BAND)
    for t in range(lo, hi + 1):
        # Contour just below t: identical membership for data stored in 0.1-degree
        # steps, but no sample sits exactly on a level (which makes 0-area rings).
        pts, offs, outer = (c[0] for c in gen.filled(t - LEVEL_EPS, top))
        if pts is not None:
            fills.append((t, pts, offs, outer))
        # Isolines for text placement only (every 5 deg at low zoom).
        if t > lo and (t in LABEL_LEVELS if LABEL_LEVELS is not None else (t % 5 == 0 or z >= LABEL_ALL_ZOOM)):
            lp, lo_ = (c[0] for c in gen.lines(t - LEVEL_EPS))
            if lp is not None:
                lines.append((t, lp, lo_))
    if not fills:
        return zxy, None

    # one reprojection call for every vertex in the tile
    allpts = np.concatenate([f[1] for f in fills] + [l[1] for l in lines])
    mx, my = fld.to_merc.transform(allpts[:, 0], allpts[:, 1])
    tp = np.column_stack([(mx - minx) * scale, (maxy - my) * scale])
    # vertices on the lattice window border stay fixed when smoothing
    tol = 1e-6 * fld.dx
    onb = ((np.abs(allpts[:, 0] - X[0]) < tol) | (np.abs(allpts[:, 0] - X[-1]) < tol) |
           (np.abs(allpts[:, 1] - Y[0]) < tol) | (np.abs(allpts[:, 1] - Y[-1]) < tol))
    px = EXTENT / 512 / (16 if z == TOPZOOM else 1)
    delta = SMOOTH_PX * px
    k = 0
    polys, mls = [], []
    for t, pts, offs, outer in fills:
        c, pn = tp[k:k + len(pts)], onb[k:k + len(pts)]; k += len(pts)
        r = drop_short_rings(offs, outer)
        if len(r) == 3:
            offs, outer, idx = r
            c, pn = c[idx], pn[idx]
        if len(outer) < 2:
            continue
        c, offs = smooth_rings(c, pn, offs, np.ones(len(offs) - 1, bool), delta)
        polys.append(shapely.from_ragged_array(
            shapely.GeometryType.MULTIPOLYGON, c, (offs, outer, np.array([0, len(outer) - 1])))[0])
    for t, lp, lo_ in lines:
        c, pn = tp[k:k + len(lp)], onb[k:k + len(lp)]; k += len(lp)
        first, last = lo_[:-1], lo_[1:] - 1
        closed = np.all(c[first] == c[last], axis=1)
        c, lo_ = smooth_rings(c, pn, lo_, closed, delta)
        mls.append(shapely.from_ragged_array(
            shapely.GeometryType.MULTILINESTRING, c, (lo_, np.array([0, len(lo_) - 1])))[0])

    rect = (-BUFFER, -BUFFER, EXTENT + BUFFER, EXTENT + BUFFER)
    tol = max(0.5, SIMPLIFY_PX * px)
    r = ragged(shapely.clip_by_rect(np.array(polys), *rect), "polygon")
    if r is None:
        return zxy, None
    coords, ring_off = simplify_rings(r[0], r[1], tol)
    geoms = encode_rings(coords, ring_off, r[2], r[3])
    levels = [(f[0], 3, g) for f, g in zip(fills, geoms) if g]
    labels = []
    if mls:
        mls = shapely.simplify(shapely.clip_by_rect(np.array(mls), *rect), LABEL_TOLERANCE)
        r = ragged(mls, "line")
        if r is not None:
            geoms = encode_rings(r[0], r[1], r[2], None)
            labels = [(l[0], 2, g) for l, g in zip(lines, geoms) if g]
    if not levels:
        return zxy, None
    pbf = encode_layer("base", levels[:1])
    if len(levels) > 1:
        pbf += encode_layer("levels", levels[1:])
    if labels:
        pbf += encode_layer("labels", labels)
    return zxy, gzip.compress(pbf, 6, mtime=0)


# --------------------------------------------------------------------------- packing


def pack_key(z, x, y):
    """Which pack file a tile lives in (mirrored in the web client)."""
    if z <= 4:
        return (z, 0, 0)
    root = 5 if z <= 6 else 7
    return (root, x >> (z - root), y >> (z - root))


def live_pack_key(z, x, y):
    """Packing for the live map's z2-z6 tiles: one pack per zoom up to z4, then one
    per z4 ancestor (few files per forecast hour)."""
    return (z, 0, 0) if z <= 4 else (4, x >> (z - 4), y >> (z - 4))


def domain_tiles(fld, z):
    ii = np.concatenate([np.arange(fld.nx), np.full(fld.ny, fld.nx - 1), np.arange(fld.nx)[::-1], np.zeros(fld.ny)])
    jj = np.concatenate([np.zeros(fld.nx), np.arange(fld.ny), np.full(fld.nx, fld.ny - 1), np.arange(fld.ny)[::-1]])
    mx, my = fld.to_merc.transform(fld.x0 + ii * fld.dx, fld.y0 + jj * fld.dx)
    size = 2 * ORIGIN / 2**z
    x0, x1 = int((min(mx) + ORIGIN) // size), int((max(mx) + ORIGIN) // size)
    y0, y1 = int((ORIGIN - max(my)) // size), int((ORIGIN - min(my)) // size)
    n = 2 ** z  # domains may reach past web mercator's +-85.05 deg / the date line
    x0, x1, y0, y1 = max(0, x0), min(n - 1, x1), max(0, y0), min(n - 1, y1)
    return [(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def build(source, out, minzoom=MINZOOM, maxzoom=MAXZOOM, workers=None, log=True, pack=None, label_levels=None,
          min_band=None):
    """Build zooms minzoom..maxzoom from a GRIB2 file or a published grid into
    pack files in `out`.  Returns (tiles, packs, bytes, seconds)."""
    t0 = time.time()
    fld = Field(source)
    jobs = [t for z in range(minzoom, maxzoom + 1) for t in domain_tiles(fld, z)]
    # Longest jobs first (low zooms are the heaviest tiles) so no straggler is
    # left running alone at the end.
    jobs.sort(key=lambda t: t[0])
    packs = {}
    nbytes = 0
    with Pool(workers or os.cpu_count(), initializer=init_worker, initargs=(source, label_levels, min_band)) as pool:
        for n, (zxy, data) in enumerate(pool.imap_unordered(build_tile, jobs, chunksize=2)):
            if data:
                packs.setdefault((pack or pack_key)(*zxy), []).append((zxy, data))
                nbytes += len(data)
            if log and n % 500 == 0:
                print(f"{n}/{len(jobs)} tiles, {nbytes/1e6:.1f} MB, {time.time()-t0:.0f}s", flush=True)
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(out):
        os.remove(os.path.join(out, f))
    for key, tiles in packs.items():
        tiles.sort()
        header = struct.pack("<I", len(tiles))
        off = 4 + 20 * len(tiles)
        body = b""
        for (z, x, y), data in tiles:
            header += struct.pack("<5I", z, x, y, off, len(data))
            off += len(data)
            body += data
        with open(os.path.join(out, "%d-%d-%d.bin" % key), "wb") as f:
            f.write(header + body)
    return fld, packs, nbytes, time.time() - t0


def main(grib="data/hrrr_t2m.grib2", out="web/tiles"):
    fld, packs, nbytes, secs = build(grib, out)
    meta = json.load(open(grib.replace(".grib2", ".json")))
    meta.update(
        minzoom=MINZOOM, maxzoom=MAXZOOM, units="F",
        tmin=float(np.floor(fld.F.min())), tmax=float(np.ceil(fld.F.max())),
        packs=sorted("%d-%d-%d" % k for k in packs),
    )
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"))
    ntiles = sum(len(v) for v in packs.values())
    print(f"done: {ntiles} tiles in {len(packs)} packs, {nbytes/1e6:.1f} MB, {secs:.0f}s")


if __name__ == "__main__":
    main(*sys.argv[1:])
    # eccodes and PROJ both register native teardown that can double-free at
    # interpreter exit; all output is written, so skip teardown.
    sys.stdout.flush()
    os._exit(0)
