# Phase 01 -- Docker Configuration

## Context Links

- [plan.md](./plan.md)
- [Dockerfile.dev](/docker/Dockerfile.dev)
- [docker-compose.yml](/docker/docker-compose.yml)
- [Makefile](/Makefile)
- [pyproject.toml](/pyproject.toml)

## Overview

- **Priority**: P1
- **Status**: completed
- **Description**: Update Dockerfile.dev and docker-compose.yml so PySpark local mode + Jupyter works out of the box

## Key Insights

- `bitnami/spark:3.5` sets `JAVA_HOME=/opt/bitnami/java` and `SPARK_HOME=/opt/bitnami/spark`
- These env vars may not propagate into `uv run` subshell; must export explicitly
- `uv sync` creates `.venv` at `/app/.venv`; Jupyter kernel must point to this venv Python
- Current CMD already starts Jupyter but with default token enabled
- `PYTHONPATH=/app` needed so notebooks import `scripts`, `config`, `src` packages
- bitnami image runs as user 1001 by default; Dockerfile switches to root which is fine for dev

## Requirements

### Functional
- PySpark SparkSession("local[*]") starts without errors inside container
- Jupyter accessible at port 8888 with no authentication
- `from scripts import clean_gutenberg_text` works in notebook
- `from config.settings import config` works in notebook
- Spark UI accessible at port 4040 when SparkSession active

### Non-Functional
- Container build < 3 minutes on cached layers
- Image size reasonable (bitnami/spark:3.5 is ~1.5GB; final ~2GB acceptable)

## Architecture

```
Host machine                     Docker container (lsh-dev)
-----------                      --------------------------
project root/  --volume-->       /app/
  data/sample/*.txt                data/sample/*.txt
  notebooks/*.ipynb                notebooks/*.ipynb
  scripts/*.py                     scripts/*.py
  config/settings.py               config/settings.py

Ports:
  8888 <--> 8888   (Jupyter)
  4040 <--> 4040   (Spark UI)
  8000 <--> 8000   (FastAPI)
  8501 <--> 8501   (Streamlit)
```

## Related Code Files

### Modify
- `docker/Dockerfile.dev` -- add env vars, ipykernel registration, disable token
- `docker/docker-compose.yml` -- add PYTHONPATH, PYSPARK env vars

### No changes needed
- `Makefile` -- `make docker` target already correct
- `pyproject.toml` -- `ipykernel` already in dev deps

## Implementation Steps

### Step 1: Update Dockerfile.dev

Replace current content with:

```dockerfile
FROM bitnami/spark:3.5

USER root

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:$PATH"

WORKDIR /app
COPY pyproject.toml .

# Install dependencies (including dev extras for jupyter/ipykernel)
RUN uv sync --all-extras

# Register ipykernel so Jupyter sees the venv Python with pyspark
RUN uv run python -m ipykernel install --user --name lsh-spark --display-name "PySpark (LSH)"

# Ensure Spark and Java are visible to uv-managed Python
ENV JAVA_HOME="/opt/bitnami/java"
ENV SPARK_HOME="/opt/bitnami/spark"
ENV PYTHONPATH="/app"
ENV PYSPARK_PYTHON="/app/.venv/bin/python"
ENV PYSPARK_DRIVER_PYTHON="/app/.venv/bin/python"

EXPOSE 8888 8501 8000 4040

CMD ["uv", "run", "jupyter", "notebook", \
     "--ip=0.0.0.0", "--port=8888", "--allow-root", "--no-browser", \
     "--NotebookApp.token=''", "--NotebookApp.password=''", \
     "--notebook-dir=/app/notebooks"]
```

**Key changes from current Dockerfile:**
1. Added `uv run python -m ipykernel install` -- registers kernel with Spark-aware Python
2. Added `JAVA_HOME`, `SPARK_HOME`, `PYTHONPATH`, `PYSPARK_PYTHON`, `PYSPARK_DRIVER_PYTHON` env vars
3. Disabled Jupyter token/password via `--NotebookApp.token='' --NotebookApp.password=''`
4. Set `--notebook-dir=/app/notebooks` so Jupyter opens directly in notebooks folder

### Step 2: Update docker-compose.yml

```yaml
version: "3.8"

services:
  dev:
    build:
      context: ..
      dockerfile: docker/Dockerfile.dev
    container_name: lsh-dev
    environment:
      - LSH_ENV=dev
      - PYTHONPATH=/app
      - JAVA_HOME=/opt/bitnami/java
      - SPARK_HOME=/opt/bitnami/spark
      - PYSPARK_PYTHON=/app/.venv/bin/python
      - PYSPARK_DRIVER_PYTHON=/app/.venv/bin/python
    ports:
      - "8888:8888"
      - "8501:8501"
      - "8000:8000"
      - "4040:4040"
    volumes:
      - ..:/app
    working_dir: /app
```

**Key changes:**
1. Added `PYTHONPATH=/app` -- enables `from scripts import ...` without sys.path hack
2. Added `JAVA_HOME`, `SPARK_HOME` -- ensures Spark finds JVM even in uv subshell
3. Added `PYSPARK_PYTHON`, `PYSPARK_DRIVER_PYTHON` -- ensures PySpark uses venv Python

### Step 3: Verify Build

After changes, run:
```bash
make docker
docker logs lsh-dev  # should show Jupyter starting with no token
# Open localhost:8888 -- should load directly with no login
```

## Todo List

- [x] Update `docker/Dockerfile.dev` with env vars, ipykernel install, token disable
- [x] Update `docker/docker-compose.yml` with environment variables
- [x] Build and verify container starts cleanly
- [x] Confirm Jupyter loads at localhost:8888 without token
- [x] Confirm Spark UI accessible at localhost:4040 (when SparkSession active)

## Success Criteria

1. `docker compose -f docker/docker-compose.yml build` succeeds
2. `docker compose -f docker/docker-compose.yml up -d` starts container
3. `docker logs lsh-dev` shows Jupyter running, no errors
4. Browser at `localhost:8888` loads Jupyter with no auth prompt
5. Python kernel named "PySpark (LSH)" visible in Jupyter kernel list

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| bitnami image update breaks JAVA_HOME path | Low | High | Pin to bitnami/spark:3.5 (already done) |
| uv sync fails on cached layer with volume mount | Medium | Medium | COPY pyproject.toml before sync; volume overrides at runtime |
| ipykernel install lost when volume mounts over /app | Medium | High | Install kernel to `/root/.local/` (--user flag) so it persists |

## Security Considerations

- Token disabled -- acceptable for local dev container only
- Container runs as root -- acceptable for dev; never deploy this image
- No secrets in Dockerfile or compose file
- .env files gitignored; not copied into image

## Next Steps

After this phase, proceed to [Phase 02 -- Test Notebook](./phase-02-test-notebook.md) to create the working data exploration notebook.
