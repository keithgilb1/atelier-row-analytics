# Convenience wrapper so every target also works from the repo root.
# The real Makefile lives in atelier_analytics/.
.DEFAULT_GOAL := help

help:
	@echo "Run from the repo root or from atelier_analytics/:"
	@echo "  make setup   one time: create atelier_analytics/.venv (Python 3.12+) and install packages"
	@echo "  make all     generate data, build, validate metrics, export scorecard, run tests"
	@echo "  make ask Q=\"How are comps tracking this year?\""

%:
	@$(MAKE) --no-print-directory -C atelier_analytics $@
