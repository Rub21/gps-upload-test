# gps-upload-test

Upload random GPX traces to a dev OSM instance for testing.

Target: `https://rub21.apis.dev.openstreetmap.org/`

## Steps

1. **Register users** at `/user/new`. Same password for all. Names from `TEST_USER_PREFIX` / `TEST_USER_COUNT`. Emails from `TEST_USER_EMAIL_BASE` (use `+alias` trick to keep one inbox).

2. **Register OAuth2 app** as admin user → OAuth 2 applications → Register new app.
   - Redirect URI: `urn:ietf:wg:oauth:2.0:oob`
   - Scopes: `read_prefs write_gpx read_gpx`
   - Save `client_id` and `client_secret`.

3. **Get GPX samples** from `https://planet.osm.org/gps/`:
   ```bash
   mkdir -p data/gpx
   curl -L -O https://planet.osm.org/gps/gpx-planet-2013-04-09.tar.xz
   tar -xJf gpx-planet-2013-04-09.tar.xz -C data/gpx
   ```

   The dump only contains `identifiable`, `public`, `trackable` (no `private` — excluded from the public dump for privacy reasons). To also test `private` uploads, carve out a `private/` folder by moving ~10% of each type:
   ```bash
   cd data/gpx/gpx-planet-2013-04-09
   mkdir -p private
   for v in identifiable public trackable; do
     find "$v" -name '*.gpx' \
       | shuf \
       | head -n $(( $(find "$v" -name '*.gpx' | wc -l) / 10 )) \
       | xargs -I{} mv {} private/
   done
   ```

   Reference counts after the split (full dump):
   ```
   private        23,548
   identifiable  211,935
   public        546,195
   trackable      66,381
   ```

4. **Install**:
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

5. **Configure** `.env`:
   ```bash
   cp .env.example .env
   # fill in client_id, client_secret, password, email base
   ```

6. **Run**:
   ```bash
   python scripts/get_tokens.py        # writes tokens.json
   python scripts/upload_gpx.py --per-user 5
   ```

   Progress is written to `state.jsonl` after each upload (status `ok` or `fail`). Re-running the script skips any `(user, gpx)` pair already marked `ok`, so you can stop and resume freely.

## Phased rollout

The full dump has ~848K traces. 10% of that (~85K uploads) at the default rate would take days. Start small and scale up:

| Phase | Command | Approx uploads | Approx duration |
|-------|---------|----------------|-----------------|
| Smoke | `--per-user 5` | 50 | ~5 min |
| Small | `--per-user 50` | 500 | ~45 min |
| Medium | `--total 5000` | 5,000 | ~8 h |
| Big | `--total 85000` | 85,000 | ~5+ days |

Each phase reuses `state.jsonl`, so later runs continue where earlier ones stopped. Use `--no-resume` to start over.
