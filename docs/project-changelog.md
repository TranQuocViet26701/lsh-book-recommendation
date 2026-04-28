# Project Changelog

All notable changes to this project are documented in this file. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.2.0] — 2026-04-28

### Changed
- Migrated experiment runtime from local Spark / planned HDFS cluster to **Databricks Free Edition (Serverless)** for the course report.
- Refactored `src/preprocessing.py::create_spark_session()` to be Databricks-aware: returns `SparkSession.getActiveSession()` when an injected `spark` exists; otherwise builds a local session honoring config-driven master/memory.
- Refactored `src/preprocessing.py::_ensure_nltk_stopwords()` to honor the `NLTK_DATA` env var so the pre-bundled corpus on a UC Volume is discovered without `nltk.download()`.
- All 5 notebooks now share a single Databricks-aware setup preamble that auto-detects `_in_databricks`, sets `LSH_ENV` + `NLTK_DATA`, and walks `sys.path` to repo root (Repos clone path or local `..`).
- Notebook 04 aggregate cell now writes `experiment_results.csv` to `config.DATA_OUTPUT_PATH` instead of a hardcoded local path.
- README rewritten: Databricks Free Edition is the primary Quick Start; local dev is now the secondary path.
- `docs/system-architecture.md` and `docs/codebase-summary.md` rewritten to reflect post-migration reality.

### Added
- `config/settings.py::DatabricksConfig` — UC Volume paths via `LSH_DBX_CATALOG` / `LSH_DBX_SCHEMA` / `LSH_DBX_VOLUME` env vars (defaults: `workspace` / `lsh_book_recommendation` / `data`).
- `scripts/bootstrap-nltk-stopwords-to-volume.py` — local helper that pre-downloads the NLTK stopwords corpus into `./build/nltk_data/` for upload to a UC Volume (works around Databricks Serverless outbound restrictions).
- `docs/databricks-setup-guide.md` — end-to-end walkthrough: signup → UC Volume → upload → GitHub PAT → Repos clone → notebook attach → export.
- Implementation plan at `plans/260428-0843-databricks-migration-experiments/`.

### Removed
- `api/` (FastAPI stubs, 0 LOC) and `frontend/` (Streamlit stubs, 0 LOC).
- `docker/` (PySpark+Jupyter dev image).
- Cluster shell scripts: `scripts/setup_cluster.sh`, `run_pipeline.sh`, `upload_data.sh`.
- Gutenberg ingestion scripts: `scripts/hdfs_uploader.py`, `gutenberg_downloader.py`, `generate_sample_dataset.py`, `download_and_upload_gutenberg.py`.
- `src/main.py` (CLI entrypoint), `src/baseline_main.py`, `src/prepare_sample.py`.
- `config/cluster.env`.
- Production dependencies: `fastapi`, `uvicorn`, `pydantic`, `python-multipart`, `streamlit`, `requests`, `beautifulsoup4`.
- Makefile targets: `api`, `ui`, `docker`, `download-sample`, `download-gutenberg`, `cluster-deploy`, `cluster-upload`, `cluster-run`, `cluster-ui`, `run`, `query`.

### Verified
- `LSH_ENV=dev uv run pytest -q` → 35/35 tests pass.
- `LSH_ENV=databricks` config prints expected Volume paths.

---

## [0.1.0] — 2026-03-04

### Added
- Initial project skeleton with `src/` Spark pipeline (preprocessing, shingling, MinHash, LSH, query).
- 100-book Gutenberg sample + preprocessing pipeline (93 books validated).
- 35 unit tests across all `src/` modules.
- Configuration management (`DevConfig`, `ClusterConfig`).
- Docker dev environment for local PySpark+Jupyter.
- Initial documentation set in `docs/`.
