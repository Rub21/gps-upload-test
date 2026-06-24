"""Headless OAuth2 authorization code flow for test users.

For each test user:
  1. Log in via /login.
  2. Visit /oauth2/authorize and click Authorize.
  3. Read the displayed authorization code (out-of-band redirect).
  4. Exchange the code for an access token at /oauth2/token.

Writes the resulting {user, token} pairs to tokens.json.
"""

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

BASE = os.environ["BASE_URL"].rstrip("/")
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
REDIRECT = os.environ.get("REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob")
SCOPES = os.environ.get("SCOPES", "read_prefs write_gpx read_gpx")
PREFIX = os.environ.get("TEST_USER_PREFIX", "mapper")
COUNT = int(os.environ.get("TEST_USER_COUNT", "10"))
PASSWORD = os.environ["TEST_USER_PASSWORD"]
TOKENS_FILE = ROOT / os.environ.get("TOKENS_FILE", "tokens.json")


def extract_code(html: str) -> str | None:
    # The oob view shows the code inside <code>...</code> or in an input value.
    for pat in (
        r"<code[^>]*>([A-Za-z0-9_\-]{20,})</code>",
        r'name="code"[^>]*value="([A-Za-z0-9_\-]{20,})"',
        r'value="([A-Za-z0-9_\-]{20,})"[^>]*name="code"',
    ):
        m = re.search(pat, html)
        if m:
            return m.group(1)
    return None


def fetch_token(username: str, browser) -> dict | None:
    ctx = browser.new_context()
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/login")
        page.fill('input[name="username"]', username)
        page.fill('input[name="password"]', PASSWORD)
        page.click('input[type="submit"]')
        page.wait_for_load_state("networkidle")

        auth_url = (
            f"{BASE}/oauth2/authorize"
            f"?response_type=code"
            f"&client_id={quote(CLIENT_ID)}"
            f"&redirect_uri={quote(REDIRECT)}"
            f"&scope={quote(SCOPES)}"
        )
        page.goto(auth_url)
        page.wait_for_load_state("networkidle")

        # If app was already authorized, the oob code page loads directly.
        authorize_btn = page.locator('input[type="submit"][value="Authorize"]')
        if authorize_btn.count():
            authorize_btn.first.click()
            page.wait_for_load_state("networkidle")

        code = extract_code(page.content())
        if not code:
            print(f"{username}: authorization code not found in page", file=sys.stderr)
            return None

        r = requests.post(
            f"{BASE}/oauth2/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT,
            },
            timeout=30,
        )
        r.raise_for_status()
        token = r.json().get("access_token")
        if not token:
            print(f"{username}: token missing in response: {r.text}", file=sys.stderr)
            return None
        return {"user": username, "token": token}
    finally:
        ctx.close()


def main() -> int:
    # If a username is passed as an argument, generate a token only for that
    # user; otherwise fall back to the full PREFIX1..PREFIXn range.
    if len(sys.argv) > 1:
        users = sys.argv[1:]
    else:
        users = [f"{PREFIX}{i}" for i in range(1, COUNT + 1)]
    tokens: list[dict] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for u in users:
                entry = fetch_token(u, browser)
                if entry:
                    tokens.append(entry)
                    print(f"{u}: {entry['token'][:12]}...")
        finally:
            browser.close()
    TOKENS_FILE.write_text(json.dumps(tokens, indent=2))
    print(f"\nWrote {len(tokens)} tokens to {TOKENS_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
