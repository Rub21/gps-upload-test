"""Upload one of every compression format to OSM dev and report status.

Goal: check that the API accepts each allowed container/compression combo
(plain gpx, gz, bz2, zip, tar, tar.gz, tar.bz2; single and multi file).

Uploads each file in gps-formats/ once, as a single user, and prints a small
result table. This does not touch state.jsonl; it is a one-shot format probe.
"""

import json
import mimetypes
import os
import sys
from pathlib import Path

import requests

from envload import ROOT, load_env

load_env()

BASE = os.environ["BASE_URL"].rstrip("/")
TOKENS_FILE = ROOT / os.environ.get("TOKENS_FILE", "tokens.json")
# top-level files in GPX_DIR are the compression matrix; bulk planet dump
# lives in subfolders (identifiable/ ...) and is skipped by iterdir().
FORMATS_DIR = Path(os.environ.get("GPX_DIR", ROOT / "data" / "gpx")).expanduser()

# content type per extension; OSM decides decompression from the filename
CONTENT_TYPES = {
    ".gpx": "application/gpx+xml",
    ".gz": "application/gzip",
    ".bz2": "application/x-bzip2",
    ".zip": "application/zip",
    ".tar": "application/x-tar",
}


def content_type(path: Path) -> str:
    return CONTENT_TYPES.get(path.suffix, "application/octet-stream")


def upload(token: str, path: Path, visibility: str) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"}
    with path.open("rb") as fh:
        files = {"file": (path.name, fh, content_type(path))}
        data = {
            "description": f"format test {path.name}",
            "tags": "test,format-test",
            "visibility": visibility,
        }
        return requests.post(
            f"{BASE}/api/0.6/gpx/create",
            headers=headers,
            files=files,
            data=data,
            timeout=120,
        )


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--visibility",
        default="identifiable",
        choices=["private", "public", "trackable", "identifiable"],
        help="visibility for every upload (default identifiable)",
    )
    args = ap.parse_args()

    raw = json.loads(TOKENS_FILE.read_text())
    # New format: {username: token}. Old format: [{"user": ..., "token": ...}].
    tokens = [{"user": u, "token": t} for u, t in raw.items()] if isinstance(raw, dict) else raw
    if not tokens:
        sys.exit(f"no tokens in {TOKENS_FILE}. Run get_tokens.py first.")
    token = tokens[0]["token"]
    user = tokens[0]["user"]

    files = sorted(p for p in FORMATS_DIR.iterdir() if p.is_file())
    # skip the raw source members used only to build the archives
    files = [p for p in files if p.name not in {"2.gpx"}]
    if not files:
        sys.exit(f"no files in {FORMATS_DIR}")

    print(f"uploading {len(files)} formats as {user} [{args.visibility}] -> {BASE}\n")
    rows = []
    for p in files:
        try:
            r = upload(token, p, args.visibility)
            ok = r.ok
            detail = r.text.strip()[:80] if ok else f"{r.status_code}: {r.text.strip()[:80]}"
        except requests.RequestException as e:
            ok = False
            detail = f"EXC: {e}"
        rows.append((p.name, ok, detail))
        print(f"{'OK ' if ok else 'ERR'}  {p.name:24} {detail}")

    n_ok = sum(1 for _, ok, _ in rows if ok)
    print(f"\nok={n_ok} fail={len(rows) - n_ok}")
    return 0 if n_ok == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())
