#!/usr/bin/env python3
"""Publish GFS 0.25° 2 m temperature (global) for the live map.

Same bands as the HRRR field (1 °F, same colours); the grid is the whole
world, cropped to web mercator's latitude range plus one row, with the -180
column repeated at +180 so the field closes at the date line.

usage: publish_gfs_t2m.py [--run 2026092706] [--hours 72] [--step 6] [--out web/live/run]
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

VID = "gfst2m"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="2026092706")
    ap.add_argument("--hours", type=int, default=72)
    ap.add_argument("--step", type=int, default=6)
    ap.add_argument("--out", default="web/live/run")
    ap.add_argument("--tiles-maxzoom", type=int, default=2)
    a = ap.parse_args()
    run = dt.datetime.strptime(a.run, "%Y%m%d%H")
    var = VARIABLES["t2m"]
    out = os.path.join(a.out, VID)
    grids = os.path.join(out, "grids")
    os.makedirs(grids, exist_ok=True)

    t0 = time.time()
    hours = list(range(0, a.hours + 1, a.step))
    with ThreadPoolExecutor(12) as ex:
        fields = list(ex.map(lambda fh: gfs_snow.fetch(run, fh, var["match"]), hours))
    t_dl = time.time() - t0
    gm = fields[0][1]
    d = gm["iDirectionIncrementInDegrees"]
    ny_g, nx_g = fields[0][0].shape
    lats = gm["latitudeOfFirstGridPointInDegrees"] - d * np.arange(ny_g)  # rows north -> south
    lons = (gm["longitudeOfFirstGridPointInDegrees"] + d * np.arange(nx_g) + 180) % 360 - 180
    rows = np.nonzero(np.abs(lats) <= 85.25)[0][::-1]  # south -> north
    cols = np.argsort(lons)
    cols = np.concatenate([cols, cols[:1]])  # repeat -180 as +180
    vmin, vmax = 1e9, -1e9
    for fh, (raw, _) in zip(hours, fields):
        f = var["convert"](raw[np.ix_(rows, cols)])
        vmin, vmax = min(vmin, float(f.min())), max(vmax, float(f.max()))
        q = np.round(f / var["interval"] * var["scale"]).astype("<i2")
        dq = np.diff(q, axis=1, prepend=np.int16(0)).astype("<i2")
        with open(os.path.join(grids, f"f{fh:02d}.i16.gz"), "wb") as fp:
            fp.write(gzip.compress(dq.tobytes(), 6, mtime=0))
    meta = {
        "model": "GFS", "grid": "0.25°", "run": run.strftime("%Y-%m-%dT%H:00Z"), "hours": hours,
        "var": {k: v for k, v in var.items() if k not in ("convert", "match")} | {"id": VID},
        "scale": var["scale"],
        "nx": len(cols), "ny": len(rows), "dx": d, "global": True,
        "x0": float(lons[cols[0]]), "y0": float(lats[rows[0]]),
        "proj": {"type": "latlon", "R": 6371229.0, "lat0": 30.0},
        "vmin": vmin, "vmax": vmax, "tmin": vmin / var["interval"], "tmax": vmax / var["interval"],
        "view": {"center": [-40, 25], "zoom": 1.2},
    }
    with open(os.path.join(grids, "meta.json"), "w") as fp:
        json.dump(meta, fp)
    print(f"GFS {a.run} t2m f{hours[0]:02d}-f{hours[-1]:02d}: download {t_dl:.1f}s, "
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
    index["vars"] = [v for v in index["vars"] if v["id"] != VID] + [{"id": VID, "name": "GFS temp"}]
    with open(idx_path, "w") as fp:
        json.dump(index, fp)
    print(f"published in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)
