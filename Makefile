# Convenience wrapper so every target also works from the repo root.
# The analytics Makefile lives in atelier_analytics/; the dashboard targets live here.
.DEFAULT_GOAL := help

help:
	@echo "Run from the repo root or from atelier_analytics/:"
	@echo "  make setup            one time: create atelier_analytics/.venv (Python 3.12+) and install packages"
	@echo "  make all              generate data, build, validate metrics, export scorecard, run tests"
	@echo "  make ask Q=\"How are comps tracking this year?\""
	@echo ""
	@echo "Dashboard (needs Node 20+; macOS: brew install node):"
	@echo "  make dashboard        open the React dashboard at http://localhost:5173"
	@echo "  make dashboard-data   refresh the dashboard's data from the semantic layer"
	@echo "  make dashboard-build  build the static site into dashboard/dist"

.PHONY: help dashboard dashboard-build dashboard-install check-node

check-node:
	@command -v npm >/dev/null 2>&1 || { echo "Node.js is not installed. macOS: brew install node"; exit 1; }

dashboard/node_modules: dashboard/package-lock.json | check-node
	cd dashboard && npm ci
	@touch $@

dashboard-install: dashboard/node_modules

dashboard: dashboard-install
	cd dashboard && npm run dev

dashboard-build: dashboard-install
	cd dashboard && npm run build

%:
	@$(MAKE) --no-print-directory -C atelier_analytics $@
