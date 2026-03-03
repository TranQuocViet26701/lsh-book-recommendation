# Docker Dev Environment Guide

**Last Updated**: 2026-03-03

## Overview

Docker dev container provides PySpark + Jupyter in `local[*]` mode. No Java or Spark install needed on host — everything runs inside the container.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Sample data downloaded: `make download-sample` (run once on host)

## Quick Start

```bash
# 1. Build & start (first time takes ~2 min)
make docker

# 2. Open Jupyter (no login needed)
open http://localhost:8888

# 3. Open notebook 01_data_exploration.ipynb and run all cells

# 4. Stop when done
docker compose -f docker/docker-compose.yml down
```

## Services & Ports

| Port | Service | When Available |
|------|---------|----------------|
| 8888 | Jupyter Notebook | Always (container CMD) |
| 4040 | Spark UI | When SparkSession active |
| 8000 | FastAPI | When started manually |
| 8501 | Streamlit | When started manually |

## Jupyter Kernels

Two kernels available:

- **PySpark (LSH)** — registered via `ipykernel`, points to `/opt/venv/bin/python` with PySpark pre-installed. Use this for notebooks.
- **python3** — default kernel, same venv.

## How It Works

### Base Image

`python:3.11-slim` + `openjdk-21-jre-headless`. PySpark installed via `uv sync` (from `pyproject.toml`), not from a pre-built Spark image.

### Volume Mount

Host project root is mounted at `/app` inside the container:
```
Host: ./              →  Container: /app/
  data/sample/*.txt       data/sample/*.txt
  notebooks/*.ipynb       notebooks/*.ipynb
  scripts/*.py            scripts/*.py
  config/settings.py      config/settings.py
```

Changes to source files on host are immediately visible in the container (and vice versa).

### Virtual Environment

Python packages installed at `/opt/venv` (not `/app/.venv`) to avoid being overwritten by the volume mount. The `UV_PROJECT_ENVIRONMENT` env var tells `uv` where to find it.

### PYTHONPATH

Set to `/app` so notebooks can do:
```python
from config.settings import config
from scripts import clean_gutenberg_text
```
No `sys.path` hacks needed.

## Running Other Services

```bash
# FastAPI (inside container)
docker exec -it lsh-dev uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# Streamlit (inside container)
docker exec -it lsh-dev streamlit run frontend/app.py --server.port 8501

# Interactive shell
docker exec -it lsh-dev bash
```

## Rebuilding

Rebuild after changing `pyproject.toml` dependencies:

```bash
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `localhost:8888` not loading | Check `docker logs lsh-dev` for errors |
| Spark `JAVA_HOME` error | Verify `JAVA_HOME=/usr/lib/jvm/java-21` in compose env |
| Import errors in notebook | Ensure using "PySpark (LSH)" kernel, check PYTHONPATH |
| Old packages after dep change | Rebuild: `docker compose -f docker/docker-compose.yml build --no-cache` |
| Port conflict | Stop other services on 8888/4040/8000/8501 first |

## Architecture

```
Host machine                     Docker container (lsh-dev)
-----------                      --------------------------
project root/  --volume-->       /app/  (PYTHONPATH)
                                 /opt/venv/  (Python packages)
                                 /usr/lib/jvm/java-21/  (JRE)

Ports:
  8888 <--> 8888   Jupyter
  4040 <--> 4040   Spark UI
  8000 <--> 8000   FastAPI
  8501 <--> 8501   Streamlit
```
