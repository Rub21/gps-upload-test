# gps-upload-test

Upload GPX traces to a dev OSM instance for testing.

Targets:

- `osm2.geocompas.org`
- `gpsvisibility.apis.dev.openstreetmap.org`
- `gpxcompression.apis.dev.openstreetmap.org`
- `gpsdatabase.apis.dev.openstreetmap.org`

## Setup

**1. Register test users** at `/user/new`. Use the same password for all.

**2. Register an OAuth2 app** as admin → OAuth 2 applications → Register new app.

- Redirect URI: `urn:ietf:wg:oauth:2.0:oob`
- Scopes: `read_prefs write_gpx read_gpx`
- Save the `client_id` and `client_secret`.

**3. Install**

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
```

**4. Configure**

```bash
cp .env.example .env
# fill in client_id, client_secret, password, email base
```

One env file per instance. Each sets its own `BASE_URL`, OAuth app, and
`TOKENS_FILE` / `STATE_FILE`, so instances never overwrite each other:

```
.env                 default
.env.gpxcompression  -> gpxcompression.apis.dev.openstreetmap.org
.env.gpsvisibility   -> gpsvisibility.apis.dev.openstreetmap.org
```

Pick one with `--env` on any script, or set `APP_ENV_FILE` once:

```bash
python scripts/upload_gpx.py --env .env.gpxcompression --per-user 5
export APP_ENV_FILE=.env.gpxcompression
```

## Run

```bash
python scripts/get_tokens.py           # writes the tokens file
python scripts/upload_gpx.py --per-user 5
```

Progress goes to the state file after each upload (`ok` or `fail`). Re-running
skips any `(user, gpx)` pair already marked `ok`, so you can stop and resume.
Use `--no-resume` to start over.

### Tokens

By default `get_tokens.py` reads `mapper1..TEST_USER_COUNT`. Override the count
or name the users:

```bash
python scripts/get_tokens.py --count 2
python scripts/get_tokens.py --users mapper1,mapper2
```

For a single user (like `admin`), use `get_tokens_admin.py` and pass the
usernames as arguments:

```bash
python scripts/get_tokens_admin.py admin
python scripts/get_tokens_admin.py mapper3 mapper7
```

The upload scripts use whatever tokens exist in the tokens file.

## GPX samples

Sample traces are committed in `data/gpx/`, so tests work right after clone.
This includes the compression matrix (`*.gpx`, `*.gpx.gz`, `*.gpx.bz2`, `*.zip`,
`*.tar`, `*.tar.gz`, `*.tar.bz2`, single and multi-file) used by
`upload_formats.py`:

```bash
python scripts/upload_formats.py
```

For scale tests, pull the full planet dump into the same folder. The bulk
subfolders are git-ignored, so they stay local:

```bash
curl -L -O https://planet.osm.org/gps/gpx-planet-2013-04-09.tar.xz
tar -xJf gpx-planet-2013-04-09.tar.xz -C data/gpx
```

The dump has `identifiable` (211,935), `public` (546,195), and `trackable`
(66,381). There is no `private` — it is excluded from the public dump for
privacy reasons. We only upload `identifiable/`; the rest is kept for reference.

## Phased rollout

`identifiable/` has ~212K traces. 10% of that (~21K uploads) at the default rate
takes days, so start small:

| Phase | Command | Uploads | Duration |
|-------|---------|---------|----------|
| Smoke | `--per-user 5` | 50 | ~5 min |
| Small | `--per-user 50` | 500 | ~45 min |
| Medium | `--total 5000` | 5,000 | ~8 h |

Each phase reuses `state.jsonl`, so later runs continue where earlier ones
stopped.
