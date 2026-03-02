#!/bin/bash
# ═══════════════════════════════════════════
# Hadoop + Spark Cluster Setup
# Usage:
#   ROLE=master ./setup_cluster.sh
#   ROLE=worker ./setup_cluster.sh
# ═══════════════════════════════════════════

set -e
ROLE=${ROLE:-worker}

echo "Setting up ${ROLE} node..."
echo "TODO: Week 1 — Implement full cluster setup"
echo "  1. Install Java 11"
echo "  2. Install Hadoop 3.3.x"
echo "  3. Install Spark 3.5.x"
echo "  4. Configure HDFS, YARN, Spark"
echo "  5. Format NameNode (master only)"
echo "  6. Start services"
