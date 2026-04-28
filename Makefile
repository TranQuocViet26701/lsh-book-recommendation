.PHONY: help sync test notebook lint format clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Dev ──────────────────────────────

sync: ## Install all dependencies with uv
	uv sync --all-extras

test: ## Run tests
	LSH_ENV=dev uv run pytest -v

notebook: ## Start Jupyter
	LSH_ENV=dev uv run jupyter notebook notebooks/ --port 8888

lint: ## Lint with ruff
	uv run ruff check src/ tests/

format: ## Format with ruff
	uv run ruff format src/ tests/

# ── Utils ────────────────────────────

clean: ## Remove caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf data/output/ .ruff_cache/ 2>/dev/null || true
