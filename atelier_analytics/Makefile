# Atelier Row analytics. Run `make all` from this folder after `make install`.
PY ?= python
GEN_DIR := ../generator
export DBT_SEND_ANONYMOUS_USAGE_STATS := false

.PHONY: install data build validate scorecard test docs all ask eval clean

install:            ## install pinned dependencies
	$(PY) -m pip install -r requirements.txt

data:               ## generate the synthetic warehouse (seed 42, about 20 seconds)
	cd "$(GEN_DIR)" && $(PY) atelier_row_generator.py

build:              ## run every model, data test and unit test
	dbt build --profiles-dir .

validate:           ## validate the semantic layer against the warehouse
	mf validate-configs

scorecard:          ## export the dashboard datasets from the semantic layer
	mkdir -p exports
	mf query --saved-query executive_scorecard --csv exports/executive_scorecard.csv
	mf query --saved-query inventory_health --csv exports/inventory_health.csv

test:               ## guardrail, agent loop and metric parity tests
	$(PY) -m pytest

docs:               ## build the dbt docs site into target/
	dbt docs generate --profiles-dir .

all: data build validate scorecard test

ask:                ## ask the agent: make ask Q="How are comps tracking this year?"
	$(PY) -m atelier.agent --show-sql "$(Q)"

eval:               ## score the agent against the answer key (uses the Claude API)
	$(PY) -m atelier.agent.eval

clean:
	dbt clean --profiles-dir . && rm -f atelier_analytics.duckdb
