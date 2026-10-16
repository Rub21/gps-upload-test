# gps-upload-test. `make` lists the targets.
.DEFAULT_GOAL := help

SLUG   ?= gpx-tracks
ENV    ?= .env
# SERVER comes from $(ENV) (SERVER=root@ip, or SERVER=local). Command line wins.
SERVER ?= $(shell grep -s '^SERVER=' $(ENV) | cut -d= -f2-)
PY      = .venv/bin/python3

.PHONY: help setup tokens upload formats

help: ## Show this help
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

setup: ## Create .venv, install requirements, copy .env.example to .env if missing
	@test -d .venv || python3 -m venv .venv
	@$(PY) -m pip install -q -r requirements.txt
	@test -f .env || cp .env.example .env
	@echo "ok. edit .env if the instance is not $(SLUG)"

tokens: ## Copy the user tokens of an osm-dev instance: make tokens [SLUG=gpx-tracks] [SERVER=root@ip | SERVER=local]
ifeq ($(strip $(SERVER)),)
	$(error SERVER is not set. Add SERVER=root@ip (or SERVER=local) to $(ENV), or pass it: make tokens SERVER=root@ip)
else ifeq ($(SERVER),local)
	@cp ../osm-dev/.tokens/$(SLUG).json tokens.json
else
	@ssh $(SERVER) 'cat ~/osm-dev/.tokens/$(SLUG).json' > tokens.json
endif
	@echo "tokens.json: $$($(PY) -c 'import json;print(", ".join(json.load(open("tokens.json"))))')"

upload: tokens.json ## Upload traces: make upload PER_USER=5 [VISIBILITIES=trackable,identifiable] [ENV=.env.other]
	@$(PY) scripts/upload_gpx.py --env $(ENV) $(if $(PER_USER),--per-user $(PER_USER)) $(if $(TOTAL),--total $(TOTAL)) $(if $(VISIBILITIES),--visibilities $(VISIBILITIES))

formats: tokens.json ## Upload the compression matrix (gpx, gz, bz2, zip, tar) once
	@$(PY) scripts/upload_formats.py --env $(ENV)

tokens.json:
	@echo "no tokens.json, run: make tokens" && exit 1
