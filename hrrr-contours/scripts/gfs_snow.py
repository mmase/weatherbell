#!/usr/bin/env python3
"""GFS 10:1 snowfall from the public NOAA GFS archive on AWS.

GFS 0.25 deg pgrb2 has no total-snowfall field, so snowfall is built the usual
way: for each 6 h window, liquid precipitation (APCP, kg m-2 == mm) times the
fraction of the window with categorical snow (CSNOW 6 h average), times a 10:1
snow-to-liquid ratio, converted to inches and summed over the windows.
Only the two GRIB messages per window are range-fetched via the .idx files.
"""
import datetime as dt
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import eccodes as ec
import numpy as np

BUCKET = "https://noaa-gfs-bdp-pds.s3.amazonaws.com"


def get(url, headers=None):
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers or {}), timeout=90) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise


def gfs_url(run, fh):
    return f"{BUCKET}/gfs.{run:%Y%m%d}/{run:%H}/atmos/gfs.t{run:%H}z.pgrb2.0p25.f{fh:03d}"


def fetch(run, fh, match):
    idx = get(gfs_url(run, fh) + ".idx").decode().strip().splitlines()
    for i, line in enumerate(idx):
        if match in line:
            a = int(line.split(":")[1])
            b = int(idx[i + 1].split(":")[1]) - 1 if i + 1 < len(idx) else ""
            g = ec.codes_new_from_message(get(gfs_url(run, fh), {"Range": f"bytes={a}-{b}"}))
            try:
                ni, nj = ec.codes_get(g, "Ni"), ec.codes_get(g, "Nj")
                v = ec.codes_get_values(g).reshape(nj, ni)
                meta = {k: ec.codes_get(g, k) for k in (
                    "latitudeOfFirstGridPointInDegrees", "longitudeOfFirstGridPointInDegrees",
                    "iDirectionIncrementInDegrees", "jDirectionIncrementInDegrees", "jScansPositively")}
            finally:
                ec.codes_release(g)
            return v, meta
    raise KeyError(f"{match} not in f{fh:03d}")


def window_snow(run, fh):
    """10:1 snowfall (inches) in the 6 h window ending at fh."""
    w = f"{fh - 6}-{fh} hour"
    apcp, meta = fetch(run, fh, f":APCP:surface:{w} acc fcst:")
    csnow, _ = fetch(run, fh, f":CSNOW:surface:{w} ave fcst:")
    return apcp * np.clip(csnow, 0, 1) * 10 / 25.4, meta


def total_snow(run, f0, f1, workers=8):
    """Accumulated 10:1 snowfall from f0 to each 6 h step up to f1 (list of (fh, grid))."""
    hours = list(range(f0 + 6, f1 + 1, 6))
    with ThreadPoolExecutor(workers) as pool:
        parts = list(pool.map(lambda h: window_snow(run, h), hours))
    acc, out = 0, []
    for h, (s, meta) in zip(hours, parts):
        acc = acc + s
        out.append((h, acc.copy()))
    return out, parts[0][1]


def ne_box(grid, meta, lat=(37, 48), lon=(-82, -66)):
    """Crop a global 0.25 grid (lat 90 -> -90, lon 0 -> 360) to a lat/lon box."""
    d = meta["iDirectionIncrementInDegrees"]
    lats = meta["latitudeOfFirstGridPointInDegrees"] - d * np.arange(grid.shape[0])
    lons = (meta["longitudeOfFirstGridPointInDegrees"] + d * np.arange(grid.shape[1]) + 180) % 360 - 180
    r = (lats >= lat[0]) & (lats <= lat[1])
    c = (lons >= lon[0]) & (lons <= lon[1])
    return grid[np.ix_(r, c)]


if __name__ == "__main__":
    # scan: 24 h 10:1 snowfall from every 00Z run, Northeast box
    start, end = dt.datetime(2026, 1, 1), dt.datetime(2026, 2, 28)
    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]

    def one(day):
        try:
            steps, meta = total_snow(day, 0, 24, workers=4)
            ne = ne_box(steps[-1][1], meta)
            return day, float(ne.max()), float((ne >= 12).mean() * 100), float((ne >= 6).mean() * 100)
        except Exception as e:
            return day, None, str(e)[:60], None

    with ThreadPoolExecutor(6) as pool:
        for day, mx, a12, a6 in pool.map(one, days):
            print(f"{day:%Y-%m-%d} 00Z  max {mx if mx is None else round(mx, 1)} in  "
                  f"area>=12in {a12 if isinstance(a12, str) else round(a12, 1)}%  area>=6in {a6 if a6 is None else round(a6, 1)}%",
                  flush=True)
