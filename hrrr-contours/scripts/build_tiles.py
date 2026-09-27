#!/usr/bin/env python3
"""Build vector tiles of 1-degree filled temperature contours from an HRRR GRIB2 field.

Pipeline (per tile, per zoom):

  1. Pick a lattice in HRRR grid-index space whose spacing is ~1.5 screen px at
     that zoom (1/16 of a 3 km cell at z9, 8 cells at z2).  The lattice is
     global, so neighbouring tiles share identical lattice points.
  2. Evaluate the field on the lattice window covering the tile:
       - upsampling (spacing < 1 cell): separable Keys bicubic convolution.
         It is C1-continuous, so contours come out as smooth curves instead of
         the kinked polylines you get from contouring the raw 3 km grid, and
         it is strictly local (4x4 support) so every tile computes bit-identical
         values for shared lattice points -> contours match across tile seams.
       - at low zooms the lattice is the native grid itself (never coarser),
         so every model feature is kept.
  3. contourpy computes, for every integer degree t, the superlevel polygon
     {T >= t} (layer "levels", plus the data footprint in "base").  Painted in
     ascending t, these stack into 1-degree bands that cannot have gaps, and
     their outlines are the isotherms.  A lightly simplified copy of the
     isolines (layer "labels") is used only for text placement.
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
LABEL_ALL_ZOOM = 7  # from this zoom every 1-degree isoline gets a label line
LABEL_TOLERANCE = 40  # tile units (~2.5 px) for the label-only line layer
# Fill simplification, in screen px at the tile's own zoom.  Levels are stacked
# (see below), so each polygon can be simplified independently without opening
# gaps; rings are never removed (topology-preserving), only thinned.  The top
# zoom is overzoomed up to 16x, so its tolerance is set in overzoomed px.
SIMPLIFY_PX = 0.3
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


def keys_weights(u, n):
    """Keys (a=-0.5) cubic convolution weights for sample positions u (in cells).

    Returns (W, first) where W[k, :] are weights over padded-grid columns
    first..first+W.shape[1]-1 (the grid is padded by 2 on each side).
    """
    base = np.floor(u).astype(np.int64)
    t = u - base
    a = -0.5
    def k1(x):  # |x| <= 1
        return (a + 2) * x**3 - (a + 3) * x**2 + 1
    def k2(x):  # 1 < |x| < 2
        return a * x**3 - 5 * a * x**2 + 8 * a * x - 4 * a
    w = np.stack([k2(1 + t), k1(t), k1(1 - t), k2(2 - t)], axis=1)
    first = base.min() - 1
    width = base.max() + 3 - first
    W = np.zeros((len(u), width))
    rows = np.arange(len(u))[:, None]
    cols = (base - 1 - first)[:, None] + np.arange(4)[None, :]
    W[rows, cols] = w
    return W, first + 2  # +2 for padding offset


class Field:
    def __init__(self, path):
        self.F, self.proj, self.x0, self.y0, self.dx = load_field(path)
        self.ny, self.nx = self.F.shape
        self.Fp = np.pad(self.F, 2, mode="edge")
        self.to_merc = WebMercator(self.proj, inverse=False)
        self.to_lcc = WebMercator(self.proj, inverse=True)

    def spacing(self, z):
        # ~1.6 px per lattice step at every zoom; the top zoom is twice as dense
        # because it is also what MapLibre overzooms (up to 16x) beyond z9.
        # Never coarser than the native 3 km grid, so no model feature is
        # smoothed away at low zooms.
        return 1.0 / 32.0 if z == MAXZOOM else min(1.0, 2.0 ** (MAXZOOM - z) / 16.0)

    def lattice(self, z, i0, i1, j0, j1):
        """Field values on the global lattice restricted to grid-index box."""
        s = self.spacing(z)
        ni = np.arange(max(0, math.ceil(i0 / s)), min(math.floor((self.nx - 1) / s), math.floor(i1 / s)) + 1)
        nj = np.arange(max(0, math.ceil(j0 / s)), min(math.floor((self.ny - 1) / s), math.floor(j1 / s)) + 1)
        if len(ni) < 2 or len(nj) < 2:
            return None
        ui, uj = ni * s, nj * s
        if s < 1:
            Wx, fx = keys_weights(ui, self.nx)
            Wy, fy = keys_weights(uj, self.ny)
            sub = self.Fp[fy:fy + Wy.shape[1], fx:fx + Wx.shape[1]]
            Z = Wy @ sub @ Wx.T
        else:  # exactly the native grid: use the model values as-is
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


def init_worker(path):
    global FIELD
    FIELD = Field(path)


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
    pad = 2 * s
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
    for t in range(lo, hi + 1):
        pts, offs, outer = (c[0] for c in gen.filled(t, top))
        if pts is not None:
            fills.append((t, pts, offs, outer))
        # Isolines for text placement only (every 5 deg at low zoom).
        if t > lo and (t % 5 == 0 or z >= LABEL_ALL_ZOOM):
            lp, lo_ = (c[0] for c in gen.lines(t))
            if lp is not None:
                lines.append((t, lp, lo_))
    if not fills:
        return zxy, None

    # one reprojection call for every vertex in the tile
    allpts = np.concatenate([f[1] for f in fills] + [l[1] for l in lines])
    mx, my = fld.to_merc.transform(allpts[:, 0], allpts[:, 1])
    tp = np.column_stack([(mx - minx) * scale, (maxy - my) * scale])
    k = 0
    polys, mls = [], []
    for t, pts, offs, outer in fills:
        c = tp[k:k + len(pts)]; k += len(pts)
        polys.append(shapely.from_ragged_array(
            shapely.GeometryType.MULTIPOLYGON, c, (offs, outer, np.array([0, len(outer) - 1])))[0])
    for t, lp, lo_ in lines:
        c = tp[k:k + len(lp)]; k += len(lp)
        mls.append(shapely.from_ragged_array(
            shapely.GeometryType.MULTILINESTRING, c, (lo_, np.array([0, len(lo_) - 1])))[0])

    rect = (-BUFFER, -BUFFER, EXTENT + BUFFER, EXTENT + BUFFER)
    px = EXTENT / 512 / (16 if z == MAXZOOM else 1)
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


def domain_tiles(fld, z):
    ii = np.concatenate([np.arange(fld.nx), np.full(fld.ny, fld.nx - 1), np.arange(fld.nx)[::-1], np.zeros(fld.ny)])
    jj = np.concatenate([np.zeros(fld.nx), np.arange(fld.ny), np.full(fld.nx, fld.ny - 1), np.arange(fld.ny)[::-1]])
    mx, my = fld.to_merc.transform(fld.x0 + ii * fld.dx, fld.y0 + jj * fld.dx)
    size = 2 * ORIGIN / 2**z
    x0, x1 = int((min(mx) + ORIGIN) // size), int((max(mx) + ORIGIN) // size)
    y0, y1 = int((ORIGIN - max(my)) // size), int((ORIGIN - min(my)) // size)
    return [(z, x, y) for x in range(x0, x1 + 1) for y in range(y0, y1 + 1)]


def main(grib="data/hrrr_t2m.grib2", out="web/tiles"):
    t0 = time.time()
    fld = Field(grib)
    jobs = [t for z in range(MINZOOM, MAXZOOM + 1) for t in domain_tiles(fld, z)]
    # Longest jobs first (low zooms are the heaviest tiles) so no straggler is
    # left running alone at the end.
    jobs.sort(key=lambda t: t[0])
    packs = {}
    nbytes = 0
    with Pool(os.cpu_count(), initializer=init_worker, initargs=(grib,)) as pool:
        for n, (zxy, data) in enumerate(pool.imap_unordered(build_tile, jobs, chunksize=4)):
            if data:
                packs.setdefault(pack_key(*zxy), []).append((zxy, data))
                nbytes += len(data)
            if n % 500 == 0:
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
    meta = json.load(open(grib.replace(".grib2", ".json")))
    meta.update(
        minzoom=MINZOOM, maxzoom=MAXZOOM, units="F",
        tmin=float(np.floor(fld.F.min())), tmax=float(np.ceil(fld.F.max())),
        packs=sorted("%d-%d-%d" % k for k in packs),
    )
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"))
    ntiles = sum(len(v) for v in packs.values())
    print(f"done: {ntiles} tiles in {len(packs)} packs, {nbytes/1e6:.1f} MB, {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main(*sys.argv[1:])
    # eccodes and PROJ both register native teardown that can double-free at
    # interpreter exit; all output is written, so skip teardown.
    sys.stdout.flush()
    os._exit(0)
