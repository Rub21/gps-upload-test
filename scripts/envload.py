"""Pick and load an env file for the scripts.

Lets each instance use its own config, e.g.:
    python scripts/get_tokens.py --env .env.gpxcompression

Resolution order:
    1. --env / -e PATH on the command line (stripped from argv after reading)
    2. APP_ENV_FILE environment variable
    3. .env in the project root

Relative paths resolve against the project root.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


def _take_env_arg() -> str | None:
    argv = sys.argv
    for i, a in enumerate(argv[1:], start=1):
        if a in ("--env", "-e") and i + 1 < len(argv):
            val = argv[i + 1]
            del argv[i : i + 2]
            return val
        if a.startswith("--env="):
            del argv[i]
            return a.split("=", 1)[1]
    return None


def load_env() -> Path:
    chosen = _take_env_arg() or os.environ.get("APP_ENV_FILE") or ".env"
    path = Path(chosen)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        sys.exit(f"env file not found: {path}")
    load_dotenv(path, override=True)
    print(f"env: {path.name}", file=sys.stderr)
    return path
