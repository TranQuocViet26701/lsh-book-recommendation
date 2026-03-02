"""
Environment configuration — dev (local) vs cluster (VPS).

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

    SHINGLE_K = 3
    MINHASH_NUM_HASHES = 100
    LSH_NUM_BANDS = 20
    LSH_ROWS_PER_BAND = 5
    DEFAULT_TOP_K = 10


def get_config():
    env = os.getenv("LSH_ENV", "dev").lower()
    return ClusterConfig() if env == "cluster" else DevConfig()


config = get_config()
