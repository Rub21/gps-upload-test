"""Upload random GPX files to OSM dev as each test user.

- Round-robin across users (one upload per user, then rotate) to spread load.
- Random sleep between uploads (jitter) to avoid bot-like patterns.
- Append-only state log (state.jsonl) so the run can resume after a crash:
  any (user, gpx) pair already marked status=ok is skipped on the next run.
"""

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from envload import ROOT, load_env

load_env()

BASE = os.environ["BASE_URL"].rstrip("/")
GPX_DIR = Path(os.environ.get("GPX_DIR", ROOT / "data" / "gpx")).expanduser()
TOKENS_FILE = ROOT / os.environ.get("TOKENS_FILE", "tokens.json")
STATE_FILE = ROOT / os.environ.get("STATE_FILE", "state.jsonl")

ALL_VISIBILITIES = ["private", "public", "trackable", "identifiable"]
DEFAULT_VISIBILITIES = "trackable,identifiable"

DEFAULT_PER_USER = 5
DEFAULT_RATE_MIN = 3.0
DEFAULT_RATE_MAX = 8.0
DEFAULT_TOTAL = 0  # 0 = use per_user; >0 = cap total uploads across all users


def load_tokens() -> list[dict]:
    if not TOKENS_FILE.exists():
        sys.exit(f"tokens file not found: {TOKENS_FILE}. Run get_tokens.py first.")
    raw = json.loads(TOKENS_FILE.read_text())
    # New format (generate_token.rb): {username: token}.
    # Old format: [{"user": ..., "token": ...}, ...]. Normalize to the latter.
    if isinstance(raw, dict):
        return [{"user": user, "token": token} for user, token in raw.items()]
    return raw


def list_gpx() -> list[Path]:
    only = os.environ.get("GPX_ONLY_FOLDERS")  # e.g. "identifiable" or "identifiable,private"
    files = sorted(GPX_DIR.rglob("*.gpx"))
    if only:
        keep = [s.strip() for s in only.split(",") if s.strip()]
        files = [f for f in files if any(f"/{k}/" in str(f) for k in keep)]
    if not files:
        sys.exit(f"no .gpx files found under {GPX_DIR} (filter={only!r})")
    return files


def parse_visibilities(raw: str) -> list[str]:
    vis = [v.strip() for v in raw.split(",") if v.strip()]
    bad = [v for v in vis if v not in ALL_VISIBILITIES]
    if bad:
        sys.exit(f"unknown visibility {bad}, allowed: {ALL_VISIBILITIES}")
    if not vis:
        sys.exit("no visibility given")
    return vis


def load_state() -> set[tuple[str, str]]:
    done: set[tuple[str, str]] = set()
    if not STATE_FILE.exists():
        return done
    with STATE_FILE.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if e.get("status") == "ok":
                done.add((e["user"], e["gpx"]))
    return done


def append_state(entry: dict) -> None:
    with STATE_FILE.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
        fh.flush()


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


def build_plan(tokens: list[dict], gpx_files: list[Path], per_user: int, total: int, done: set[tuple[str, str]]) -> list[tuple[dict, Path]]:
    """Round-robin across users until per_user is reached for each, or total cap is hit.

    If total > 0, it overrides per_user and the plan stops after that many uploads
    (distributed round-robin: ceil(total / users) per user max).
    """
    n_users = len(tokens)
    if total > 0:
        per_user = (total + n_users - 1) // n_users  # ceil division

    # A file is uploaded once: skip files that any user already uploaded, and deal the rest across users.
    taken = {g for _, g in done}
    available = [g for g in gpx_files if str(g) not in taken]
    random.shuffle(available)
    picks: dict[str, list[Path]] = {}
    for i, entry in enumerate(tokens):
        user = entry["user"]
        picks[user] = available[i::n_users][:per_user]
        if len(picks[user]) < per_user:
            print(f"warn: only {len(picks[user])} unseen gpx for {user} (wanted {per_user})", file=sys.stderr)

    plan: list[tuple[dict, Path]] = []
    for round_idx in range(per_user):
        for entry in tokens:
            user = entry["user"]
            if round_idx < len(picks[user]):
                plan.append((entry, picks[user][round_idx]))
                if total > 0 and len(plan) >= total:
                    return plan
    return plan


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-user", type=int, default=DEFAULT_PER_USER, help=f"GPX uploads per user (default {DEFAULT_PER_USER}, ignored if --total > 0)")
    ap.add_argument("--total", type=int, default=DEFAULT_TOTAL, help="cap total uploads across all users (overrides --per-user)")
    ap.add_argument("--rate-min", type=float, default=DEFAULT_RATE_MIN, help=f"min seconds between uploads (default {DEFAULT_RATE_MIN})")
    ap.add_argument("--rate-max", type=float, default=DEFAULT_RATE_MAX, help=f"max seconds between uploads (default {DEFAULT_RATE_MAX})")
    ap.add_argument(
        "--visibilities",
        default=os.environ.get("VISIBILITIES", DEFAULT_VISIBILITIES),
        help=f"comma list picked at random per upload (default {DEFAULT_VISIBILITIES}; env VISIBILITIES)",
    )
    ap.add_argument("--no-resume", action="store_true", help="ignore state.jsonl, re-upload everything")
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()
    if args.seed is not None:
        random.seed(args.seed)
    if args.rate_min < 0 or args.rate_max < args.rate_min:
        sys.exit("invalid rate range")

    visibilities = parse_visibilities(args.visibilities)

    tokens = load_tokens()
    gpx_files = list_gpx()
    done = set() if args.no_resume else load_state()

    if done:
        print(f"resume: {len(done)} uploads already ok, will skip")

    plan = build_plan(tokens, gpx_files, args.per_user, args.total, done)
    if not plan:
        print("nothing to do")
        return 0
    print(f"plan: {len(plan)} uploads across {len(tokens)} users, visibility from {visibilities}")

    ok = 0
    fail = 0
    for i, (entry, gpx) in enumerate(plan, 1):
        user = entry["user"]
        token = entry["token"]
        vis = random.choice(visibilities)
        desc = f"test trace from {user}"
        tags = "test,gps-upload-test"

        ts = datetime.now(timezone.utc).isoformat()
        try:
            r = upload(token, gpx, vis, desc, tags)
            if r.ok:
                ok += 1
                trace_id = r.text.strip()
                print(f"[{i}/{len(plan)}] {user}: {gpx.name} [{vis}] -> id={trace_id}")
                append_state({"user": user, "gpx": str(gpx), "visibility": vis, "trace_id": trace_id, "status": "ok", "ts": ts})
            else:
                fail += 1
                print(f"[{i}/{len(plan)}] {user}: {gpx.name} [{vis}] FAIL {r.status_code}: {r.text[:200]}", file=sys.stderr)
                append_state({"user": user, "gpx": str(gpx), "visibility": vis, "trace_id": None, "status": "fail", "error": f"{r.status_code}: {r.text[:500]}", "ts": ts})
        except requests.RequestException as e:
            fail += 1
            print(f"[{i}/{len(plan)}] {user}: {gpx.name} EXCEPTION: {e}", file=sys.stderr)
            append_state({"user": user, "gpx": str(gpx), "visibility": vis, "trace_id": None, "status": "fail", "error": str(e), "ts": ts})

        if i < len(plan):
            time.sleep(random.uniform(args.rate_min, args.rate_max))

    print(f"\nok={ok} fail={fail} state={STATE_FILE}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
