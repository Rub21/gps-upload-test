# gps-upload-test

Upload GPX traces to a test OSM instance (osm-dev on the dev server by default).

```bash
make setup                        # .venv, requirements, .env
make tokens SLUG=gpx-tracks       # copies the user tokens from the osm-dev server
make upload PER_USER=5            # 5 traces per user
```

`make` lists the targets. Progress is saved in the state file after each upload, so a run can stop and continue. `--no-resume` starts over.

## Config

`make setup` copies `.env.example` to `.env`. Only these are needed for osm-dev:

| variable | what |
|---|---|
| `BASE_URL` | instance URL, for example `https://gpx-tracks.rub21.com` |
| `SERVER` | where osm-dev runs, `root@ip`, or `local` for `../osm-dev` |
| `GPX_DIR` | folder with the traces, default `./data/gpx` |
| `GPX_ONLY_FOLDERS` | subfolders of `GPX_DIR` to use, default `identifiable` |
| `VISIBILITIES` | picked at random per upload: `private`, `public`, `trackable`, `identifiable` |
| `TOKENS_FILE` | default `./tokens.json` |
| `STATE_FILE` | default `./state.jsonl` |

One file per instance: `.env.gpx-tracks`, `.env.gpx-soft-delete`, each with its own `BASE_URL`, `SERVER` and `STATE_FILE`. Pass it with `ENV=`:

```bash
make tokens SLUG=gpx-soft-delete ENV=.env.gpx-soft-delete
make upload TOTAL=100 ENV=.env.gpx-soft-delete
```

`CLIENT_ID`, `CLIENT_SECRET`, `REDIRECT_URI`, `SCOPES`, `TEST_USERS` and `TEST_USER_PASSWORD` are only for instances that are not osm-dev, see below.

## Tokens

osm-dev creates OAuth tokens for `admin`, `Rub21`, `mapper1..3` on every start and writes them to `.tokens/<slug>.json`. `make tokens` copies that file here as `tokens.json`. osm-dev regenerates the tokens when a container is recreated, so run `make tokens` again after `make up`.

For an instance that is not osm-dev (for example `*.apis.dev.openstreetmap.org`): register an OAuth 2 app there with redirect `urn:ietf:wg:oauth:2.0:oob` and scopes `read_prefs write_gpx read_gpx`, fill `CLIENT_ID`, `CLIENT_SECRET`, `TEST_USERS` and `TEST_USER_PASSWORD` in the env file, then:

```bash
.venv/bin/playwright install chromium
.venv/bin/python3 scripts/get_tokens.py --env .env.other
```

## Traces

Put GPX files in `data/gpx/<folder>/` (gitignored). Two ways to get real data:

```bash
# public points of a bbox from openstreetmap.org, 5 pages per tile
.venv/bin/python3 scripts/fetch_bbox.py --name amsterdam --bbox 4.75,52.28,5.05,52.45 --pages 5

# the 2013 planet dump: identifiable/, public/ and trackable/
curl -L -O https://planet.osm.org/gps/gpx-planet-2013-04-09.tar.xz
tar -xJf gpx-planet-2013-04-09.tar.xz -C data/gpx
```

`make upload` takes `PER_USER=N` or `TOTAL=N`. Each file is uploaded once, spread across the users. `make formats` uploads the compression matrix once (`gpx`, `gz`, `bz2`, `zip`, `tar`).
