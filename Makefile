.DEFAULT_GOAL := help
PY ?= python

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install the package with dev + api extras
	pip install -e ".[api,dev]"

demo: ## Run the full pipeline locally (no Docker, no keys) then print next steps
	$(PY) scripts/seed_demo.py

serve: ## Start the API + dashboard on :8000
	uvicorn api.main:app --host 0.0.0.0 --port 8000

pipeline: ## Run ingest -> lake -> ML -> dbt end to end
	$(PY) -m techtrend.pipeline

test: ## Run the test suite
	pytest

lint: ## Ruff lint + format check
	ruff check src api tests scripts
	ruff format --check src api tests scripts

typecheck: ## mypy static analysis
	mypy src

dbt-docs: ## Build and serve dbt lineage docs
	cd dbt/techtrend_dw && dbt docs generate --profiles-dir profiles && dbt docs serve --profiles-dir profiles

up: ## Start the full Docker stack (API, Airflow, MLflow, Prometheus, Grafana)
	docker compose up -d --build

down: ## Stop the Docker stack
	docker compose down
