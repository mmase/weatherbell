#!/usr/bin/env python3
"""Publish HRRR 2 m temperature forecast hours as compact grids for the live map.

This is the whole server-side step for the client-contoured map: no tiles are
built.  For each forecast hour it

  1. HTTP-range-fetches only the TMP:2 m message (via the .idx sidecar),
  2. decodes it with eccodes,
  3. quantises to int16 tenths of a degree F, and gzips it (~1 MB).

Hours are processed in parallel and each one is written as soon as it is ready,
so in production this runs per forecast hour straight off NOAA's
new-object notifications.

With --tiles-maxzoom N it also builds the zoomed-out vector tiles (z2..N) for
each hour from that same grid; the browser contours everything above N itself.

usage: publish_grids.py [--run YYYYMMDDHH] [--hours 0-18] [--tiles-maxzoom 6] [--out web/live/run]
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
VAR = ":TMP:2 m above ground:"
SCALE = 10  # stored value = round(degF * SCALE)


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


def fetch_message(run, fh):
    idx = get(url(run, fh) + ".idx").decode().strip().splitlines()
    for i, line in enumerate(idx):
        if VAR in line:
            start = int(line.split(":")[1])
            end = int(idx[i + 1].split(":")[1]) - 1 if i + 1 < len(idx) else ""
            return get(url(run, fh), {"Range": f"bytes={start}-{end}"})
    raise RuntimeError(f"TMP:2 m missing in f{fh:02d}")


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


def process(run, fh, out):
    t0 = time.time()
    msg = fetch_message(run, fh)
    t1 = time.time()
    info, proj, k = grid_info(msg)
    f = (k - 273.15) * 9 / 5 + 32
    q = np.round(f * SCALE).astype("<i2").reshape(info["Ny"], info["Nx"])
    # row deltas compress ~1/3 better; the client undoes them with a prefix sum
    d = np.diff(q, axis=1, prepend=np.int16(0)).astype("<i2")
    data = gzip.compress(d.tobytes(), 6, mtime=0)
    with open(os.path.join(out, f"f{fh:02d}.i16.gz"), "wb") as fp:
        fp.write(data)
    t2 = time.time()
    return fh, info, proj, float(f.min()), float(f.max()), len(data), t1 - t0, t2 - t1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", help="YYYYMMDDHH (default: newest run that has the last hour)")
    ap.add_argument("--hours", default="0-18")
    ap.add_argument("--out", default="web/live/run")
    ap.add_argument("--tiles-maxzoom", type=int, default=6, help="0 = grids only")
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.hours.split("-"))
    run = (dt.datetime.strptime(a.run, "%Y%m%d%H").replace(tzinfo=dt.timezone.utc)
           if a.run else latest_complete_run(hi))
    grids = os.path.join(a.out, "grids")
    os.makedirs(grids, exist_ok=True)
    t0 = time.time()
    results = []
    with ThreadPoolExecutor(8) as pool:
        for r in pool.map(lambda fh: process(run, fh, grids), range(lo, hi + 1)):
            fh, _, _, tmin, tmax, size, t_dl, t_enc = r
            print(f"f{fh:02d}: download {t_dl:.2f}s, decode+encode {t_enc:.2f}s, "
                  f"{size / 1e6:.2f} MB, {tmin:.0f}..{tmax:.0f} F", flush=True)
            results.append(r)
    info, proj = results[0][1], results[0][2]
    lon1 = info["longitudeOfFirstGridPointInDegrees"]
    lon1 = lon1 - 360 if lon1 > 180 else lon1
    x0, y0 = Transformer.from_crs("+proj=longlat +R=6371229 +no_defs", proj, always_xy=True).transform(
        lon1, info["latitudeOfFirstGridPointInDegrees"])
    lov = info["LoVInDegrees"]
    meta = {
        "model": "HRRR", "field": "2 m temperature", "units": "F", "scale": SCALE,
        "run": run.strftime("%Y-%m-%dT%H:00Z"), "hours": [r[0] for r in results],
        "nx": info["Nx"], "ny": info["Ny"], "dx": info["DxInMetres"],
        "x0": x0, "y0": y0,  # projected coordinates of grid point (0, 0)
        "proj": {"type": "lcc", "R": 6371229.0, "lat0": info["LaDInDegrees"],
                 "lon0": lov - 360 if lov > 180 else lov,
                 "lat1": info["Latin1InDegrees"], "lat2": info["Latin2InDegrees"]},
        "tmin": min(r[3] for r in results), "tmax": max(r[4] for r in results),
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
            _, packs, nbytes, secs = build_tiles.build(src, os.path.join(a.out, "tiles", f"f{fh:02d}"),
                                                      2, a.tiles_maxzoom, log=False)
            meta["tiles"]["packs"][f"{fh:02d}"] = sorted("%d-%d-%d" % k for k in packs)
            print(f"f{fh:02d}: z2-{a.tiles_maxzoom} tiles {secs:.1f}s, {nbytes / 1e6:.1f} MB", flush=True)
    with open(os.path.join(a.out, "meta.json"), "w") as fp:
        json.dump(meta, fp)
    print(f"published in {time.time() - t0:.1f}s wall")


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)  # skip eccodes/PROJ native teardown (double free at exit)
