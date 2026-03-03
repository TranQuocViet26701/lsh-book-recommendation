# LSH Book Recommendation — Project Overview & PDR

**Project Name**: LSH Book Recommendation System
**Version**: 0.1.0
**Status**: Active Development (Week 2 complete)
**Last Updated**: 2026-03-03
**Course**: CO5135 Big Data — HK2 2025-2026
**Institution**: Trường Đại Học Bách Khoa TPHCM
**Advisor**: PGS.TS Thoại Nam

## Executive Summary

LSH Book Recommendation implements a distributed Locality-Sensitive Hashing (LSH) system on Apache Spark to detect similar books at scale. The system downloads book data from Project Gutenberg, preprocesses text, computes MinHash signatures, performs LSH bucketing, and exposes query capabilities via REST API and Streamlit web UI.

**Current Phase**: Week 2 of 7 complete
**Implemented**: Preprocessing pipeline + data ingestion utilities
**Pending**: Shingling, MinHash, LSH modules, API, Frontend, Experiments

## Project Purpose

### Vision
Build a scalable recommendation system demonstrating big data processing patterns (distributed text analysis, similarity detection via LSH, batch + serving architecture).

### Mission
Implement a full LSH pipeline showing:
- Large-scale text data ingestion from public datasets
- Distributed preprocessing with Spark
- MinHash + LSH for efficient similarity detection
- Web UI for interactive queries

### Learning Objectives
1. Master PySpark DataFrame & RDD operations
2. Understand LSH algorithm fundamentals
3. Deploy distributed systems on cluster infrastructure
4. Integrate multiple data processing layers (ingestion, batch, serving)

## Target Users & Personas

### Primary Users
1. **Big Data Course Students**: Learning Spark, LSH algorithms
2. **Researchers**: Studying similarity detection at scale
3. **Open-Source Developers**: Extending recommendation systems

### Persona: CS Student (Lei)
- **Goal**: Understand distributed text processing
- **Pain Points**: Complex Spark APIs, LSH theory
- **Solution**: Well-documented code + runnable examples

## Key Requirements

### Functional Requirements

#### FR1: Data Ingestion
- Download 100-1000 books from Project Gutenberg
- Extract metadata (title, author, language)
- Store locally and optionally on HDFS
- Support both single books and batch downloads
- Implement retry/backoff for network failures

#### FR2: Preprocessing Pipeline
- Load raw .txt files via Spark
- Strip Gutenberg-specific headers/footers
- Normalize text (lowercase, remove special chars)
- Tokenize into words
- Remove stopwords
- Output: DataFrame(book_id, tokens[]) → Parquet

#### FR3: Shingling (NOT YET IMPLEMENTED)
- Convert token streams into k-shingles
- Store shingles per book
- Support variable k (default k=3)

#### FR4: MinHash (NOT YET IMPLEMENTED)
- Compute MinHash signatures from shingles
- Use multiple hash functions (default 50-100)
- Output: DataFrame(book_id, signature[]) → Parquet

#### FR5: LSH Indexing (NOT YET IMPLEMENTED)
- Hash signatures into bands and rows
- Create lookup index for efficient querying
- Support configurable bands/rows (default 10 bands, 5 rows each)

#### FR6: Query Engine (NOT YET IMPLEMENTED)
- Find similar books by LSH index lookup
- Return top-K results with similarity scores
- Support parameterized queries (top_k, threshold)

#### FR7: REST API (NOT YET IMPLEMENTED)
- FastAPI server with:
  - `GET /health` - Server status
  - `POST /query` - Find similar books
  - `GET /dataset/info` - Dataset stats
  - `GET /dataset/books` - List books

#### FR8: Web UI (NOT YET IMPLEMENTED)
- Streamlit app with multi-page interface:
  - Browse Books page
  - Similar Books search page
  - Dataset Management page
  - Dashboard with metrics

### Non-Functional Requirements

#### NFR1: Performance
- Preprocessing: < 10 minutes for 100 books
- Query latency: < 1 second for top-10 results
- Memory: < 4GB for 100-book dataset

#### NFR2: Scalability
- Support 1000+ books without code changes
- Horizontally scalable via Spark cluster mode
- Distributed file storage (HDFS) for large datasets

#### NFR3: Reliability
- Retry failed downloads (exponential backoff)
- Handle corrupted book files gracefully
- Validate data quality at each pipeline stage

#### NFR4: Code Quality
- Test coverage > 80%
- PEP 8 compliant
- Type hints for all functions
- Comprehensive docstrings

#### NFR5: Documentation
- Setup guides for dev/cluster modes
- API documentation
- Algorithm walkthroughs
- Troubleshooting guides

## Architecture Overview

### System Diagram
```
Project Gutenberg
        ↓
scripts/gutenberg_downloader.py (fetch metadata + download)
        ↓
data/sample/ or HDFS (storage)
        ↓
src/preprocessing.py (tokenization + cleaning) [IMPLEMENTED]
        ↓
src/shingling.py (k-shingles) [PENDING]
        ↓
src/minhash.py (signatures) [PENDING]
        ↓
src/lsh.py (index) [PENDING]
        ↓
FastAPI /query endpoint [PENDING]
Streamlit UI [PENDING]
```

### Technology Stack

| Layer | Technology | Status |
|-------|-----------|--------|
| **Data Source** | Project Gutenberg API | ✅ Working |
| **Storage** | Parquet + HDFS | ✅ Working |
| **Compute** | Apache Spark 3.5+ | ✅ Working |
| **Preprocessing** | PySpark + NLTK | ✅ Implemented |
| **LSH Algorithms** | Custom Python | ⏳ Pending |
| **API** | FastAPI + Uvicorn | ⏳ Pending |
| **UI** | Streamlit | ⏳ Pending |
| **Dev Environment** | Docker + Jupyter | ✅ Working |
| **Package Manager** | uv | ✅ Working |

## Implementation Status

### Week 1-2: Foundation ✅ COMPLETE
- ✅ Project setup + repository structure
- ✅ Docker dev environment (PySpark + Jupyter)
- ✅ Data acquisition pipeline (Gutenberg downloader)
- ✅ Sample dataset generation (100 books)
- ✅ Preprocessing pipeline + unit tests (10 tests, all passing)
- ✅ Configuration management (dev/cluster modes)

### Week 3-5: Core LSH Algorithm ⏳ NOT STARTED
- ⏳ Shingling module + tests
- ⏳ MinHash module + tests
- ⏳ LSH indexing module + tests
- ⏳ Query engine + tests
- ⏳ Integration tests (end-to-end)

### Week 6-7: Serving & Experiments ⏳ NOT STARTED
- ⏳ FastAPI REST API
- ⏳ Streamlit web UI
- ⏳ Performance experiments
- ⏳ Optimization & tuning
- ⏳ Final report + presentation

## Success Criteria

### Must Have (MVP)
- [x] Preprocessing pipeline working with 100 books
- [ ] LSH algorithm correctly detecting similar books (manual validation)
- [ ] Query engine returning top-10 results < 1 second
- [ ] REST API accepting queries

### Should Have
- [ ] Streamlit UI with search interface
- [ ] Test coverage > 80%
- [ ] Support for 500+ book dataset
- [ ] Comprehensive documentation

### Nice To Have
- [ ] Cluster deployment guide
- [ ] Performance benchmarks (vs baseline methods)
- [ ] Docker Compose for full stack
- [ ] Experiment notebooks with visualizations

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|-----------|
| Slow preprocessing on large datasets | High | Medium | Optimize Spark config, use RDD caching |
| LSH false negatives | High | Medium | Tune hash functions, adjust bands/rows |
| Network failures during download | Medium | High | Implement retry with exponential backoff ✅ |
| HDFS cluster unavailability | High | Low | Fall back to local Parquet in dev |
| Python/Spark version incompatibility | Medium | Low | Lock versions in pyproject.toml ✅ |

## Milestones & Timeline

| Milestone | Week | Status | Deliverable |
|-----------|------|--------|-------------|
| Setup + Preprocessing | 1-2 | ✅ COMPLETE | Preprocessing pipeline, 100 books |
| Shingling + MinHash | 3 | ⏳ PENDING | src/shingling.py, src/minhash.py + tests |
| LSH + Query | 4-5 | ⏳ PENDING | src/lsh.py, src/query.py + integration tests |
| API + UI | 6 | ⏳ PENDING | api/ + frontend/ implementations |
| Testing + Optimization | 6-7 | ⏳ PENDING | Full test suite, performance tuning |
| Report + Demo | 7 | ⏳ PENDING | Final documentation + presentation |

## Configuration & Deployment

### Development Environment
```bash
LSH_ENV=dev
SPARK_MASTER=local[*]
DATA_RAW_PATH=./data/sample/
```

### Cluster Environment
```bash
LSH_ENV=cluster
SPARK_MASTER=spark://master:7077
HDFS_NAMENODE=hdfs://master:9000
DATA_RAW_PATH=hdfs:///project-lsh/datasets/gutenberg_default/raw/
```

See `config/settings.py` for all configuration options.

## Team Roles & Responsibilities

| Team Member | MSSV | Primary Role | Focus Areas |
|-------------|------|--------------|-------------|
| Nguyễn Hoàng Kiên | 2570435 | Preprocessing & Testing | Data pipelines, unit tests, validation |
| Ngô Hoài Tú | 2570536 | LSH Algorithm & Frontend | Shingling, MinHash, LSH, UI |
| Trần Quốc Việt | 2570154 | Lead, Infra, API | Architecture, API, DevOps, experiments |

## Dependencies & Prerequisites

### Required
- Python >= 3.10
- Java 11+ (Spark requirement)
- Git (version control)

### Package Manager
- `uv` (recommended) or pip

### External Services
- Project Gutenberg API (public, no auth required)
- Optional: HDFS cluster for production

### Key Libraries (from pyproject.toml)
- pyspark >= 3.5
- nltk >= 3.8 (stopwords)
- fastapi, uvicorn (API)
- streamlit (UI)
- pytest (testing)

## Known Constraints

1. **Python Modules Are Flat**: `src/` contains flat .py files, not subdirectories
2. **Spark Memory**: Dev mode limited to 2GB (adjust SPARK_DRIVER_MEMORY in config/settings.py)
3. **Sample Data**: 100 books for local dev; larger datasets require HDFS setup
4. **Gutenberg Rate Limiting**: Download script has built-in delays to respect API limits
5. **Test Fixtures**: SparkSession reused across tests via pytest session scope

## Next Steps

### Immediate (Week 3)
1. Implement shingling module + tests
2. Design MinHash algorithm approach
3. Plan LSH bucketing strategy

### Short-term (Week 4-5)
1. Complete MinHash + LSH modules
2. Build integration tests
3. Validate similarity detection accuracy

### Medium-term (Week 6-7)
1. Implement API endpoints
2. Build Streamlit UI
3. Run performance experiments
4. Document findings

## References & Resources

- **Spark Documentation**: https://spark.apache.org/docs/latest/
- **LSH Algorithm**: Mining Massive Datasets (Ch. 3) - Leskovec et al.
- **Project Gutenberg**: https://www.gutenberg.org/
- **Course Materials**: Provided by PGS.TS Thoại Nam
- **Internal Docs**: See `./docs/` for system architecture, code standards, deployment guides

## Document References

- [Codebase Summary](./codebase-summary.md) — Complete file structure & component status
- [System Architecture](./system-architecture.md) — Detailed technical design
- [Code Standards](./code-standards.md) — Development conventions
- [Deployment Guide](./deployment-guide.md) — Setup for dev & cluster
- [Project Roadmap](./project-roadmap.md) — Timeline & progress tracking
