# Makefile — wc2026-predictor local dev helpers
# Requires: Python 3.12+, Node 22+, npm
# All targets assume the repo root is the working directory.
#
# Usage:
#   make dev       — start backend (port 8000) and frontend (port 5173) concurrently
#   make retrain   — re-fit the Poisson model (writes data/POST.json, ~5-30s, needs internet)
#   make test      — run pytest + vitest
#   make lint      — ruff + eslint + tsc --noEmit

SHELL := /bin/bash
.DEFAULT_GOAL := help

# ── Python venv detection ─────────────────────────────────────────────────────
# If backend/.venv exists, prefer it. Otherwise fall through to system python.
VENV_PYTHON := $(shell [ -d backend/.venv ] && echo "backend/.venv/bin/python" || echo "python")
VENV_PIP    := $(shell [ -d backend/.venv ] && echo "backend/.venv/bin/pip" || echo "pip")
PYTEST      := $(shell [ -d backend/.venv ] && echo "backend/.venv/bin/pytest" || echo "pytest")
UVICORN     := $(shell [ -d backend/.venv ] && echo "backend/.venv/bin/uvicorn" || echo "uvicorn")
RUFF        := $(shell [ -d backend/.venv ] && echo "backend/.venv/bin/ruff" || echo "ruff")

# ── Targets ───────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## Install all dependencies (backend venv + frontend node_modules)
	cd backend && python -m venv .venv && .venv/bin/pip install --upgrade pip && .venv/bin/pip install -r requirements.txt
	cd frontend && npm ci

.PHONY: dev
dev: ## Start backend (uvicorn --reload) + frontend (vite dev) in parallel
	@echo "Starting backend on http://127.0.0.1:8000 and frontend on http://localhost:5173"
	@echo "Press Ctrl-C to stop both."
	@trap 'kill 0' INT; \
	$(UVICORN) backend.app.main:app --reload --host 127.0.0.1 --port 8000 & \
	(cd frontend && npm run dev) & \
	wait

.PHONY: retrain
retrain: ## Re-fit the Poisson model (downloads match history, writes data/POST.json)
	$(VENV_PYTHON) retrain.py

.PHONY: retrain-via-api
retrain-via-api: ## Trigger retrain via the API (requires backend running, optional RETRAIN_TOKEN)
	@if [ -n "$$RETRAIN_TOKEN" ]; then \
	  curl -fsSL -X POST http://127.0.0.1:8000/model/retrain \
	    -H "Authorization: Bearer $$RETRAIN_TOKEN" \
	    -H "Content-Type: application/json" \
	    -d '{"half_life": 3.0, "n_draws": 400}'; \
	else \
	  curl -fsSL -X POST http://127.0.0.1:8000/model/retrain \
	    -H "Content-Type: application/json" \
	    -d '{"half_life": 3.0, "n_draws": 400}'; \
	fi

.PHONY: test
test: test-backend test-frontend ## Run all tests (pytest + vitest)

.PHONY: test-backend
test-backend: ## Run pytest with coverage
	$(PYTEST) backend/tests/ -v --cov=backend/app --cov-report=term-missing --cov-fail-under=80

.PHONY: test-frontend
test-frontend: ## Run vitest unit tests
	cd frontend && npm run test -- --reporter=verbose

.PHONY: test-e2e
test-e2e: ## Run Playwright E2E tests (requires both servers running)
	cd frontend && npx playwright test

.PHONY: lint
lint: lint-backend lint-frontend ## Run all linters (ruff + eslint + tsc)

.PHONY: lint-backend
lint-backend: ## ruff check + ruff format check + mypy
	$(RUFF) check backend/
	$(RUFF) format --check backend/
	$(VENV_PYTHON) -m mypy backend/app/ --strict

.PHONY: lint-frontend
lint-frontend: ## ESLint + tsc --noEmit
	cd frontend && npm run lint
	cd frontend && npm run typecheck

.PHONY: audit
audit: audit-backend audit-frontend ## Run dependency security audits

.PHONY: audit-backend
audit-backend: ## pip-audit on backend dependencies
	$(VENV_PYTHON) -m pip_audit -r backend/requirements.txt

.PHONY: audit-frontend
audit-frontend: ## npm audit on frontend dependencies
	cd frontend && npm audit --audit-level=moderate

.PHONY: sbom
sbom: ## Generate CycloneDX SBOM for backend and frontend
	$(VENV_PYTHON) -m cyclonedx_py requirements backend/requirements.txt --of json -o sbom-backend.json
	cd frontend && npx --yes @cyclonedx/cyclonedx-npm --output-file ../sbom-frontend.json
	@echo "SBOM written: sbom-backend.json + sbom-frontend.json"

.PHONY: research
research: ## Run all three research scripts (bivariate, halflife, market_edge)
	$(VENV_PYTHON) -m backend.app.research.bivariate_vs_independent
	$(VENV_PYTHON) -m backend.app.research.halflife_sensitivity
	$(VENV_PYTHON) -m backend.app.research.market_edge_today
	@echo "Research outputs written to research/"

.PHONY: clean
clean: ## Remove build artefacts, caches, coverage reports
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage coverage.xml
	rm -rf frontend/dist/ frontend/.vite/ frontend/.react-router/
	rm -rf playwright-report/ test-results/
