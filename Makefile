.PHONY: help sync test run api ui docker notebook lint format clean

MASTER_HOST ?= master
MASTER_USER ?= user

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Dev ──────────────────────────────

sync: ## Install all dependencies with uv
	uv sync --all-extras

test: ## Run tests
	LSH_ENV=dev uv run pytest -v

run: ## Run ingestion pipeline (dev)
	LSH_ENV=dev uv run python -m src.main

query: ## Query similar books — make query BOOK=pg1234
	LSH_ENV=dev uv run python -m src.main query $(BOOK) 10

api: ## Start FastAPI
	LSH_ENV=dev uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

ui: ## Start Streamlit
	LSH_ENV=dev uv run streamlit run frontend/app.py --server.port 8501

notebook: ## Start Jupyter
	LSH_ENV=dev uv run jupyter notebook notebooks/ --port 8888

docker: ## Start Docker dev env
	docker compose -f docker/docker-compose.yml up -d

download-sample: ## Download 100-book sample dataset
	uv run python -m scripts.generate_sample_dataset

download-gutenberg: ## Download books from Gutenberg — make download-gutenberg NUM=500
	uv run python -m scripts.download_and_upload_gutenberg \
		--num-books $(or $(NUM),100) --output-dir ./data/raw

lint: ## Lint with ruff
	uv run ruff check src/ api/ tests/

format: ## Format with ruff
	uv run ruff format src/ api/ tests/

# ── Cluster ──────────────────────────

cluster-deploy: ## Sync code to master
	rsync -avz --exclude '.git' --exclude 'data' --exclude '__pycache__' \
		--exclude '.venv' --exclude 'uv.lock' \
		. $(MASTER_USER)@$(MASTER_HOST):~/project-lsh/

cluster-upload: ## Upload data to HDFS
	ssh $(MASTER_USER)@$(MASTER_HOST) "hdfs dfs -mkdir -p /project-lsh/datasets/gutenberg_default/raw/ && \
		hdfs dfs -put -f ~/data/raw/*.txt /project-lsh/datasets/gutenberg_default/raw/"

cluster-run: ## Run pipeline on cluster
	ssh $(MASTER_USER)@$(MASTER_HOST) "cd ~/project-lsh && LSH_ENV=cluster spark-submit \
		--master spark://master:7077 --executor-memory 4g src/main.py"

cluster-ui: ## Start Streamlit on cluster
	ssh $(MASTER_USER)@$(MASTER_HOST) "cd ~/project-lsh && LSH_ENV=cluster \
		nohup streamlit run frontend/app.py --server.port 8501 &"

# ── Utils ────────────────────────────

clean: ## Remove caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf data/output/ .ruff_cache/ 2>/dev/null || true
