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
