# Atelier Row analytics. Quick start (from this folder or the repo root):
#
#   make setup    # one time: creates .venv with Python 3.12+ and installs pinned packages
#   make all      # generate data, dbt build, validate metrics, export scorecard, run tests
#
# Targets use .venv automatically when it exists, so activating it is optional.
# To run dbt or mf by hand in a new terminal: source atelier_analytics/.venv/bin/activate

GEN_DIR := ../generator
VENV := .venv
export DBT_SEND_ANONYMOUS_USAGE_STATS := false

# Interpreter used to create the venv: the newest python3.x found, unless PYTHON is set.
PYTHON ?= $(shell for p in python3.13 python3.12 python3; do command -v $$p >/dev/null 2>&1 && { echo $$p; break; }; done)

ifneq ($(wildcard $(VENV)/bin/python),)
  BIN := $(VENV)/bin/
  PY := $(CURDIR)/$(VENV)/bin/python
else
  BIN :=
  PY ?= $(PYTHON)
endif

.PHONY: setup install data build validate scorecard test docs all ask eval clean check-python

check-python:
	@test -n "$(PYTHON)" || { echo "No python3 found. Install Python 3.12+ (macOS: brew install python@3.12)."; exit 1; }
	@$(PYTHON) -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)' || { \
	  echo "$(PYTHON) is $$($(PYTHON) --version 2>&1). This project needs Python 3.12 or newer."; \
	  echo "macOS: brew install python@3.12, then run: make setup PYTHON=python3.12"; exit 1; }

setup: check-python ## one time: create .venv and install pinned dependencies
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install -r requirements.txt
	@echo ""
	@echo "Ready. Next: make all"

install:            ## install pinned dependencies into the current Python (CI uses this)
	$(PY) -m pip install -r requirements.txt

data:               ## generate the synthetic warehouse (seed 42, about 20 seconds)
	cd "$(GEN_DIR)" && $(PY) atelier_row_generator.py

build:              ## run every model, data test and unit test
	$(BIN)dbt build --profiles-dir .

validate:           ## validate the semantic layer against the warehouse
	$(BIN)mf validate-configs

scorecard:          ## export the dashboard datasets from the semantic layer
	mkdir -p exports
	$(BIN)mf query --saved-query executive_scorecard --csv exports/executive_scorecard.csv
	$(BIN)mf query --saved-query inventory_health --csv exports/inventory_health.csv

test:               ## guardrail, agent loop and metric parity tests
	$(PY) -m pytest

docs:               ## build the dbt docs site into target/
	$(BIN)dbt docs generate --profiles-dir .

all: data build validate scorecard test

ask:                ## ask the agent: make ask Q="How are comps tracking this year?"
	$(PY) -m atelier.agent --show-sql "$(Q)"

eval:               ## score the agent against the answer key (uses the Claude API)
	$(PY) -m atelier.agent.eval

clean:              ## remove dbt build output and the built warehouse
	$(BIN)dbt clean --profiles-dir .
	rm -f atelier_analytics.duckdb
