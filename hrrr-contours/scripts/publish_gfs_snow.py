#!/usr/bin/env python3
"""Publish GFS 10:1 total snowfall for the live map (accumulated by forecast hour).

The colour scale is WeatherBell's snowfall scale in inches, whose bands are not
evenly spaced (0.1, 0.5, 1, 1.5 ... 10, 11, 12 ... 48).  The contour engine
works in "band units", so the field is stored through a monotonic
piecewise-linear map that puts threshold k at k (and 0 in at -1, i.e. below
the first band).  A monotonic remap does not move level sets, so the band
edges are exactly the thresholds; the page maps values back for the readout.

usage: publish_gfs_snow.py [--run 2026022200] [--hours 72] [--out web/live/run]
"""
import argparse
import datetime as dt
import gzip
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import build_tiles  # noqa: E402
import gfs_snow  # noqa: E402

# WeatherBell snowfall scale (inches): legend labels, and a colour per half-step
LABELS = [0.1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10] + list(range(12, 50, 2))
THRESHOLDS = [0.1, 0.5] + [x / 2 for x in range(2, 21)] + list(range(11, 49))  # 59 edges
COLORS = [  # sampled from the WeatherBell colour bar, one per band (58)
    "#dbdbdb", "#979797", "#6e6e6e", "#505050", "#a3d0f5", "#88b6f4", "#66a2ec", "#5595ed",
    "#4482e9", "#366de2", "#2e63cb", "#2758be", "#380689", "#44098a", "#520d87", "#5d0f86",
    "#791785", "#911e83", "#b7267f", "#df317b", "#e03581", "#e44e98", "#eb69ac", "#ed75b3",
    "#ed8bc0", "#e491c3", "#e198c6", "#daa0c9", "#d3add2", "#cdb5d5", "#c7c6e0", "#bbd5e7",
    "#b8e1ed", "#b4ecf3", "#aef7f8", "#a7f1f2", "#93d8d5", "#82bac2", "#89b6c6", "#8cb5c9",
    "#8fb3cd", "#91b0cc", "#95accf", "#95add1", "#99a7d4", "#9ba7d7", "#9da4d8", "#a1a2d8",
    "#a59eda", "#a99ee0", "#aa9de2", "#ae9ae2", "#b195e4", "#b194e5", "#b692e9", "#b990ea",
    "#c08dec", "#c38af0",
]
assert len(THRESHOLDS) == len(COLORS) + 1
SCALE = 400  # int16 counts per band


def to_bands(v):
    """inches -> band units (threshold k maps to k; 0 in maps to -1)."""
    th = np.asarray(THRESHOLDS, float)
    x = np.concatenate([[0.0], th, [th[-1] + 100]])
    y = np.concatenate([[-1.0], np.arange(len(th)), [len(th) - 1 + 100 / (th[-1] - th[-2])]])
    return np.interp(v, x, y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="2026022200")
    ap.add_argument("--hours", type=int, default=72)
    ap.add_argument("--region", default="global", help="'global' or lat0,lat1,lon0,lon1")
    ap.add_argument("--out", default="web/live/run")
    ap.add_argument("--tiles-maxzoom", type=int, default=6)
    a = ap.parse_args()
    run = dt.datetime.strptime(a.run, "%Y%m%d%H")
    # whole model domain by default; web mercator stops at +-85 deg
    la0, la1, lo0, lo1 = (-85, 85, -180, 180) if a.region == "global" else (float(x) for x in a.region.split(","))
    out = os.path.join(a.out, "snow")
    grids = os.path.join(out, "grids")
    os.makedirs(grids, exist_ok=True)

    t0 = time.time()
    steps, gm = gfs_snow.total_snow(run, 0, a.hours, workers=12)
    t_dl = time.time() - t0
    d = gm["iDirectionIncrementInDegrees"]
    lat_first = gm["latitudeOfFirstGridPointInDegrees"]  # 90, rows north -> south
    ny_g, nx_g = steps[0][1].shape
    lats = lat_first - d * np.arange(ny_g)
    lons = (gm["longitudeOfFirstGridPointInDegrees"] + d * np.arange(nx_g) + 180) % 360 - 180
    rows = np.nonzero((lats >= la0) & (lats <= la1))[0][::-1]  # south -> north
    cols = np.nonzero((lons >= lo0) & (lons <= lo1))[0]
    cols = cols[np.argsort(lons[cols])]
    wrap = a.region == "global"
    if wrap:  # repeat -180 as +180 so the grid closes at the date line
        cols = np.concatenate([cols, cols[:1]])
    vmax = 0.0
    for fh, acc in steps:
        v = acc[np.ix_(rows, cols)]
        vmax = max(vmax, float(v.max()))
        q = np.round(to_bands(v) * SCALE).astype("<i2")
        dq = np.diff(q, axis=1, prepend=np.int16(0)).astype("<i2")
        with open(os.path.join(grids, f"f{fh:02d}.i16.gz"), "wb") as fp:
            fp.write(gzip.compress(dq.tobytes(), 6, mtime=0))
    hours = [fh for fh, _ in steps]
    meta = {
        "model": "GFS", "grid": "0.25°", "run": run.strftime("%Y-%m-%dT%H:00Z"), "hours": hours,
        "accumulated": True,
        "var": {"id": "snow", "name": "GFS 10:1 Snowfall", "short": "Snowfall", "units": "in",
                "decimals": 1, "thresholds": THRESHOLDS, "colors": COLORS, "labels": LABELS,
                "alt": {"factor": 2.54, "units": "cm"}},
        "scale": SCALE,
        "nx": len(cols), "ny": len(rows), "dx": d, "global": wrap,
        "x0": float(lons[cols[0]]), "y0": float(lats[rows[0]]),
        "proj": {"type": "latlon", "R": 6371229.0, "lat0": 41.0 if wrap else (la0 + la1) / 2},
        "vmin": 0.0, "vmax": vmax,
        "tmin": -1.0, "tmax": float(to_bands(vmax)),
        "view": {"center": [-74.5, 41.2], "zoom": 5.4},
    }
    with open(os.path.join(grids, "meta.json"), "w") as fp:
        json.dump(meta, fp)
    t_grid = time.time() - t0
    print(f"GFS {a.run} snowfall f{hours[0]:02d}-f{hours[-1]:02d}: download {t_dl:.1f}s, "
          f"grids {t_grid:.1f}s, max {vmax:.1f} in, grid {len(cols)}x{len(rows)}", flush=True)

    label_bands = {THRESHOLDS.index(v) for v in LABELS}
    meta["tiles"] = {"minzoom": 2, "maxzoom": a.tiles_maxzoom, "packs": {}}
    for fh in hours:
        _, packs, nbytes, secs = build_tiles.build(
            os.path.join(grids, f"f{fh:02d}.i16.gz"), os.path.join(out, "tiles", f"f{fh:02d}"),
            2, a.tiles_maxzoom, log=False, pack=build_tiles.live_pack_key, label_levels=label_bands,
            min_band=0)  # under 0.1 in is transparent
        meta["tiles"]["packs"][f"{fh:02d}"] = sorted("%d-%d-%d" % k for k in packs)
        print(f"f{fh:02d}: z2-{a.tiles_maxzoom} tiles {secs:.1f}s, {sum(len(v) for v in packs.values())} tiles, "
              f"{nbytes / 1e3:.0f} KB", flush=True)
    with open(os.path.join(out, "meta.json"), "w") as fp:
        json.dump(meta, fp)
    idx_path = os.path.join(a.out, "index.json")
    index = json.load(open(idx_path)) if os.path.exists(idx_path) else {"vars": []}
    index["vars"] = [v for v in index["vars"] if v["id"] != "snow"] + [{"id": "snow", "name": "GFS snow"}]
    with open(idx_path, "w") as fp:
        json.dump(index, fp)
    print(f"published in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)
