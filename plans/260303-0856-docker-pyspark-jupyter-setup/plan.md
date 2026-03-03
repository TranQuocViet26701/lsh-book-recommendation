---
title: "Docker PySpark + Jupyter Dev Environment"
description: "Enhance Docker setup for local PySpark + Jupyter with working test notebook"
status: completed
priority: P1
effort: 1.5h
branch: main
tags: [docker, pyspark, jupyter, dev-environment]
created: 2026-03-03
---

# Docker PySpark + Jupyter Dev Environment

## Goal

Make `make docker` + open `localhost:8888` a seamless experience: PySpark local[*] mode running inside container, Jupyter accessible with no token, notebooks can `import scripts`.

## Current State (Completed)

- `docker/Dockerfile.dev` updated with env vars (JAVA_HOME, SPARK_HOME, PYTHONPATH), ipykernel registration, Jupyter token disabled
- `docker/docker-compose.yml` updated with PYTHONPATH, PYSPARK env vars for proper module resolution
- `notebooks/01_data_exploration.ipynb` replaced with complete working Spark-based data exploration notebook
- `scripts/` package exports `clean_gutenberg_text` from `__init__.py`
- `config/settings.py` DevConfig uses `local[*]` master, paths relative to `./data/sample/`

## Problems to Fix

1. **PYTHONPATH not set** -- notebook uses `sys.path.insert(0, '..')` hack; breaks in Docker
2. **No ipykernel registration** -- Jupyter may not see PySpark-enabled kernel
3. **No SPARK_HOME/JAVA_HOME env vars exported** -- bitnami sets them but may not survive uv subshell
4. **Jupyter token enabled by default** -- friction for team; need `--NotebookApp.token=''`
5. **Notebook mostly stubs** -- needs real Spark DataFrame exploration code
6. **docker-compose missing PYTHONPATH** -- env var not passed to container

## Phases

| # | Phase | Status | Effort |
|---|-------|--------|--------|
| 1 | [Docker Configuration](./phase-01-docker-configuration.md) | completed | 0.5h |
| 2 | [Test Notebook](./phase-02-test-notebook.md) | completed | 1h |

## Deviations from Original Plan

1. **Base Image**: Changed from `bitnami/spark:3.5` (discontinued Sept 2025) to `python:3.11-slim` + `openjdk-21-jre-headless`
   - bitnami image no longer maintained; needed alternative approach
   - python:3.11-slim provides minimal, stable base
   - openjdk-21-jre-headless is available in Debian Trixie

2. **Virtual Environment Location**: Changed from `/app/.venv` to `/opt/venv`
   - `/app` is volume-mounted from host, causing venv symlinks to break
   - `/opt/venv` persists properly within container layer
   - Updated PATH and PYSPARK env vars accordingly

3. **Java Version**: Used Java 21 instead of Java 17
   - Debian Trixie (python:3.11-slim) only provides Java 21 in official repos
   - Java 21 LTS compatible with Spark 3.5+

4. **Jupyter Startup**: Changed from `uv run jupyter` to direct jupyter binary
   - Direct binary invocation more reliable than uv run wrapper
   - Cleaner container logs and faster startup

## Dependencies

- `data/sample/*.txt` must exist (run `make download-sample` first if empty)
- Custom Docker setup with python:3.11-slim + Apache Spark 3.5 + OpenJDK 21

## Key Decisions

- Keep `uv` as package manager inside container (already in Dockerfile)
- Use `local[*]` Spark master (no cluster needed for dev)
- Disable Jupyter token entirely for team convenience (dev-only container)
- Set PYTHONPATH=/app so `from scripts import ...` and `from config import ...` work without hacks
- Notebook runs with `/app` as working directory, paths match DevConfig

## Success Criteria

1. `make docker` builds and starts container without errors
2. `localhost:8888` opens Jupyter with no token prompt
3. Notebook `01_data_exploration.ipynb` runs all cells successfully
4. SparkSession initialized in local[*] mode inside container
5. Notebook reads .txt files from data/sample/, shows stats via Spark DataFrames
6. `from scripts import clean_gutenberg_text` works in notebook cells
