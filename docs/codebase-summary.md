# Codebase Summary

**Last Updated**: 2026-03-03
**Version**: 0.1.0
**Project**: LSH Book Recommendation System
**Team**: Nguyễn Hoàng Kiên, Ngô Hoài Tú, Trần Quốc Việt
**Course**: CO5135 Big Data — HK2 2025-2026

## Overview

LSH Book Recommendation is a distributed system for finding similar books using Locality-Sensitive Hashing (LSH) on Apache Spark. The system processes large-scale book datasets from Project Gutenberg, generates minwise signatures, and enables fast similarity queries through LSH bucketing.

**Architecture**: Streamlit → FastAPI → PySpark → HDFS + Parquet

## Project Structure

```
lsh-book-recommendation/
├── .claude/              # Claude Code configuration & skills
├── .github/              # GitHub Actions workflows
├── api/                  # FastAPI REST API (stubs only)
│   ├── main.py          # App entry (0 LOC)
│   ├── routers/         # Endpoint handlers (all stubs)
│   └── schemas.py       # Pydantic models (0 LOC)
├── config/               # Configuration management
│   ├── dev.env          # Development environment
│   ├── cluster.env      # Cluster settings
│   └── settings.py      # Settings loader (59 LOC) ✅
├── data/                 # Data storage & datasets
│   ├── sample/          # 100-book development sample (pre-downloaded)
│   └── output/          # Pipeline results (Parquet files)
├── docs/                 # Project documentation
├── docker/               # Docker dev environment (PySpark + Jupyter)
├── frontend/             # Streamlit web UI (stubs only)
│   ├── app.py           # Main entry (0 LOC)
│   └── pages/           # Multi-page components (all stubs)
├── notebooks/            # Jupyter exploration & demos
├── plans/                # Implementation plans
├── scripts/              # Data ingestion package (355 LOC total)
│   ├── __init__.py      # Package marker
│   ├── text_cleaning_utils.py       # Text cleaning (97 LOC) ✅
│   ├── gutenberg_downloader.py      # Gutenberg API client (134 LOC) ✅
│   ├── hdfs_uploader.py             # HDFS integration (115 LOC) ✅
│   ├── generate_sample_dataset.py   # Sample generator (124 LOC) ✅
│   └── download_and_upload_gutenberg.py  # CLI orchestrator (92 LOC) ✅
├── src/                  # Core Spark pipeline (FLAT FILE STRUCTURE)
│   ├── __init__.py      # Package marker
│   ├── preprocessing.py  # Tokenization & cleanup (120 LOC) ✅
│   ├── shingling.py      # k-shingle generation (0 LOC - stub)
│   ├── minhash.py        # MinHash signatures (0 LOC - stub)
│   ├── lsh.py            # LSH bucketing (0 LOC - stub)
│   ├── query.py          # Query engine (0 LOC - stub)
│   ├── evaluation.py     # Metrics (0 LOC - stub)
│   ├── utils.py          # Utilities (0 LOC - stub)
│   └── main.py           # Pipeline entry (0 LOC - stub)
├── tests/                # Unit & integration tests (118 LOC)
│   ├── conftest.py      # SparkSession fixture (23 LOC)
│   ├── test_preprocessing.py  # 10 tests (118 LOC) ✅
│   └── test_*.py        # Other tests (all stubs)
├── CLAUDE.md            # Development guidelines
├── Makefile             # Development commands (73 LOC)
├── pyproject.toml       # Python dependencies & config
├── README.md            # Project overview (96 LOC)
└── repomix-output.xml   # Codebase compaction (AI analysis)
```

**Legend**: ✅ Implemented | ⏳ Stub (not implemented)

## Core Technologies

### Runtime & Dependencies
- **Python**: >= 3.10
- **Package Manager**: uv (recommended) / pip
- **Spark**: >= 3.5 (PySpark)
- **Java**: 11+ (Spark requirement)

### Data Processing Stack
- **Apache Spark**: Distributed RDD/DataFrame processing
- **HDFS**: Distributed file storage for datasets
- **Parquet**: Columnar storage for efficiency
- **BeautifulSoup4**: HTML parsing for Gutenberg fallback

### Web Services
- **FastAPI**: High-performance REST API
- **Streamlit**: Interactive web dashboard
- **Uvicorn**: ASGI application server

## Key Components

### 1. Data Ingestion Layer (`scripts/` package)

**Responsibility**: Download and prepare book data from Project Gutenberg

**Modules**:

| Module | Purpose |
|--------|---------|
| `text_cleaning_utils.py` | Text preprocessing (whitespace, lowercasing, token filtering) |
| `gutenberg_downloader.py` | Project Gutenberg API client (search, metadata fetch, download) |
| `hdfs_uploader.py` | Upload files to HDFS cluster |
| `generate_sample_dataset.py` | Generate 100-book sample from Gutenberg mirror |
| `download_and_upload_gutenberg.py` | Orchestrator: download + HDFS upload pipeline |

**Entry Points**:
```bash
# Generate 100-book sample for local testing
make download-sample

# Download N books from Gutenberg API + upload to HDFS
make download-gutenberg NUM=500
```

### 2. Core LSH Pipeline (`src/` package)

**Responsibility**: Distributed LSH computation on Spark for similarity indexing

**Modules**:

| Module | Purpose | Output |
|--------|---------|--------|
| `preprocessing.py` | PySpark pipeline: load raw books, strip Gutenberg headers, lowercase, regex clean, tokenize, remove stopwords | `DataFrame(book_id: string, tokens: array<string>)` saved to Parquet |
| `shingling/` | Generate k-shingles from token streams (k=5 default) | Shingle sets per book |
| `minhash/` | Compute MinHash signatures using 200 hash functions | Signature vectors |
| `lsh/` | Hash signatures into bands/buckets for clustering | Bucket assignments |
| `query/` | Find similar books by querying LSH index | Top-K results |
| `evaluation/` | Compute precision, recall, F1 metrics | Evaluation report |

**Preprocessing Public API** (`src/preprocessing.py`):

| Function | Signature | Purpose |
|----------|-----------|---------|
| `create_spark_session` | `() -> SparkSession` | Create/get SparkSession from project config |
| `load_raw_books` | `(spark: SparkSession) -> DataFrame` | Read all `.txt` files via `wholeTextFiles`; returns `(path, content)` |
| `preprocess_books` | `(df: DataFrame, spark: SparkSession) -> DataFrame` | Full pipeline: headers → lowercase → regex → tokenize → stopwords; returns `(book_id, tokens)` |
| `run_preprocessing` | `() -> DataFrame` | Full pipeline + Parquet save; reads back saved data |

**Output**: Parquet files at `data/output/cleaned/` — schema `(book_id: string, tokens: array<string>)`
**Validated**: 93 sample books processed successfully.

**Configuration** (from `config/settings.py`):
- `SHINGLE_K=3` (dev) / `3` (cluster) - Shingle size
- `MINHASH_NUM_HASHES=50` (dev) / `100` (cluster) - Number of hash functions
- `LSH_NUM_BANDS=10` (dev) / `20` (cluster) - Band count
- `LSH_ROWS_PER_BAND=5` (both) - Rows per band

### 3. API & Frontend Layer (NOT YET IMPLEMENTED)

**Status**: ⏳ Stubs only — no implementation code

**API** (`api/` - 0 LOC):
- `main.py` - FastAPI app (stub, 0 LOC)
- `routers/books.py`, `datasets.py`, `metrics.py` - Endpoint handlers (stubs)
- `schemas.py` - Pydantic models (stub, 0 LOC)

**Planned Endpoints**:
- `GET /health` - Service status
- `POST /query` - Find similar books (requires book_id, returns top_k results)
- `GET /dataset/info` - Dataset statistics
- `GET /dataset/books` - List available books

**Frontend** (`frontend/` - 0 LOC):
- `app.py` - Streamlit entry point (stub, 0 LOC)
- `pages/1_Browse_Books.py`, `2_Similar_Books.py`, `3_Dataset_Management.py`, `4_Dashboard.py` - Pages (stubs)

**Planned Schemas**:
- `QueryRequest(book_id: str, top_k: int)`
- `SimilarBook(id: str, title: str, similarity: float)`
- `QueryResponse(query_book: str, results: List[SimilarBook], execution_time: float)`

### 4. Configuration Management

**Location**: `config/` directory

**Files**:
- `dev.env` - Development mode (local Spark, sample data)
- `cluster.env` - Cluster mode (Spark master, HDFS paths)
- `settings.py` - Settings class (loads ENV-based config at runtime)

**Key Environment Variables**:
- `LSH_ENV` - Environment type (dev/cluster)
- `HDFS_PATH` - HDFS dataset root
- `SPARK_MASTER` - Spark master URL
- `SHINGLING_K` - Shingle size parameter

### 5. Development Infrastructure

**Makefile Targets**:
```bash
# Development
sync               # Install all dependencies with uv
test               # Run pytest suite
run                # Run ingestion pipeline (dev mode)
query BOOK=pg1234  # Query similar books
api                # Start FastAPI server
ui                 # Start Streamlit dashboard
notebook           # Start Jupyter Lab

# Data operations
download-sample              # Generate 100-book sample
download-gutenberg NUM=500   # Download N books from Gutenberg

# Code quality
lint               # Check with ruff
format             # Format with ruff

# Cluster operations
cluster-deploy     # Sync code to cluster
cluster-upload     # Upload data to HDFS
cluster-run        # Run pipeline on Spark cluster
cluster-ui         # Start Streamlit on cluster
```

## Dependencies Overview

### Production Dependencies
```
pyspark>=3.5,<4          # Spark distributed computing
nltk>=3.8               # Stopword corpus for preprocessing
fastapi                  # REST API framework
uvicorn                  # ASGI server
streamlit               # Web UI framework
beautifulsoup4          # HTML parsing (Gutenberg fallback)
numpy, pandas           # Data manipulation
```

### Development Dependencies
```
pytest                  # Unit testing
jupyter, notebook       # Interactive notebooks
ipykernel              # Jupyter kernel
ruff                   # Code linting & formatting
```

## Data Flow

```
Project Gutenberg API
        ↓
scripts/gutenberg_downloader.py  (fetch metadata & download books)
        ↓
scripts/hdfs_uploader.py  (upload to HDFS)
        ↓
HDFS /project-lsh/datasets/
        ↓
src/preprocessing/  (tokenize)
        ↓
src/shingling/  (k-shingles)
        ↓
src/minhash/  (signatures)
        ↓
src/lsh/  (bucket assignment)
        ↓
API (FastAPI) + UI (Streamlit)  (query interface)
```

## Critical Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Python config, dependencies, version |
| `Makefile` | Development command shortcuts |
| `CLAUDE.md` | Development guidelines & workflows |
| `config/settings.py` | Centralized configuration management |
| `api/main.py` | FastAPI application entry |
| `scripts/__init__.py` | Makes scripts/ importable as Python package |

## Testing Strategy

- **Unit tests**: `tests/test_preprocessing.py` - 10 unit tests for preprocessing pipeline (all passing)
- **Shared fixtures**: `tests/conftest.py` - session-scoped SparkSession (`local[1]`, 2g driver memory)
- **Integration tests**: `tests/integration/` - End-to-end pipeline validation (planned)

**Run tests**:
```bash
make test                    # Run all tests
LSH_ENV=dev uv run pytest    # Custom test execution
```

## Security & Configuration

### Secret Management
- `.env` files are gitignored
- Use `.env.example` as template
- Environment variables loaded via `config/settings.py`

### Data Privacy
- Book data from Project Gutenberg (public domain)
- No user data collection
- Local HDFS storage (no cloud uploads in dev)

## Unresolved Questions

1. **HDFS Cluster Setup**: How to properly configure HDFS paths across dev/cluster environments?
2. **Performance Scaling**: What LSH parameters (bands, hash functions) are optimal for 1M+ books?
3. **Query Latency SLA**: What response time targets for similarity queries in production?
