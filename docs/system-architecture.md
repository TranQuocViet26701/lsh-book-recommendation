# System Architecture

**Last Updated**: 2026-04-28
**Version**: 0.2.0
**Project**: LSH Book Recommendation

## Overview

LSH Book Recommendation runs a notebook-driven, distributed Locality-Sensitive Hashing pipeline on Apache Spark for book similarity detection. After the Databricks Free Edition (Serverless) migration, the system has two interchangeable run paths — **Databricks notebook** (primary, used for the course report) and **local Spark** (dev/test) — sharing one PySpark codebase.

## Architectural Pattern

**Primary Pattern**: Notebook-driven Data Pipeline
**Design Philosophy**:
- **Separation of Concerns**: distinct modules for shingling, MinHash, LSH, query
- **Scalability**: distributed processing via Spark DataFrames + RDDs
- **Reproducibility**: configuration-driven (`LSH_ENV` selects Dev/Cluster/Databricks)
- **Portability**: same `src/` runs locally or on Databricks Serverless without changes

## High-Level Diagram

```
Notebook (Databricks Serverless / Local Jupyter)
        ↓
[src/preprocessing.py] — tokens DataFrame  (or load pre-cleaned parquet)
        ↓
[src/shingling.py]     — k-shingle sets
        ↓
[src/minhash.py]       — N-dim MinHash signatures
        ↓
[src/lsh.py]           — band/bucket index → candidate pairs
        ↓
[src/evaluation.py]    — recall / precision / F1 / FPR
        ↓
Parquet + CSV  (UC Volume on Databricks  |  ./data/output/ locally)
```

## System Components

### Layer 1: Data Source

- **Local dev**: `data/sample/` (raw `.txt`) + `data/output/cleaned/*.parquet` (pre-processed, 93 books)
- **Databricks**: parquet artifact uploaded to `/Volumes/<catalog>/<schema>/<volume>/cleaned/` (UC Volume)

> Outbound internet is restricted on Databricks Free Edition Serverless. NLTK stopwords are pre-bundled to the Volume via `scripts/bootstrap-nltk-stopwords-to-volume.py` (run locally, then upload).

### Layer 2: Batch Processing (Spark)

#### 2.1 Preprocessing — `src/preprocessing.py`
- Reads raw `.txt` via `wholeTextFiles` (local) OR loads pre-cleaned parquet directly (Databricks)
- Strips Gutenberg headers, lowercases, regex-cleans, tokenizes, removes stopwords
- Output: `DataFrame(book_id, tokens: array<string>)`
- `create_spark_session()` is Databricks-aware: returns `SparkSession.getActiveSession()` if `spark` is auto-injected; otherwise builds a local session from config

#### 2.2 Shingling — `src/shingling.py`
- Sliding k-token windows; default `k=3`
- Output: `DataFrame(book_id, shingles: array<string>)`

#### 2.3 MinHash — `src/minhash.py`
- N independent universal hash functions (md5-seeded, deterministic with seed=42)
- Output: `DataFrame(book_id, signature: array<int>)`
- `MINHASH_NUM_HASHES`: `50` (dev) / `100` (cluster, databricks)

#### 2.4 LSH — `src/lsh.py`
- Band-and-row bucketing (`b` bands × `r` rows, `b·r ≤ N`)
- Self-join on `(band_id, bucket_hash)` → candidate pairs
- `LSH_NUM_BANDS`: `10` (dev) / `20` (cluster, databricks); `LSH_ROWS_PER_BAND=5`

#### 2.5 Query — `src/query.py`
- Look up query book signature → matching buckets → exact-Jaccard re-rank → top-K
- Used by `notebooks/05_query_demo.ipynb` and `tests/test_query.py`

#### 2.6 Evaluation — `src/evaluation.py`
- Pair-level recall / precision / F1 / FPR vs ground-truth set (J ≥ threshold)
- Driven by `notebooks/04_experiments.ipynb` for the report

### Layer 3: Notebooks (Run Surface)

| Notebook | Purpose |
|---|---|
| `01_data_exploration.ipynb` | Dataset shape & cleaning diagnostics |
| `02_preprocessing_demo.ipynb` | Step-by-step preprocessing walk-through |
| `03_lsh_pipeline_demo.ipynb` | End-to-end shingling → MinHash → LSH demo |
| `04_experiments.ipynb` | TN1–TN4 metrics + plots (course report deliverable) |
| `05_query_demo.ipynb` | Top-K similarity queries |

All five notebooks share the same Databricks-aware setup preamble (auto-detects `_in_databricks`, sets `LSH_ENV`/`NLTK_DATA`, walks `sys.path` to repo root).

## Configuration

Selected via `LSH_ENV` env var → `config/settings.py::get_config()`:

| `LSH_ENV` | Config | Spark master | Data root |
|---|---|---|---|
| `dev` (default) | `DevConfig` | `local[*]` | `./data/...` |
| `cluster` (legacy) | `ClusterConfig` | `spark://master:7077` | `hdfs:///project-lsh/...` |
| `databricks` | `DatabricksConfig` | `None` (auto-injected) | `/Volumes/<c>/<s>/<v>/...` |

`DatabricksConfig` honors override env vars: `LSH_DBX_CATALOG`, `LSH_DBX_SCHEMA`, `LSH_DBX_VOLUME` (defaults: `workspace` / `lsh_book_recommendation` / `data`).

## Deployment Topologies

### Databricks Free Edition (primary)
- Compute: Serverless (auto-injected `spark`, ~2.5h timeout, no cluster mgmt)
- Storage: UC Volume managed by Unity Catalog
- Code: cloned as Git folder at `/Workspace/Repos/<user>/lsh-book-recommendation/`
- Setup: see [databricks-setup-guide.md](./databricks-setup-guide.md)

### Local Development
- Compute: PySpark `local[*]` via `uv run`
- Storage: `./data/sample/` + `./data/output/`
- Setup: `uv sync --all-extras`, then `make notebook` or `LSH_ENV=dev uv run pytest`

## Performance Notes

- **Brute-force baseline**: O(N²) Jaccard over all pairs — 8s for 93 books locally
- **LSH pipeline**: dominated by Spark JVM startup at small N (~5s); becomes a clear win at scale (see TN3 in notebook 04)
- **Synthetic-scale TN3**: sizes [200, 500, 1000, 1500] with auto-fallback to [200, 500, 1000] on driver OOM
- **Storage**: parquet ~50MB for 93 cleaned books

## Error Handling

- `_ensure_nltk_stopwords()` honors `NLTK_DATA` env (pre-bundled corpus); falls back to `nltk.download()` if available
- `create_spark_session()` reuses an active session when present (Databricks invariant), avoiding `local[*]` override
- Aggregation cell guards `os.makedirs` against `/Volumes/` paths (which already exist as managed FS)

## Security

- PAT for Databricks↔GitHub stored only in Databricks user settings (never in repo)
- Volume access governed by Unity Catalog ACLs (single-user on Free Edition)
- All data is public Project Gutenberg text — no PII concerns

## References

- Internal: [project-overview-pdr.md](./project-overview-pdr.md), [codebase-summary.md](./codebase-summary.md), [code-standards.md](./code-standards.md), [databricks-setup-guide.md](./databricks-setup-guide.md)
- External: [Apache Spark](https://spark.apache.org/docs/), [Databricks Free Edition limits](https://docs.databricks.com/aws/en/getting-started/free-edition-limitations), [LSH theory](https://en.wikipedia.org/wiki/Locality-sensitive_hashing)
