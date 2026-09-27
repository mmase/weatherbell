#!/usr/bin/env python3
"""Download the 2 m temperature field from the most recent HRRR CONUS analysis.

Uses the public NOAA HRRR bucket on AWS and the .idx sidecar to HTTP-range
fetch only the single GRIB2 message we need (~1-2 MB instead of ~150 MB).
"""
import datetime as dt
import json
import sys
import urllib.request

BUCKET = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com"
VAR = ":TMP:2 m above ground:"


def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def latest_run(fhour=0, max_back_hours=12):
    now = dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)
    for back in range(max_back_hours):
        t = now - dt.timedelta(hours=back)
        base = f"{BUCKET}/hrrr.{t:%Y%m%d}/conus/hrrr.t{t:%H}z.wrfsfcf{fhour:02d}.grib2"
        try:
            idx = get(base + ".idx").decode()
            return t, base, idx
        except Exception:
            continue
    sys.exit("no HRRR run found")


def main(out="data/hrrr_t2m.grib2"):
    t, base, idx = latest_run()
    lines = idx.strip().splitlines()
    for i, line in enumerate(lines):
        if VAR in line:
            start = int(line.split(":")[1])
            end = int(lines[i + 1].split(":")[1]) - 1 if i + 1 < len(lines) else ""
            break
    else:
        sys.exit("TMP:2 m not in index")
    data = get(base, {"Range": f"bytes={start}-{end}"})
    with open(out, "wb") as f:
        f.write(data)
    meta = {"run": t.strftime("%Y-%m-%dT%H:00Z"), "fhour": 0, "source": base}
    with open(out.replace(".grib2", ".json"), "w") as f:
        json.dump(meta, f)
    print(f"{base} bytes {start}-{end} -> {out} ({len(data)/1e6:.1f} MB)")


if __name__ == "__main__":
    main(*sys.argv[1:])
