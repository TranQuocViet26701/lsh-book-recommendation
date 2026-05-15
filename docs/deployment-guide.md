# Deployment Guide

**Last Updated**: 2026-04-28
**Version**: 0.2.0

## Overview

Two interchangeable run paths after the Databricks Free Edition migration:

1. **Databricks Free Edition (Serverless)** — primary; used to produce the course report (notebook `04_experiments.ipynb`)
2. **Local development** — for tests, dev iteration, debugging notebooks before pushing

There is no longer a Docker dev image, no FastAPI server, and no Streamlit dashboard — the experiment surface is the Databricks notebook itself.

---

## Part 1 — Databricks Free Edition (Primary)

End-to-end walkthrough: see [databricks-setup-guide.md](./databricks-setup-guide.md).

### Prerequisites
- Databricks Free Edition account (signup link in setup guide)
- GitHub PAT with `Contents: Read & Write` on this repo
- Pre-cleaned parquet at `data/output/cleaned/*.parquet` (already in repo, 93 books)

### One-Time Setup
1. Sign up Free Edition
2. Create UC Volume `/Volumes/workspace/lsh_book_recommendation/data/`
3. Run `scripts/bootstrap-nltk-stopwords-to-volume.py` locally → upload `./build/nltk_data/` to Volume
4. Upload `./data/output/cleaned/` to Volume
5. Link GitHub PAT in Databricks user settings
6. Clone repo as Git folder, switch to `databricks-migration` branch

### Running an Experiment
1. Open `notebooks/04_experiments.ipynb` → attach **Serverless**
2. Run All
3. CSV + plots saved to `/Volumes/.../output/`
4. Pull artifacts: `databricks fs cp dbfs:/Volumes/.../output ./reports`

### Constraints
- Serverless-only (no cluster mgmt)
- 2.5h notebook timeout
- Outbound internet restricted (NLTK pre-bundled to Volume)
- Single-user UC ACLs on Free Edition

---

## Part 2 — Local Development

### Prerequisites
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Java 11+ (PySpark requirement)

### Setup

```bash
git clone <repo-url>
cd lsh-book-recommendation
uv sync --all-extras
```

### Run Tests

```bash
LSH_ENV=dev uv run pytest -v
# Expect: 35/35 pass
```

### Run Notebooks

```bash
make notebook
# Or: LSH_ENV=dev uv run jupyter notebook notebooks/
```

The setup preamble in each notebook auto-detects local vs Databricks; no env vars needed beyond `LSH_ENV=dev` (which is the default).

### Lint / Format

```bash
make lint     # ruff check
make format   # ruff format
```

---

## Configuration

`config/settings.py` exposes three configs selected by `LSH_ENV`:

| `LSH_ENV` | Use case | Spark master | Data root |
|---|---|---|---|
| `dev` (default) | local Jupyter, pytest | `local[*]` | `./data/...` |
| `cluster` (legacy) | reserved for future on-prem Spark | `spark://master:7077` | `hdfs://...` |
| `databricks` | Free Edition Serverless | `None` (auto-injected) | `/Volumes/.../...` |

### Databricks Volume Path Override

Defaults: `/Volumes/workspace/lsh_book_recommendation/data/`. Override with env vars (set in notebook before importing config):

```python
import os
os.environ["LSH_DBX_CATALOG"] = "my_catalog"
os.environ["LSH_DBX_SCHEMA"]  = "my_schema"
os.environ["LSH_DBX_VOLUME"]  = "my_volume"
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `nltk.LookupError` on Databricks | NLTK_DATA not set / corpus not uploaded | Re-upload `./build/nltk_data/` to Volume; check `NLTK_DATA` env in setup cell |
| `parquet path not found` on Databricks | Cleaned parquet not in Volume | `databricks fs ls dbfs:/Volumes/.../cleaned` to verify |
| TN3 OOM at size=1500 | Driver memory ceiling on Free Edition | Edit `sizes_tn3 = [200, 500, 1000]` and re-run |
| Local pytest fails on macOS Spark socket | macOS loopback DNS quirk | Already handled by `tests/conftest.py` (`spark.sql.shuffle.partitions=4`) |

---

## See Also

- [databricks-setup-guide.md](./databricks-setup-guide.md) — full Databricks walkthrough
- [system-architecture.md](./system-architecture.md) — architectural overview
- [codebase-summary.md](./codebase-summary.md) — module-by-module breakdown
