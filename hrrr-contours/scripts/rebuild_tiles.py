#!/usr/bin/env python3
"""Rebuild the pre-built tiles of every published field from its stored grids
(after a change to the contouring, e.g. the interpolation kernel).  No download.

usage: rebuild_tiles.py [--out web/live/run] [var ...]
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import build_tiles  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="web/live/run")
    ap.add_argument("vars", nargs="*")
    a = ap.parse_args()
    ids = a.vars or [v["id"] for v in json.load(open(os.path.join(a.out, "index.json")))["vars"]]
    for vid in ids:
        out = os.path.join(a.out, vid)
        meta = json.load(open(os.path.join(out, "meta.json")))
        tiles = meta.get("tiles")
        if not tiles:
            continue
        var = meta["var"]
        opts = {}
        if var.get("thresholds"):  # uneven bands: labels at the legend values, nothing under the first
            opts = {"label_levels": {var["thresholds"].index(v) for v in var["labels"]}, "min_band": 0}
        t0 = time.time()
        for fh in meta["hours"]:
            _, packs, nbytes, secs = build_tiles.build(
                os.path.join(out, "grids", f"f{fh:02d}.i16.gz"), os.path.join(out, "tiles", f"f{fh:02d}"),
                tiles["minzoom"], tiles["maxzoom"], log=False, pack=build_tiles.live_pack_key, **opts)
            tiles["packs"][f"{fh:02d}"] = sorted("%d-%d-%d" % k for k in packs)
        with open(os.path.join(out, "meta.json"), "w") as fp:
            json.dump(meta, fp)
        print(f"{vid}: {len(meta['hours'])} hours, z{tiles['minzoom']}-{tiles['maxzoom']}, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)
