#!/usr/bin/env python3
"""Download public GPS points of a bbox from openstreetmap.org and save them as GPX files.

- Reads GET /api/0.6/trackpoints?bbox=...&page=N (5000 points per page).
- The bbox is split in tiles (--tile degrees). A large bbox times out on the API (503).
- Writes one file per trace: identifiable traces to <out>/identifiable/<name>/<trace_id>.gpx
  (merged across pages), trackable ones to <out>/trackable/<name>/.
- Points without <time> (public/private traces) are skipped, the upload API rejects them.

Example:
  python3 scripts/fetch_bbox.py --name amsterdam --bbox 4.75,52.28,5.05,52.45 --pages 5
"""
from __future__ import annotations

import argparse
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.openstreetmap.org/api/0.6/trackpoints"
NS = "http://www.topografix.com/GPX/1/0"
MAX_BBOX_AREA = 0.25  # square degrees, API limit
MIN_POINTS = 10

ET.register_namespace("", NS)


def q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def timed_segments(trk: ET.Element) -> list[ET.Element]:
    """Copy of the trk segments, keeping only points that have a <time>."""
    segs = []
    for seg in trk.findall(q("trkseg")):
        new = ET.Element(q("trkseg"))
        new.extend(pt for pt in seg.findall(q("trkpt")) if pt.find(q("time")) is not None)
        if len(new):
            segs.append(new)
    return segs


def write_gpx(path: Path, name: str, segs: list[ET.Element]) -> int:
    n = sum(len(s) for s in segs)
    if n < MIN_POINTS:
        return 0
    gpx = ET.Element(q("gpx"), {"version": "1.0", "creator": "gps-upload-test"})
    trk = ET.SubElement(gpx, q("trk"))
    ET.SubElement(trk, q("name")).text = name
    trk.extend(segs)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(gpx).write(path, encoding="utf-8", xml_declaration=True)
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bbox", required=True, help="min_lon,min_lat,max_lon,max_lat")
    ap.add_argument("--name", required=True, help="subfolder name, e.g. amsterdam")
    ap.add_argument("--tile", type=float, default=0.1, help="tile size in degrees (default 0.1)")
    ap.add_argument("--pages", type=int, default=5, help="pages to read per tile, 5000 points each (default 5)")
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between requests (default 2)")
    ap.add_argument("--out", default=str(ROOT / "data" / "gpx"))
    args = ap.parse_args()

    w, s, e, n = (float(v) for v in args.bbox.split(","))
    if args.tile <= 0 or args.tile * args.tile > MAX_BBOX_AREA:
        sys.exit(f"tile must be > 0 and at most {MAX_BBOX_AREA} square degrees")
    tiles = []
    y = s
    while y < n - 1e-9:
        x = w
        while x < e - 1e-9:
            tiles.append((x, y, min(x + args.tile, e), min(y + args.tile, n)))
            x += args.tile
        y += args.tile

    out = Path(args.out)
    identifiable: dict[str, tuple[str, list[ET.Element]]] = {}  # trace_id -> (name, segments)
    trackable = 0
    points = 0

    for t, tile in enumerate(tiles):
        bbox = ",".join(f"{v:.5f}" for v in tile)
        for page in range(args.pages):
            try:
                r = requests.get(API, params={"bbox": bbox, "page": page}, headers={"User-Agent": "gps-upload-test"}, timeout=300)
            except requests.RequestException as ex:
                print(f"tile {t} page {page}: EXCEPTION {ex}", file=sys.stderr)
                break
            if not r.ok:
                print(f"tile {t} page {page}: FAIL {r.status_code}", file=sys.stderr)
                break
            trks = ET.fromstring(r.content).findall(q("trk"))
            if not trks:
                break
            for i, trk in enumerate(trks):
                segs = timed_segments(trk)
                if not segs:
                    continue
                url = trk.findtext(q("url"))
                if url:
                    trace_id = url.rstrip("/").rsplit("/", 1)[-1]
                    name = trk.findtext(q("name")) or f"{trace_id}.gpx"
                    identifiable.setdefault(trace_id, (name, []))[1].extend(segs)
                else:
                    path = out / "trackable" / args.name / f"t{t:03d}_p{page:03d}_{i:03d}.gpx"
                    got = write_gpx(path, path.name, segs)
                    points += got
                    trackable += 1 if got else 0
            print(f"tile {t + 1}/{len(tiles)} [{bbox}] page {page}: {len(trks)} trk, identifiable so far {len(identifiable)}, trackable files {trackable}")
            time.sleep(args.sleep)

    saved = 0
    for trace_id, (name, segs) in identifiable.items():
        got = write_gpx(out / "identifiable" / args.name / f"{trace_id}.gpx", name, segs)
        points += got
        saved += 1 if got else 0

    print(f"\nidentifiable={saved} trackable={trackable} points={points} out={out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
