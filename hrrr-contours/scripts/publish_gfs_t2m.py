#!/usr/bin/env python3
"""Publish GFS 2 m temperature (global) for the live map.

Same bands as the HRRR field (1 °F, same colours); the grid is the whole
world, cropped to web mercator's latitude range plus one row, with the -180
column repeated at +180 so the field closes at the date line.

--grid 0p25   the 0.25° lat/lon product (pgrb2.0p25), ~1M points
--grid t1534  the model's native T1534 Gaussian grid (sfluxgrb, 3072 x 1536,
              0.117° ~ 13 km), ~4.5M points.  Gaussian latitudes are within 1%
              of evenly spaced; rows are resampled (cubic) onto an even grid
              with the same 0.1171875° spacing, so cells are square like the
              rest of the pipeline expects.

usage: publish_gfs_t2m.py [--grid 0p25|t1534] [--run 2026092706] [--hours 72] [--step 6]
"""
import argparse
import datetime as dt
import gzip
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import build_tiles  # noqa: E402
import gfs_snow  # noqa: E402
from publish_grids import VARIABLES  # noqa: E402

GRIDS = {"0p25": {"id": "gfst2m", "name": "GFS temp", "label": "0.25°"},
         "t1534": {"id": "gfsnat", "name": "GFS T1534", "label": "T1534 (13 km)"}}


def fetch_native(run, fh, match):
    """One message from the native-grid sflux file -> (values north->south, distinct lats, meta)."""
    import eccodes as ec
    url = f"{gfs_snow.BUCKET}/gfs.{run:%Y%m%d}/{run:%H}/atmos/gfs.t{run:%H}z.sfluxgrbf{fh:03d}.grib2"
    idx = gfs_snow.get(url + ".idx").decode().strip().splitlines()
    i = next(k for k, line in enumerate(idx) if match in line)
    a, b = int(idx[i].split(":")[1]), int(idx[i + 1].split(":")[1]) - 1
    g = ec.codes_new_from_message(gfs_snow.get(url, {"Range": f"bytes={a}-{b}"}))
    try:
        ni, nj = ec.codes_get(g, "Ni"), ec.codes_get(g, "Nj")
        assert ec.codes_get(g, "gridType") == "regular_gg" and ec.codes_get(g, "jScansPositively") == 0
        v = ec.codes_get_values(g).reshape(nj, ni)
        lats = ec.codes_get_array(g, "distinctLatitudes")
        meta = {"latitudeOfFirstGridPointInDegrees": float(lats.max()),
                "longitudeOfFirstGridPointInDegrees": ec.codes_get(g, "longitudeOfFirstGridPointInDegrees"),
                "iDirectionIncrementInDegrees": 360 / ni}
    finally:
        ec.codes_release(g)
    return v, np.sort(lats)[::-1], meta


def regrid_rows(v, src_lats, dst_lats):
    """Cubic (Catmull-Rom) resampling of rows (src north->south) onto dst latitudes."""
    asc = src_lats[::-1]
    u = np.interp(dst_lats, asc, np.arange(len(asc)))  # fractional row in ascending order
    j = np.clip(np.floor(u).astype(int), 1, len(asc) - 3)
    t = (u - j)[:, None]
    rows = v[::-1]
    p0, p1, p2, p3 = rows[j - 1], rows[j], rows[j + 1], rows[j + 2]
    return p1 + 0.5 * t * (p2 - p0 + t * (2 * p0 - 5 * p1 + 4 * p2 - p3 + t * (3 * (p1 - p2) + p3 - p0)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default="0p25", choices=sorted(GRIDS))
    ap.add_argument("--run", default="2026092706")
    ap.add_argument("--hours", type=int, default=72)
    ap.add_argument("--step", type=int, default=6)
    ap.add_argument("--out", default="web/live/run")
    ap.add_argument("--tiles-maxzoom", type=int, default=2)
    a = ap.parse_args()
    run = dt.datetime.strptime(a.run, "%Y%m%d%H")
    var = VARIABLES["t2m"]
    G = GRIDS[a.grid]
    VID = G["id"]
    out = os.path.join(a.out, VID)
    grids = os.path.join(out, "grids")
    os.makedirs(grids, exist_ok=True)

    t0 = time.time()
    hours = list(range(0, a.hours + 1, a.step))
    with ThreadPoolExecutor(12) as ex:
        if a.grid == "t1534":
            nat = list(ex.map(lambda fh: fetch_native(run, fh, var["match"]), hours))
        else:
            fields = list(ex.map(lambda fh: gfs_snow.fetch(run, fh, var["match"]), hours))
    t_dl = time.time() - t0
    if a.grid == "t1534":
        _, glats, gm = nat[0]
        d = gm["iDirectionIncrementInDegrees"]
        k = int(np.ceil(85.2 / d))  # even rows from the equator, one past web mercator's 85.05
        lats = d * np.arange(k, -k - 1, -1)  # north -> south, like the source
        fields = [(regrid_rows(v, gl, lats[::-1])[::-1], None) for v, gl, _ in nat]
    else:
        gm = fields[0][1]
        d = gm["iDirectionIncrementInDegrees"]
        lats = gm["latitudeOfFirstGridPointInDegrees"] - d * np.arange(fields[0][0].shape[0])  # rows north -> south
    nx_g = fields[0][0].shape[1]
    lons = (gm["longitudeOfFirstGridPointInDegrees"] + d * np.arange(nx_g) + 180) % 360 - 180
    rows = np.nonzero(np.abs(lats) <= 85.35)[0][::-1]  # south -> north
    cols = np.argsort(lons)
    cols = np.concatenate([cols, cols[:1]])  # repeat -180 as +180
    vmin, vmax = 1e9, -1e9
    levels = [k for k in (2, 4, 8) if (len(rows) - 1) % k == 0 and (len(cols) - 1) % k == 0]
    for fh, (raw, _) in zip(hours, fields):
        f = var["convert"](raw[np.ix_(rows, cols)])
        vmin, vmax = min(vmin, float(f.min())), max(vmax, float(f.max()))
        q = np.round(f / var["interval"] * var["scale"]).astype("<i2")
        dq = np.diff(q, axis=1, prepend=np.int16(0)).astype("<i2")
        with open(os.path.join(grids, f"f{fh:02d}.i16.gz"), "wb") as fp:
            fp.write(gzip.compress(dq.tobytes(), 6, mtime=0))
        for k in levels:  # pyramid: every k-th node, for zoomed-out views and playback
            qk = np.ascontiguousarray(q[::k, ::k])
            dk = np.diff(qk, axis=1, prepend=np.int16(0)).astype("<i2")
            with open(os.path.join(grids, f"f{fh:02d}-{k}.i16.gz"), "wb") as fp:
                fp.write(gzip.compress(dk.tobytes(), 6, mtime=0))
    meta = {
        "model": "GFS", "grid": G["label"], "run": run.strftime("%Y-%m-%dT%H:00Z"), "hours": hours,
        "var": {k: v for k, v in var.items() if k not in ("convert", "match")} | {"id": VID},
        "scale": var["scale"],
        "nx": len(cols), "ny": len(rows), "dx": d, "global": True, "levels": levels,
        "x0": float(lons[cols[0]]), "y0": float(lats[rows[0]]),
        "proj": {"type": "latlon", "R": 6371229.0, "lat0": 30.0},
        "vmin": vmin, "vmax": vmax, "tmin": vmin / var["interval"], "tmax": vmax / var["interval"],
        "view": {"center": [-40, 25], "zoom": 1.2},
    }
    with open(os.path.join(grids, "meta.json"), "w") as fp:
        json.dump(meta, fp)
    print(f"GFS {a.grid} {a.run} t2m f{hours[0]:02d}-f{hours[-1]:02d}: download {t_dl:.1f}s, "
          f"grids {time.time() - t0:.1f}s, {vmin:.1f}..{vmax:.1f} °F, grid {len(cols)}x{len(rows)}", flush=True)

    meta["tiles"] = {"minzoom": 0, "maxzoom": a.tiles_maxzoom, "packs": {}}
    for fh in hours:
        _, packs, nbytes, secs = build_tiles.build(
            os.path.join(grids, f"f{fh:02d}.i16.gz"), os.path.join(out, "tiles", f"f{fh:02d}"),
            0, a.tiles_maxzoom, log=False, pack=build_tiles.live_pack_key)  # labels every 5 °F, like HRRR
        meta["tiles"]["packs"][f"{fh:02d}"] = sorted("%d-%d-%d" % k for k in packs)
        print(f"f{fh:02d}: z0-{a.tiles_maxzoom} tiles {secs:.1f}s, {nbytes / 1e6:.1f} MB", flush=True)
    with open(os.path.join(out, "meta.json"), "w") as fp:
        json.dump(meta, fp)
    idx_path = os.path.join(a.out, "index.json")
    index = json.load(open(idx_path)) if os.path.exists(idx_path) else {"vars": []}
    index["vars"] = [v for v in index["vars"] if v["id"] != VID] + [{"id": VID, "name": G["name"]}]
    with open(idx_path, "w") as fp:
        json.dump(index, fp)
    print(f"published in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)
