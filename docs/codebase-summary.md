# Codebase Summary

**Last Updated**: 2026-04-28
**Version**: 0.2.0
**Project**: LSH Book Recommendation System
**Team**: Nguyễn Hoàng Kiên, Ngô Hoài Tú, Trần Quốc Việt
**Course**: CO5135 Big Data — HK2 2025-2026

## Overview

LSH Book Recommendation is a notebook-driven, distributed system for finding similar books using Locality-Sensitive Hashing (LSH) on Apache Spark. After the Databricks Free Edition (Serverless) migration, the experiment surface lives in `notebooks/04_experiments.ipynb` and consumes pre-cleaned parquet from a Unity Catalog Volume. The same `src/` codebase runs locally for tests and dev.

**Architecture**: Notebook (Databricks Serverless / Local) → PySpark → Parquet (UC Volume / local)

## Project Structure

```
lsh-book-recommendation/
├── .claude/              # Claude Code config & skills (gitignored)
├── config/               # Configuration management
│   ├── dev.env           # Local dev env vars
│   └── settings.py       # DevConfig / ClusterConfig / DatabricksConfig
├── data/                 # Data storage
│   ├── sample/           # 100-book raw .txt for local dev
│   └── output/cleaned/   # Pre-cleaned parquet (uploaded to UC Volume on Databricks)
├── docs/                 # Project documentation
│   ├── databricks-setup-guide.md   # Free Edition setup walkthrough
│   ├── system-architecture.md      # Architectural overview
│   ├── codebase-summary.md         # This file
│   ├── code-standards.md
│   ├── project-overview-pdr.md
│   └── project-roadmap.md
├── notebooks/            # 5 Jupyter notebooks (Databricks-aware setup)
│   ├── 01_data_exploration.ipynb
│   ├── 02_preprocessing_demo.ipynb
│   ├── 03_lsh_pipeline_demo.ipynb
│   ├── 04_experiments.ipynb        # Course report deliverable (TN1–TN4)
│   └── 05_query_demo.ipynb
├── plans/                # Implementation plans (gitignored)
├── scripts/              # Helper scripts
│   ├── __init__.py
│   ├── text_cleaning_utils.py             # Gutenberg header strip
│   └── bootstrap-nltk-stopwords-to-volume.py  # Pre-bundle NLTK for Databricks
├── src/                  # Core Spark pipeline
│   ├── __init__.py
│   ├── preprocessing.py            # Tokenize + stopword removal (Databricks-aware Spark)
│   ├── shingling.py                # k-shingle generation
│   ├── minhash.py                  # MinHash signatures
│   ├── lsh.py                      # Band/bucket index + candidate pairs
│   ├── query.py                    # Top-K similarity lookup
│   ├── query_by_text_helpers.py    # Helper utilities for nb 05
│   ├── evaluation.py               # Metrics (recall/precision/F1/FPR)
│   └── utils.py
├── tests/                # 35 unit tests (all passing)
│   ├── conftest.py                 # SparkSession fixture
│   ├── test_preprocessing.py       # 10 tests
│   ├── test_shingling.py           # 6 tests
│   ├── test_minhash.py             # 6 tests
│   ├── test_lsh.py                 # 6 tests
│   └── test_query.py               # 7 tests
├── CLAUDE.md             # Dev guidelines (gitignored)
├── Makefile              # sync / test / notebook / lint / format
├── pyproject.toml        # 5 prod deps, 5 dev deps
├── README.md             # Quick start
└── uv.lock
```

## Core Technologies

### Runtime
- **Python**: >= 3.10
- **Package Manager**: uv
- **Spark**: PySpark >= 3.5
- **Java**: 11+ (local Spark requirement; not needed on Databricks)

### Data Processing
- **PySpark DataFrame/RDD** — distributed compute
- **Parquet** — columnar storage (local + UC Volume)
- **NLTK** — English stopwords (pre-bundled to Volume on Databricks)
- **NumPy / pandas / matplotlib** — driver-side aggregation + plots

### Compute Targets
- **Databricks Free Edition (Serverless)** — primary, for course report
- **Local Spark `local[*]`** — dev + tests + notebook iteration

## Key Components

### 1. Helper Scripts (`scripts/` package)

| Module | Purpose |
|---|---|
| `text_cleaning_utils.py` | Strip Gutenberg headers/footers; lowercase; whitespace normalization |
| `bootstrap-nltk-stopwords-to-volume.py` | Local helper — downloads NLTK stopwords corpus into `./build/nltk_data/` for upload to UC Volume (works around Databricks Serverless outbound block) |

### 2. Core LSH Pipeline (`src/` package)

| Module | Purpose | Output Schema |
|---|---|---|
| `preprocessing.py` | Load raw books, strip headers, lowercase, regex clean, tokenize, remove stopwords | `(book_id: string, tokens: array<string>)` |
| `shingling.py` | Generate k-shingles from token streams (k=3) | `(book_id, shingles: array<string>)` |
| `minhash.py` | Compute N-dim MinHash signatures (universal hashing, md5-seeded) | `(book_id, signature: array<int>)` |
| `lsh.py` | Hash signatures into bands/buckets; self-join for candidate pairs | `(book_id, band_id, bucket_hash)` |
| `query.py` | Top-K similar books for a query book_id | `(book_id, similarity[, Title, Author])` |
| `evaluation.py` | Pair-level recall/precision/F1/FPR vs ground-truth | metrics dict |

#### Databricks-Aware SparkSession (`src/preprocessing.py`)

`create_spark_session()` returns `SparkSession.getActiveSession()` if present (Databricks auto-injects `spark`), else builds a local session honoring config-driven master/memory. No `PYSPARK_SUBMIT_ARGS` overrides.

`_ensure_nltk_stopwords()` honors `NLTK_DATA` env var so the pre-bundled corpus on UC Volume is discovered without an outbound `nltk.download()` call.

### 3. Configuration (`config/settings.py`)

Three dataclass configs selected by `LSH_ENV` env var:

| `LSH_ENV` | Config | Spark master | Data root |
|---|---|---|---|
| `dev` (default) | `DevConfig` | `local[*]` | `./data/...` |
| `cluster` | `ClusterConfig` (legacy) | `spark://master:7077` | `hdfs:///project-lsh/...` |
| `databricks` | `DatabricksConfig` | `None` (auto-injected) | `/Volumes/<c>/<s>/<v>/...` |

`DatabricksConfig` honors `LSH_DBX_CATALOG` / `LSH_DBX_SCHEMA` / `LSH_DBX_VOLUME` env overrides (defaults: `workspace` / `lsh_book_recommendation` / `data`).

### 4. Notebooks (Run Surface)

All 5 notebooks share a Databricks-aware setup preamble that:
- Detects `_in_databricks` (checks `/Workspace` + `DATABRICKS_RUNTIME_VERSION`)
- Sets `LSH_ENV=databricks` + `NLTK_DATA` to Volume path
- Walks `sys.path` to repo root (Repos clone path or local `..`)

| Notebook | Purpose |
|---|---|
| `01_data_exploration.ipynb` | Dataset diagnostics |
| `02_preprocessing_demo.ipynb` | Preprocessing walkthrough |
| `03_lsh_pipeline_demo.ipynb` | Shingling → MinHash → LSH demo |
| `04_experiments.ipynb` | TN1–TN4 metrics + plots (course report) |
| `05_query_demo.ipynb` | Top-K query demo |

### 5. Development Infrastructure

**Makefile targets**:
```bash
sync       # Install all deps with uv
test       # LSH_ENV=dev uv run pytest -v
notebook   # Start Jupyter on notebooks/
lint       # ruff check src/ tests/
format     # ruff format src/ tests/
clean      # Remove caches
```

## Dependencies

### Production (5)
```
pyspark>=3.5,<4    # Spark distributed compute
nltk>=3.8          # Stopword corpus
numpy
pandas
matplotlib
```

### Development (5)
```
pytest
jupyter
notebook
ipykernel
ruff
```

## Data Flow

```
Project Gutenberg (public domain)
        ↓ (one-time, locally)
data/sample/*.txt
        ↓ run notebook 02 locally OR equivalent preprocessing
data/output/cleaned/*.parquet  (93 books)
        ↓ upload via Databricks CLI / UI
/Volumes/<catalog>/<schema>/<volume>/cleaned/  (UC Volume)
        ↓
notebooks/04_experiments.ipynb  (Databricks Serverless)
        ↓
TN1–TN4 metrics + plots → /Volumes/.../output/experiment_results.csv
        ↓ databricks fs cp
./reports/  (local export for course report)
```

## Critical Files

| File | Purpose |
|---|---|
| `pyproject.toml` | Python deps + ruff/pytest config |
| `Makefile` | Dev shortcuts |
| `config/settings.py` | Dev/Cluster/Databricks config selection |
| `src/preprocessing.py` | Databricks-aware SparkSession factory + NLTK_DATA bootstrap |
| `notebooks/04_experiments.ipynb` | TN1–TN4 experiment runner (course report) |
| `scripts/bootstrap-nltk-stopwords-to-volume.py` | Pre-bundle NLTK for Databricks upload |
| `docs/databricks-setup-guide.md` | End-to-end Databricks Free Edition walkthrough |

## Testing Strategy

**Unit tests** (35/35 passing on `LSH_ENV=dev`):
- `test_preprocessing.py` — 10 tests
- `test_shingling.py` — 6 tests
- `test_minhash.py` — 6 tests
- `test_lsh.py` — 6 tests
- `test_query.py` — 7 tests

Shared fixture: `tests/conftest.py` — session-scoped SparkSession (`local[1]`, 2g driver).

```bash
make test                  # all 35 tests
LSH_ENV=dev uv run pytest  # equivalent
```

## Security & Configuration

- **Secrets**: never committed. Databricks PAT lives only in workspace user settings. `.env` files are gitignored.
- **Data privacy**: all data is public-domain Project Gutenberg text; no PII.
- **UC Volume access**: governed by Unity Catalog ACLs (single-user on Free Edition).

## Removed in Databricks Migration (2026-04-28)

- `api/` (FastAPI stubs, 0 LOC)
- `frontend/` (Streamlit stubs, 0 LOC)
- `docker/` (PySpark+Jupyter dev image)
- `scripts/setup_cluster.sh`, `run_pipeline.sh`, `upload_data.sh`
- `scripts/hdfs_uploader.py`, `gutenberg_downloader.py`, `generate_sample_dataset.py`, `download_and_upload_gutenberg.py`
- `src/main.py`, `baseline_main.py`, `prepare_sample.py`
- `config/cluster.env`
- Production deps: `fastapi`, `uvicorn`, `pydantic`, `python-multipart`, `streamlit`, `requests`, `beautifulsoup4`
- Makefile targets: `api`, `ui`, `docker`, `download-sample`, `download-gutenberg`, `cluster-*`

See `plans/260428-0843-databricks-migration-experiments/` for the full migration plan.
