#!/bin/bash
# Upload book data to HDFS
set -e

DATASET=${1:-gutenberg_default}
LOCAL_PATH=${2:-~/data/raw/}

echo "Uploading ${LOCAL_PATH} to HDFS /project-lsh/datasets/${DATASET}/raw/"
echo "TODO: Week 1 — Implement data upload"
