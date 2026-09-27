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
# Temperature colour scale (°F), one colour per 1° band from -100 to 129
# (WeatherBell-style; sampled from the reference colour bar, centre of each degree).
TEMP_COLORS = """
    #410c6b #4d0984 #4c0a85 #4c0a85 #4c0a85 #4b0a86 #531883 #541881 #771a85 #821782 #801881
    #811880 #801881 #82177f #941d83 #981f82 #9a2080 #a32483 #a4247f #b4277c #c62c7e #c62a7c
    #c7297c #c82a7d #d9317f #da307d #df337f #e0347f #e23a87 #e13c8b #e03f8b #e95da2 #e45fa2
    #e55ea3 #e55ea2 #e65fa3 #e560a3 #de7aa4 #dc7ca4 #e494c3 #e296c4 #e396c4 #e395c5 #e495c5
    #e296c5 #d8a5ce #d4aacc #d3a9cc #d3a9cd #d3a9ce #d3a9cf #cabbd6 #c8bdd6 #c7bdd6 #c7bdd7
    #c6bed6 #bdcad9 #bccbd8 #baccd8 #bbe1e8 #bae1e9 #bbe2e8 #b9e1ea #afdbe7 #aadde8 #aef3f5
    #aff1f2 #adf2f4 #aef3f4 #aef2f4 #9fd9df #a1d7df #8fc2cd #89b5c7 #73acb0 #72abae #5d8b99
    #5f8796 #5d7580 #48696d #456a6b #2d5851 #2e5952 #2f5652 #22353e #2e5a54 #2e5a55 #456b6d
    #456b6d #476b6f #5d7982 #637b86 #778c94 #8f9696 #92a6a9 #96a8aa #b5b8ba #b5b8b9 #c4c3c2
    #cfcfdb #39248b #3a238d #3b238c #4f1a84 #521981 #561c74 #612650 #612654 #632555 #672551
    #783047 #793042 #7e322c #853328 #953c26 #9f5538 #b25c48 #b25c4a #b0604b #af7759 #c68e90
    #c6908e #c79393 #d3a0a0 #dcaeae #e1b9b8 #e7c5c3 #eed0cf #f5dbdc #f9e6e6 #f1e7e6 #ece8e7
    #e6e7e9 #e1eaeb #d9ebec #cfebee #c9eded #bbe5ea #a7d5e7 #97c7e2 #85b8de #75a5d4 #6f9ac9
    #6990bd #6483b5 #5f75aa #5969a0 #515c92 #4e548b #565790 #6969a3 #7675b1 #8584b5 #9998b0
    #a6a5ac #b6b5a5 #c4c3a3 #d2d19e #e1e197 #f3f691 #fcfb87 #fcef79 #fbe671 #f6db66 #f6d05c
    #f0be4c #ecb442 #eba93c #eda038 #ee9736 #ee9034 #ea8731 #ea7e2f #e7762c #e4702c #e5682d
    #e4622b #dd5e28 #d05224 #c54822 #af361a #a12c16 #912111 #79160c #6e1611 #681914 #631e17
    #62201b #5e321a #58412e #564042 #594d43 #605b46 #675f4e #7e7267 #97786e #99796e #9e877f
    #a1958e #9e9089 #9d8c85 #997c75 #9b786f #9a7870 #9b7870 #9b786f #97675e #975d51 #8d5552
    #844d4f #834e4f #783747 #782f49 #782f48 #772f4b #682850 #593547 #554140 #544141 #494742
    #434a43 #434944 #424a43 #3a4f4a #2d5b51 #39774f #377a4e #38794d #38794a #38794b
""".split()
assert len(TEMP_COLORS) == 230

# int16 counts per band, and the colour ramp (display units -> colour).
VARIABLES = {
    "t2m": {
        "match": ":TMP:2 m above ground:", "name": "2 m Air Temperature", "short": "Temperature",
        "units": "°F", "interval": 1, "decimals": 0, "scale": 10,
        "convert": lambda k: (k - 273.15) * 9 / 5 + 32,
        "stops": [[t + 0.5, c] for t, c in zip(range(-100, 130), TEMP_COLORS)],  # one colour per degree
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
    order = list(VARIABLES)  # other publishers (GFS) append their own fields after these
    index["vars"].sort(key=lambda v: order.index(v["id"]) if v["id"] in order else len(order))
    with open(idx_path, "w") as fp:
        json.dump(index, fp)
    print(f"published in {time.time() - t0:.1f}s wall")


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)  # skip eccodes/PROJ native teardown (double free at exit)
