# Deployment Guide — Development & Cluster Setup

**Last Updated**: 2026-03-03
**Version**: 0.1.0

## Overview

This guide covers setup for both development (Docker) and cluster deployment modes for LSH Book Recommendation.

## Part 1: Development Environment (Docker)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Sample data: `make download-sample` (run once on host)

### Quick Start

```bash
# 1. Build & start container (first time: ~2 min)
make docker

# 2. Open Jupyter (no login needed)
open http://localhost:8888

# 3. Run notebook: 01_data_exploration.ipynb

# 4. Stop when done
docker compose -f docker/docker-compose.yml down
```

### Services & Ports

| Port | Service | Status |
|------|---------|--------|
| 8888 | Jupyter | Always running |
| 4040 | Spark UI | When SparkSession active |
| 8000 | FastAPI | Manual startup |
| 8501 | Streamlit | Manual startup |

### Architecture Details

#### Base Image
- `python:3.11-slim` + `openjdk-21-jre-headless`
- PySpark installed via `uv sync` from pyproject.toml
- Not using pre-built Spark images (cleaner, lighter)

#### Volume Mount
```
Host: ./              →  Container: /app/
  data/sample/*.txt       data/sample/*.txt
  notebooks/*.ipynb       notebooks/*.ipynb
  src/                    src/
  config/settings.py      config/settings.py
```

Changes on host are immediately visible in container and vice versa.

#### Virtual Environment
- Python packages installed at `/opt/venv` (not `/app/.venv`)
- This prevents overwriting by volume mount
- `UV_PROJECT_ENVIRONMENT` tells `uv` where to find packages

#### PYTHONPATH
Set to `/app` so imports work without sys.path hacks:
```python
from config.settings import config
from scripts.text_cleaning_utils import clean_gutenberg_text
```

### Running Services Inside Container

#### Jupyter (Default)
```bash
# Already running - just open http://localhost:8888
```

#### FastAPI
```bash
docker exec -it lsh-dev uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
# Access: http://localhost:8000/docs (Swagger UI)
```

#### Streamlit
```bash
docker exec -it lsh-dev streamlit run frontend/app.py --server.port 8501
# Access: http://localhost:8501
```

#### Interactive Shell
```bash
docker exec -it lsh-dev bash
cd /app
python -c "from config.settings import config; print(config.SHINGLE_K)"
```

### Jupyter Kernels

Two kernels available:
- **PySpark (LSH)** — uses `/opt/venv/bin/python` with all packages
- **python3** — default kernel, same environment

Use "PySpark (LSH)" kernel for notebooks.

### Rebuilding & Cleanup

After changing `pyproject.toml` dependencies:

```bash
# Rebuild image
docker compose -f docker/docker-compose.yml build

# Start fresh
docker compose -f docker/docker-compose.yml up -d

# Full rebuild (no cache)
docker compose -f docker/docker-compose.yml build --no-cache
```

### Troubleshooting

| Issue | Fix |
|-------|-----|
| `localhost:8888` not loading | Check: `docker logs lsh-dev` |
| `JAVA_HOME` error | Verify env var set to `/usr/lib/jvm/java-21` |
| Import errors in notebook | Use "PySpark (LSH)" kernel, check PYTHONPATH |
| Old packages after dep change | Rebuild: `docker compose ... build --no-cache` |
| Port already in use | Kill other services: `lsof -i :8888` |
| Container won't start | Check disk space: `docker system df` |

---

## Part 2: Cluster Deployment

### Prerequisites

- Hadoop cluster with HDFS namenode
- Spark cluster (standalone or YARN)
- SSH access to cluster master node
- Java 11+ on all cluster nodes

### Environment Configuration

#### Setup Cluster Credentials

1. Create `config/cluster.env`:
```bash
LSH_ENV=cluster
SPARK_MASTER=spark://master.cluster.local:7077
HDFS_NAMENODE=hdfs://master.cluster.local:9000
```

2. Set environment before running:
```bash
export LSH_ENV=cluster
```

#### Cluster Configuration

Edit `config/settings.py` for cluster-specific settings:
- `SPARK_DRIVER_MEMORY=4g` — Increase for larger datasets
- `SPARK_EXECUTOR_MEMORY=4g` — Per executor memory
- `DATA_RAW_PATH=hdfs://...` — HDFS paths
- `SHINGLE_K=3` — Tunable per experiment
- `MINHASH_NUM_HASHES=100` — Cluster uses more hashes
- `LSH_NUM_BANDS=20` — More bands for larger datasets

### Deployment Steps

#### 1. Deploy Code to Cluster

```bash
# Copy project to cluster master
make cluster-deploy
# This runs:
# rsync -av --exclude=data/ --exclude=.git/ \
#   ./ user@master:/path/to/lsh-book-recommendation/
```

#### 2. Upload Data to HDFS

```bash
# Create HDFS directories and upload sample data
make cluster-upload
# Creates: /project-lsh/datasets/gutenberg_default/raw/
# Uploads sample books to HDFS
```

#### 3. Run Preprocessing Pipeline

```bash
# Run on Spark cluster
make cluster-run
# Executes: spark-submit --master spark://master:7077 \
#   --driver-memory 4g --executor-memory 4g \
#   src/main.py
```

#### 4. Start Streamlit on Cluster

```bash
# SSH into master and start UI
make cluster-ui
# Then tunnel to local machine:
ssh -L 8501:localhost:8501 user@master

# Access: http://localhost:8501
```

### HDFS Data Structure

After deployment, HDFS contains:
```
/project-lsh/
├── datasets/
│   └── gutenberg_default/
│       ├── raw/              # Raw .txt files (input)
│       ├── cleaned/          # Preprocessed tokens (Parquet)
│       ├── signatures/       # MinHash signatures
│       ├── lsh_index/        # LSH bucket assignments
│       └── metadata/         # Book metadata
└── logs/                     # Job logs
```

### Monitoring Cluster Execution

#### Spark UI
- **Driver**: http://master:4040 (while job running)
- **History**: http://master:18080 (persistent)

#### Logs
```bash
# Application logs (on driver)
tail -f /path/to/lsh-book-recommendation/logs/*.log

# HDFS logs
hdfs dfs -cat /user/hadoop/logs/*.log

# Spark history (after job completes)
http://master:18080/
```

### Performance Tuning

#### Spark Configuration

Adjust in `config/settings.py` based on cluster size:

**Small Cluster (3 nodes)**:
```python
SPARK_DRIVER_MEMORY = "2g"
SPARK_EXECUTOR_MEMORY = "2g"
```

**Large Cluster (10+ nodes)**:
```python
SPARK_DRIVER_MEMORY = "8g"
SPARK_EXECUTOR_MEMORY = "8g"
```

#### Partitioning Strategy
```python
# More partitions = better parallelism, but more overhead
# Default: auto (based on data size)
# Tune if seeing skew: df.repartition(num_partitions)
```

#### Caching
```python
# Cache frequently-accessed DataFrames
df.cache()
df.count()  # Force materialization
```

### Troubleshooting Cluster Deployment

| Issue | Debug | Fix |
|-------|-------|-----|
| Connection refused to Spark | `ssh master` then `jps` | Check Spark daemons running |
| HDFS permission denied | `hdfs dfs -ls /` | Check user permissions, enable auth |
| Out of memory | Check Spark UI | Increase executor memory, reduce dataset |
| Data not found in HDFS | `hdfs dfs -ls /project-lsh/` | Re-run upload: `make cluster-upload` |
| Slow queries | Check Spark UI, check shuffle | Repartition, increase memory, check LSH params |

### Scaling to Larger Datasets

#### For 500+ Books

```bash
# Download more books
make download-gutenberg NUM=500

# Upload to HDFS
make cluster-upload

# Re-run preprocessing (data will be auto-discovered)
make cluster-run
```

#### For 1000+ Books

- Consider multi-node HDFS setup
- Increase executors: `SPARK_NUM_EXECUTORS=16`
- Increase executor cores: `SPARK_EXECUTOR_CORES=4`
- Use partitioned output: `output.partitionBy("first_letter")`

---

## Development Workflow

### Local Development

```bash
# Setup once
make sync

# For each change:
make lint
make test
make run  # Test pipeline locally

# View results
open notebooks/02_preprocessing_demo.ipynb
```

### Cluster Testing

```bash
# Test configuration
LSH_ENV=cluster make test

# Run on cluster (with small dataset first)
make cluster-run

# Monitor progress
ssh master -L 4040:localhost:4040
# Open http://localhost:4040
```

### Iterative Development

1. Develop & test locally (faster)
2. Commit & push to git
3. Deploy to cluster
4. Run with full dataset
5. Collect metrics & iterate

---

## Maintenance

### Regular Tasks

**Weekly**:
- Monitor Spark UI for errors
- Check HDFS disk usage: `hdfs dfsadmin -report`
- Review application logs

**Monthly**:
- Backup LSH index to external storage
- Update dependencies: `uv sync --all-extras`
- Review performance metrics

### Cleanup

```bash
# Remove old outputs (dev)
rm -rf data/output/*

# Remove old HDFS data (cluster)
hdfs dfs -rm -r /project-lsh/datasets/old_data/

# Prune old logs
find logs/ -mtime +30 -delete
```

### Upgrading

```bash
# Update PySpark version in pyproject.toml
uv sync

# Test locally
make test

# Deploy to cluster
make cluster-deploy
```

---

## References

- [Docker Documentation](https://docs.docker.com/)
- [Apache Spark Deployment](https://spark.apache.org/docs/latest/cluster-overview.html)
- [HDFS Architecture](https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HdfsDesign.html)
- [Project Configuration](./code-standards.md#configuration--constants)
- [System Architecture](./system-architecture.md)
