"""Shared pytest fixtures for PySpark tests."""

import os

import pytest
from pyspark.sql import SparkSession

# Ensure enough heap for local PySpark tests
os.environ.setdefault("PYSPARK_SUBMIT_ARGS", "--driver-memory 2g pyspark-shell")


@pytest.fixture(scope="session")
def spark():
    """Session-scoped SparkSession for tests (local[1] for speed)."""
    session = (
        SparkSession.builder
        .master("local[1]")
        .appName("test-preprocessing")
        .getOrCreate()
    )
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()
