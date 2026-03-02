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
Streamlit → FastAPI → PySpark → HDFS + Parquet
```

## 📁 Structure

```
project-lsh/
├── config/           # dev.env, cluster.env, settings.py
├── src/              # preprocessing, shingling, minhash, lsh, query, evaluation
├── api/              # FastAPI server + routers
├── frontend/         # Streamlit pages
├── notebooks/        # Jupyter exploration & demo
├── scripts/          # Cluster setup & deploy
├── tests/            # Unit tests
├── data/sample/      # 100 books for dev
├── docker/           # Dev container
├── Makefile
└── requirements.txt
```

## 🚀 Quick Start

### Prerequisites
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Java 11+ (required for PySpark)

### Setup

```bash
# Clone & setup
git clone <repo-url>
cd project-lsh

# Install with uv (fast!)
uv sync --all-extras

# Or with Docker
docker compose -f docker/docker-compose.yml up -d
```

### Run

```bash
# Notebooks
uv run jupyter notebook notebooks/

# Pipeline
LSH_ENV=dev uv run python -m src.main

# API + Frontend
LSH_ENV=dev uv run uvicorn api.main:app --port 8000
LSH_ENV=dev uv run streamlit run frontend/app.py
```

## 🧪 Tests

```bash
uv run pytest -v
```
