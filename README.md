# gps-upload-test

Upload random GPX traces to a dev OSM instance for testing.

Targets:

 - `osm2.geocompas.org`
 - `gpsvisibility.apis.dev.openstreetmap.org`
 - `gpxcompression.apis.dev.openstreetmap.org`
 - `gpsdatabase.apis.dev.openstreetmap.org`

## Steps

1. **Register users** at `/user/new`. Same password for all.

2. **Register OAuth2 app** as admin user → OAuth 2 applications → Register new app.
   - Redirect URI: `urn:ietf:wg:oauth:2.0:oob`
   - Scopes: `read_prefs write_gpx read_gpx`
   - Save `client_id` and `client_secret`.

3. **GPX samples.** A small set of sample traces is committed in `data/gpx/`, so
   tests work right after clone — no download needed. This includes the
   compression matrix (`*.gpx`, `*.gpx.gz`, `*.gpx.bz2`, `*.zip`, `*.tar`,
   `*.tar.gz`, `*.tar.bz2`, single and multi-file) used by `upload_formats.py`.

   For scale tests you can pull the full planet dump into the same folder. The
   bulk subfolders are git-ignored, so they stay local:
   ```bash
   curl -L -O https://planet.osm.org/gps/gpx-planet-2013-04-09.tar.xz
   tar -xJf gpx-planet-2013-04-09.tar.xz -C data/gpx
   ```

   The dump contains `identifiable`, `public`, and `trackable` (no `private` — excluded from the public dump for privacy reasons).

   Reference counts (full dump):
   ```
   identifiable  211,935
   public        546,195
   trackable      66,381
   ```

   For our tests, only `identifiable/` is uploaded. The other folders are kept for reference but not used.

4. **Install**:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   playwright install-deps chromium   # system libs (libnspr4, libnss3, ...)
   ```

   If `install-deps` fails to detect the distro, install the libs manually as root:
   ```bash
   apt-get update && apt-get install -y \
     libnspr4 libnss3 libnssutil3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
     libcups2 libdrm2 libatspi2.0-0 libxcomposite1 libxdamage1 libxfixes3 \
     libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 libcairo2 libasound2
   ```

5. **Configure** `.env`:
   ```bash
   cp .env.example .env
   # fill in client_id, client_secret, password, email base
   ```

   One env file per instance. Each one sets its own `BASE_URL`, OAuth app, and
   `TOKENS_FILE` / `STATE_FILE`, so instances never clobber each other:
   ```
   .env                  default
   .env.gpxcompression    -> gpxcompression.apis.dev.openstreetmap.org
   .env.gpsvisibility     -> gpsvisibility.apis.dev.openstreetmap.org
   ```

6. **Run**:
   ```bash
   python scripts/get_tokens.py        # writes the tokens file
   python scripts/upload_gpx.py --per-user 5
   ```

   To generate a token for a **single user** (or a specific list), pass the
   username(s) as arguments — without arguments it uses the full
   `TEST_USER_PREFIX` / `TEST_USER_COUNT` range:
   ```bash
   python scripts/get_tokens_admin.py admin          # just "admin"
   python scripts/get_tokens_admin.py mapper3 mapper7 # a specific list
   ```

   **Pick an env file** with `--env` (default `.env`). All three scripts accept it:
   ```bash
   python scripts/get_tokens.py    --env .env.gpxcompression
   python scripts/upload_gpx.py    --env .env.gpxcompression --per-user 5
   python scripts/upload_formats.py --env .env.gpxcompression
   ```
   You can also set it once via the `APP_ENV_FILE` environment variable:
   ```bash
   export APP_ENV_FILE=.env.gpxcompression
   python scripts/get_tokens.py
   ```

   **Fewer users.** By default `get_tokens.py` reads `mapper1..TEST_USER_COUNT`.
   Override how many, or name them explicitly:
   ```bash
   python scripts/get_tokens.py --env .env.gpxcompression --count 2
   python scripts/get_tokens.py --env .env.gpxcompression --users mapper1,mapper2
   ```
   The upload scripts just use whatever tokens exist in the tokens file.

   Progress is written to the state file after each upload (status `ok` or `fail`). Re-running the script skips any `(user, gpx)` pair already marked `ok`, so you can stop and resume freely.

## Phased rollout

The `identifiable/` folder has ~212K traces. 10% of that (~21K uploads) at the default rate would take days. Start small and scale up:

| Phase | Command | Approx uploads | Approx duration |
|-------|---------|----------------|-----------------|
| Smoke | `--per-user 5` | 50 | ~5 min |
| Small | `--per-user 50` | 500 | ~45 min |
| Medium | `--total 5000` | 5,000 | ~8 h |
| Big | `--total 21000` | 21,000 | ~5+ days |

Each phase reuses `state.jsonl`, so later runs continue where earlier ones stopped. Use `--no-resume` to start over.
