# 📚 Similar Book Recommendation using LSH

> **CO5135 Big Data — HK2 2025-2026 — Nhóm 4**
> Trường Đại Học Bách Khoa TP.HCM

## 👥 Team

| Name | MSSV | Role |
|---|---|---|
| Nguyễn Hoàng Kiên | 2570435 | Preprocessing, Testing, Report |
| Ngô Hoài Tú | 2570536 | LSH Algorithm, Frontend, Dashboard |
| Trần Quốc Việt | 2570154 | Lead, Infra, API, Experiments |

**GVHD:** PGS.TS Thoại Nam

## 🏗️ Architecture

```
Notebook (Databricks Serverless / Local) → PySpark → Parquet (UC Volume / local)
```

## 📁 Structure

```
project-lsh/
├── config/           # dev.env, settings.py (Dev/Cluster/Databricks configs)
├── src/              # preprocessing, shingling, minhash, lsh, query, evaluation
├── notebooks/        # 5 Jupyter notebooks (Databricks-aware setup cells)
├── scripts/          # text-cleaning utils + databricks NLTK bootstrap
├── tests/            # Unit tests (35 passing)
├── data/sample/      # 100 books for local dev
├── docs/             # Setup guides, architecture, code standards
├── plans/            # Implementation plans
├── Makefile
└── pyproject.toml
```

## 🚀 Quick Start

### Option A — Run on Databricks Free Edition (recommended for the report)

End-to-end notebook execution on Databricks Serverless. No local Spark needed.

→ See [docs/databricks-setup-guide.md](docs/databricks-setup-guide.md) for full walkthrough.

Summary:
1. Sign up Free Edition → create UC Volume
2. Upload pre-cleaned parquet + NLTK corpus to Volume
3. Link GitHub PAT → clone repo as Git folder
4. Open `notebooks/04_experiments.ipynb` → attach Serverless → Run All
5. Export `experiment_results.csv` + plots from Volume

### Option B — Local Development

```bash
# Prerequisites: uv (https://docs.astral.sh/uv/) + Java 11+

git clone <repo-url>
cd lsh-book-recommendation
uv sync --all-extras

# Run tests
LSH_ENV=dev uv run pytest -v

# Run notebooks
LSH_ENV=dev uv run jupyter notebook notebooks/
```

## 🧪 Tests

```bash
LSH_ENV=dev uv run pytest -v
# Expect: 35/35 pass
```

## 📖 Data

Pre-selected 93 cleaned books from Project Gutenberg in `data/output/cleaned/*.parquet` (used directly by Databricks notebook flow). Raw `.txt` samples for local dev in `data/sample/`.
