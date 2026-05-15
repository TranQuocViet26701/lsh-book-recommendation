"""
Environment configuration — dev (local), cluster (VPS), databricks (Free Edition Serverless).

Usage:
    from config.settings import config
"""

import os
from dataclasses import dataclass


@dataclass
class DevConfig:
    ENV = "dev"
    SPARK_MASTER = "local[*]"
    SPARK_APP_NAME = "LSH-Book-Recommendation"
    SPARK_EXECUTOR_MEMORY = "2g"
    SPARK_DRIVER_MEMORY = "2g"

    DATA_RAW_PATH = "./data/sample/"
    DATA_CLEANED_PATH = "./data/output/cleaned/"
    DATA_SIGNATURES_PATH = "./data/output/signatures/"
    DATA_LSH_INDEX_PATH = "./data/output/lsh_index/"
    DATA_METADATA_PATH = "./data/output/metadata/"
    DATA_OUTPUT_PATH = "./data/output/"

    SHINGLE_K = 3
    MINHASH_NUM_HASHES = 50
    LSH_NUM_BANDS = 10
    LSH_ROWS_PER_BAND = 5
    DEFAULT_TOP_K = 10


@dataclass
class ClusterConfig:
    ENV = "cluster"
    SPARK_MASTER = "spark://master:7077"
    SPARK_APP_NAME = "LSH-Book-Recommendation"
    SPARK_EXECUTOR_MEMORY = "4g"
    SPARK_DRIVER_MEMORY = "4g"

    DATA_RAW_PATH = "hdfs:///project-lsh/datasets/gutenberg_default/raw/"
    DATA_CLEANED_PATH = "hdfs:///project-lsh/datasets/gutenberg_default/cleaned/"
    DATA_SIGNATURES_PATH = "hdfs:///project-lsh/datasets/gutenberg_default/signatures/"
    DATA_LSH_INDEX_PATH = "hdfs:///project-lsh/datasets/gutenberg_default/lsh_index/"
    DATA_METADATA_PATH = "hdfs:///project-lsh/metadata/"
    DATA_OUTPUT_PATH = "hdfs:///project-lsh/output/"

    SHINGLE_K = 3
    MINHASH_NUM_HASHES = 100
    LSH_NUM_BANDS = 20
    LSH_ROWS_PER_BAND = 5
    DEFAULT_TOP_K = 10


# Databricks Free Edition (Serverless) — UC Volume paths.
# Override defaults via env vars LSH_DBX_CATALOG / LSH_DBX_SCHEMA / LSH_DBX_VOLUME.
_DBX_CATALOG = os.getenv("LSH_DBX_CATALOG", "workspace")
_DBX_SCHEMA = os.getenv("LSH_DBX_SCHEMA", "lsh_book_recommendation")
_DBX_VOLUME = os.getenv("LSH_DBX_VOLUME", "data")
_DBX_ROOT = f"/Volumes/{_DBX_CATALOG}/{_DBX_SCHEMA}/{_DBX_VOLUME}"


@dataclass
class DatabricksConfig:
    ENV = "databricks"
    # Serverless auto-injects `spark`; do NOT override master/memory.
    SPARK_MASTER = None
    SPARK_APP_NAME = "LSH-Book-Recommendation"
    SPARK_EXECUTOR_MEMORY = None
    SPARK_DRIVER_MEMORY = None

    CATALOG = _DBX_CATALOG
    SCHEMA = _DBX_SCHEMA
    VOLUME = _DBX_VOLUME

    DATA_RAW_PATH = f"{_DBX_ROOT}/raw/"
    DATA_CLEANED_PATH = f"{_DBX_ROOT}/cleaned/"
    DATA_SIGNATURES_PATH = f"{_DBX_ROOT}/signatures/"
    DATA_LSH_INDEX_PATH = f"{_DBX_ROOT}/lsh_index/"
    DATA_METADATA_PATH = f"{_DBX_ROOT}/metadata/"
    DATA_OUTPUT_PATH = f"{_DBX_ROOT}/output/"

    SHINGLE_K = 3
    MINHASH_NUM_HASHES = 100
    LSH_NUM_BANDS = 20
    LSH_ROWS_PER_BAND = 5
    DEFAULT_TOP_K = 10


def get_config():
    env = os.getenv("LSH_ENV", "dev").lower()
    if env == "databricks":
        return DatabricksConfig()
    if env == "cluster":
        return ClusterConfig()
    return DevConfig()


config = get_config()
