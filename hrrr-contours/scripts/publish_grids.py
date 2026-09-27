#!/usr/bin/env python3
"""Publish HRRR forecast hours of one field as compact grids for the live map.

This is the whole server-side step for the client-contoured map: no tiles are
built.  For each forecast hour it

  1. HTTP-range-fetches only that field's message (via the .idx sidecar),
  2. decodes it with eccodes and converts units,
  3. stores it as int16 in *band units* (value / interval * scale, so one
     contour band is `scale` counts), row-delta encoded and gzipped (~1.4 MB).

Fields are declared in VARIABLES; the contouring code only ever sees band
units, so adding a field needs no client or tiler changes.

Hours are processed in parallel and each one is written as soon as it is ready,
so in production this runs per forecast hour straight off NOAA's
new-object notifications.

With --tiles-maxzoom N it also builds the zoomed-out vector tiles (z2..N) for
each hour from that same grid; the browser contours everything above N itself.

usage: publish_grids.py [--var t2m] [--run YYYYMMDDHH] [--hours 0-18] [--tiles-maxzoom 6] [--out web/live/run]
"""
import argparse
import datetime as dt
import gzip
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import eccodes as ec
import numpy as np
from pyproj import Transformer

BUCKET = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com"
# Each field: GRIB index match, unit conversion, band interval (display units),
# int16 counts per band, and the colour ramp (display units -> colour).
VARIABLES = {
    "t2m": {
        "match": ":TMP:2 m above ground:", "name": "2 m Air Temperature", "short": "Temperature",
        "units": "°F", "interval": 1, "decimals": 0, "scale": 10,
        "convert": lambda k: (k - 273.15) * 9 / 5 + 32,
        "stops": [[-40, "#f1e6f5"], [-20, "#c7a4d8"], [0, "#7b4fa6"], [10, "#4b3f9e"], [20, "#2c5aa8"],
                  [32, "#3d93d1"], [40, "#72c6cf"], [50, "#58b37a"], [60, "#9ccb52"], [70, "#eadb55"],
                  [80, "#f5a940"], [90, "#e66a31"], [100, "#c42a2c"], [110, "#8e1239"], [120, "#e6a3c3"]],
        "ticks": 10, "highlight": 32,
    },
    "pwat": {
        "match": ":PWAT:entire atmosphere (considered as a single layer):", "name": "Precipitable Water",
        "short": "Precip. water", "units": "in", "interval": 0.1, "decimals": 1, "scale": 50,
        "convert": lambda kgm2: kgm2 / 25.4,  # kg m-2 == mm of liquid water
        "stops": [[0.0, "#8a5a2b"], [0.25, "#c49a5c"], [0.5, "#e8d6a4"], [0.75, "#c6e0a0"],
                  [1.0, "#74c07c"], [1.25, "#2f9e7c"], [1.5, "#1f7fae"], [1.75, "#2b55b3"],
                  [2.0, "#4b2f9e"], [2.25, "#8a2aa0"], [2.5, "#c33d9c"], [3.0, "#f4a3cf"]],
        "ticks": 0.5, "highlight": None,
    },
}


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def url(run, fh):
    return f"{BUCKET}/hrrr.{run:%Y%m%d}/conus/hrrr.t{run:%H}z.wrfsfcf{fh:02d}.grib2"


def latest_complete_run(last_hour, back=12):
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    for b in range(back):
        run = now - dt.timedelta(hours=b)
        try:
            get(url(run, last_hour) + ".idx")
            return run
        except Exception:
            continue
    sys.exit(f"no run with f{last_hour:02d} in the last {back} h")


def fetch_message(run, fh, match):
    idx = get(url(run, fh) + ".idx").decode().strip().splitlines()
    for i, line in enumerate(idx):
        if match in line:
            start = int(line.split(":")[1])
            end = int(idx[i + 1].split(":")[1]) - 1 if i + 1 < len(idx) else ""
            return get(url(run, fh), {"Range": f"bytes={start}-{end}"})
    raise RuntimeError(f"{match} missing in f{fh:02d}")


def grid_info(msg):
    g = ec.codes_new_from_message(msg)
    try:
        info = {k: ec.codes_get(g, k) for k in (
            "Nx", "Ny", "DxInMetres", "latitudeOfFirstGridPointInDegrees",
            "longitudeOfFirstGridPointInDegrees", "LaDInDegrees", "LoVInDegrees",
            "Latin1InDegrees", "Latin2InDegrees")}
        assert ec.codes_get(g, "jScansPositively") == 1 and ec.codes_get(g, "iScansNegatively") == 0
        proj = ec.codes_get(g, "projString")
        values = ec.codes_get_values(g)
    finally:
        ec.codes_release(g)
    return info, proj, values


def process(run, fh, out, var):
    t0 = time.time()
    msg = fetch_message(run, fh, var["match"])
    t1 = time.time()
    info, proj, raw = grid_info(msg)
    f = var["convert"](raw)
    u = f / var["interval"] * var["scale"]  # band units * scale
    assert np.abs(u).max() < 32767, "field out of int16 range; lower scale"
    q = np.round(u).astype("<i2").reshape(info["Ny"], info["Nx"])
    # row deltas compress ~1/3 better; the client undoes them with a prefix sum
    d = np.diff(q, axis=1, prepend=np.int16(0)).astype("<i2")
    data = gzip.compress(d.tobytes(), 6, mtime=0)
    with open(os.path.join(out, f"f{fh:02d}.i16.gz"), "wb") as fp:
        fp.write(data)
    t2 = time.time()
    return fh, info, proj, float(f.min()), float(f.max()), len(data), t1 - t0, t2 - t1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--var", default="t2m", choices=sorted(VARIABLES))
    ap.add_argument("--run", help="YYYYMMDDHH (default: newest run that has the last hour)")
    ap.add_argument("--hours", default="0-18")
    ap.add_argument("--out", default="web/live/run")
    ap.add_argument("--tiles-maxzoom", type=int, default=6, help="0 = grids only")
    a = ap.parse_args()
    var = VARIABLES[a.var]
    out = os.path.join(a.out, a.var)
    lo, hi = (int(x) for x in a.hours.split("-"))
    run = (dt.datetime.strptime(a.run, "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
           if a.run else latest_complete_run(hi))
    grids = os.path.join(out, "grids")
    os.makedirs(grids, exist_ok=True)
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(8) as pool:
        for r in pool.map(lambda fh: process(run, fh, grids, var), range(lo, hi + 1)):
            fh, _, _, tmin, tmax, size, t_dl, t_enc = r
            print(f"f{fh:02d}: download {t_dl:.2f}s, decode+encode {t_enc:.2f}s, "
                  f"{size / 1e6:.2f} MB, {tmin:.2f}..{tmax:.2f} {var['units']}", flush=True)
            results.append(r)
    info, proj = results[0][1], results[0][2]
    lon1 = info["longitudeOfFirstGridPointInDegrees"]
    lon1 = lon1 - 360 if lon1 > 180 else lon1
    x0, y0 = Transformer.from_crs("+proj=longlat +R=6371229 +no_defs", proj, always_xy=True).transform(
        lon1, info["latitudeOfFirstGridPointInDegrees"])
    lov = info["LoVInDegrees"]
    meta = {
        "model": "HRRR", "var": {k: v for k, v in var.items() if k not in ("convert", "match")} | {"id": a.var},
        "scale": var["scale"],  # int16 counts per contour band
        "run": run.strftime("%Y-%m-%dT%H:00Z"), "hours": [r[0] for r in results],
        "nx": info["Nx"], "ny": info["Ny"], "dx": info["DxInMetres"],
        "x0": x0, "y0": y0,  # projected coordinates of grid point (0, 0)
        "proj": {"type": "lcc", "R": 6371229.0, "lat0": info["LaDInDegrees"],
                 "lon0": lov - 360 if lov > 180 else lov,
                 "lat1": info["Latin1InDegrees"], "lat2": info["Latin2InDegrees"]},
        # data range in display units, and in band units (what the contours use)
        "vmin": min(r[3] for r in results), "vmax": max(r[4] for r in results),
        "tmin": min(r[3] for r in results) / var["interval"], "tmax": max(r[4] for r in results) / var["interval"],
    }
    with open(os.path.join(grids, "meta.json"), "w") as fp:
        json.dump(meta, fp)
    total = sum(r[5] for r in results)
    print(f"run {meta['run']}: {len(results)} grids, {total / 1e6:.1f} MB, {time.time() - t0:.1f}s wall", flush=True)

    meta["tiles"] = {"minzoom": 2, "maxzoom": a.tiles_maxzoom, "packs": {}} if a.tiles_maxzoom else None
    if a.tiles_maxzoom:
        sys.path.insert(0, os.path.dirname(__file__))
        import build_tiles
        for fh in meta["hours"]:
            src = os.path.join(grids, f"f{fh:02d}.i16.gz")
            _, packs, nbytes, secs = build_tiles.build(src, os.path.join(out, "tiles", f"f{fh:02d}"),
                                                      2, a.tiles_maxzoom, log=False,
                                                      pack=build_tiles.live_pack_key)
            meta["tiles"]["packs"][f"{fh:02d}"] = sorted("%d-%d-%d" % k for k in packs)
            print(f"f{fh:02d}: z2-{a.tiles_maxzoom} tiles {secs:.1f}s, {nbytes / 1e6:.1f} MB", flush=True)
    with open(os.path.join(out, "meta.json"), "w") as fp:
        json.dump(meta, fp)
    # run index: which fields are published (the page's field switcher reads it)
    idx_path = os.path.join(a.out, "index.json")
    index = json.load(open(idx_path)) if os.path.exists(idx_path) else {"vars": []}
    index["vars"] = [v for v in index["vars"] if v["id"] != a.var] + [{"id": a.var, "name": var["short"]}]
    index["vars"].sort(key=lambda v: list(VARIABLES).index(v["id"]))
    with open(idx_path, "w") as fp:
        json.dump(index, fp)
    print(f"published in {time.time() - t0:.1f}s wall")


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)  # skip eccodes/PROJ native teardown (double free at exit)
