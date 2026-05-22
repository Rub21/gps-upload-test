"""Upload random GPX files to OSM dev as each test user.

Reads tokens.json produced by get_tokens.py, picks random files from data/gpx,
and POSTs them to /api/0.6/gpx/create with a random visibility level.
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BASE = os.environ["BASE_URL"].rstrip("/")
GPX_DIR = Path(os.environ.get("GPX_DIR", ROOT / "data" / "gpx")).expanduser()
TOKENS_FILE = ROOT / os.environ.get("TOKENS_FILE", "tokens.json")

VISIBILITIES = ["private", "public", "trackable", "identifiable"]


def load_tokens() -> list[dict]:
    if not TOKENS_FILE.exists():
        sys.exit(f"tokens file not found: {TOKENS_FILE}. Run get_tokens.py first.")
    return json.loads(TOKENS_FILE.read_text())


def list_gpx() -> list[Path]:
    files = sorted(GPX_DIR.rglob("*.gpx"))
    if not files:
        sys.exit(f"no .gpx files found under {GPX_DIR}")
    return files


def upload(token: str, gpx_path: Path, visibility: str, description: str, tags: str) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"}
    with gpx_path.open("rb") as fh:
        files = {"file": (gpx_path.name, fh, "application/gpx+xml")}
        data = {"description": description, "tags": tags, "visibility": visibility}
        return requests.post(
            f"{BASE}/api/0.6/gpx/create",
            headers=headers,
            files=files,
            data=data,
            timeout=120,
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-user", type=int, default=3, help="GPX uploads per user")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    tokens = load_tokens()
    gpx_files = list_gpx()

    total_ok = 0
    total_fail = 0
    for entry in tokens:
        user = entry["user"]
        token = entry["token"]
        for _ in range(args.per_user):
            gpx = random.choice(gpx_files)
            vis = random.choice(VISIBILITIES)
            desc = f"test trace from {user}"
            tags = "test,gps-upload-test"
            r = upload(token, gpx, vis, desc, tags)
            if r.ok:
                total_ok += 1
                print(f"{user}: {gpx.name} [{vis}] -> id={r.text.strip()}")
            else:
                total_fail += 1
                print(f"{user}: {gpx.name} [{vis}] FAILED {r.status_code}: {r.text[:200]}", file=sys.stderr)

    print(f"\nok={total_ok} fail={total_fail}")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
