# LSH Book Recommendation — Project Roadmap

**Last Updated**: 2026-03-03
**Current Version**: 0.1.0
**Project Duration**: 7 weeks (HK2 2025-2026)
**Team**: Nguyễn Hoàng Kiên, Ngô Hoài Tú, Trần Quốc Việt

## Executive Summary

This roadmap tracks implementation progress for the LSH Book Recommendation system across 7 weeks. Week 1-2 (Foundation) is complete with preprocessing pipeline operational. Weeks 3-7 focus on core LSH algorithms, serving layer, and experiments.

## Phase Overview

### Phase 1: Foundation & Data Ingestion (Week 1-2)
**Status**: ✅ **COMPLETE** | **Completion Date**: 2026-03-03
**Progress**: 100%

Established project infrastructure, data acquisition pipeline, preprocessing framework, and unit testing foundation.

**Completed Deliverables**:
- Project repository setup with proper structure
- Docker dev environment (PySpark + Jupyter)
- Gutenberg downloader with retry/backoff logic
- Sample dataset generation (100 books, stratified sampling)
- Text cleaning utilities
- Preprocessing pipeline (tokenization, stopword removal)
- Configuration management (dev/cluster modes)
- Unit tests (10 tests, all passing)
- Documentation (README, guides)

**Key Metrics**:
- 100 sample books downloaded and processed
- 93 books successfully preprocessed
- 10 unit tests passing
- Preprocessing speed: ~1 min for 100 books (local[*])

---

### Phase 2: Core LSH Algorithm (Week 3-5)
**Status**: ⏳ **IN PROGRESS** (Week 3 COMPLETE)
**Week 3 Completion Date**: 2026-03-03
**Target Completion (Weeks 4-5)**: 2026-03-31
**Progress**: 33% (1 of 3 weeks)

Implement the core LSH pipeline: shingling, MinHash signatures, LSH bucketing, and query engine.

#### Week 3: Shingling Module ✅ COMPLETE
**Completion**: 2026-03-03

**Delivered**:
- [x] `src/shingling.py` - k-shingle generation (62 LOC)
- [x] Unit tests (6 test cases, all passing)
- [x] Integration with preprocessing output (verified)
- [x] Configurable k parameter (default k=3, runtime-tunable)

**Achievements**:
- ✅ Word-level k-shingling with PySpark UDF
- ✅ Sliding window generation (e.g., [a, b, c] → "a b c")
- ✅ Deduplication at row level
- ✅ Output: DataFrame(book_id, shingles: array<string>)
- ✅ Public API: `generate_shingles()`, `run_shingling()`

**Tests**: 6 tests covering k-values, edge cases, empty tokens, single tokens

#### Week 4: MinHash Module ✅ COMPLETE
**Completion**: 2026-03-03

**Delivered**:
- [x] `src/minhash.py` - MinHash signature computation (100 LOC)
- [x] Configurable hash function count (default 50/100)
- [x] Unit tests (6 test cases, all passing)
- [x] Signature validation tests (Jaccard estimation)

**Achievements**:
- ✅ Universal hashing with md5 determinism
- ✅ Hash parameters (a, b) generation with seed=42
- ✅ Broadcast parameter optimization for Spark
- ✅ Per-shingle minimum computation for each hash function
- ✅ Output: DataFrame(book_id, signature: array<int>)
- ✅ Public API: `compute_minhash_signatures()`, `estimate_jaccard()`, `run_minhash()`

**Tests**: 6 tests covering hash params, signature length, Jaccard estimation, edge cases

#### Week 5: LSH Indexing & Pipeline ✅ COMPLETE
**Completion**: 2026-03-03

**Delivered**:
- [x] `src/lsh.py` - LSH banding and bucketing (112 LOC)
- [x] `src/main.py` - Full pipeline orchestration (72 LOC)
- [x] Integration tests (6 test cases, all passing)
- [x] End-to-end pipeline verification

**Achievements**:
- ✅ Band-based LSH with md5 bucketing
- ✅ Candidate pair finding via self-join
- ✅ Full pipeline: preprocess → shingle → minhash → lsh → save
- ✅ Output: DataFrame(book_id, band_id, bucket_hash)
- ✅ Parquet serialization for signatures & LSH index
- ✅ Public API: `build_lsh_index()`, `find_candidate_pairs()`, `run_lsh()`, `run_pipeline()`

**Tests**: 6 tests covering band splitting, hashing, candidate pairs, parameter validation
**Performance**: ~2-3 min for 100 books (local[*])
**Query Engine**: Stub (`src/query.py`) — deferred to Phase 3

**Summary Stats**:
- **Total Code Added**: 346 LOC (shingling + minhash + lsh + main)
- **Total Tests**: 18 new tests (6+6+6), all passing
- **Total Test Suite**: 28/28 tests passing

---

### Phase 3: Serving Layer (Week 6)
**Status**: ⏳ **NOT STARTED**
**Planned Start**: 2026-04-01
**Target Completion**: 2026-04-07
**Progress**: 0%

Implement REST API and web UI for querying the LSH index.

#### FastAPI REST API

**Planned Endpoints**:
- [ ] `GET /health` - Service status check
- [ ] `POST /query` - Find similar books (request: book_id, top_k)
- [ ] `GET /dataset/info` - Dataset statistics
- [ ] `GET /dataset/books` - List all available books
- [ ] `GET /dataset/books/{id}` - Get book metadata

**Implementation Details**:
- Location: `api/main.py` + `api/routers/`
- Use Pydantic models for validation
- Add CORS headers for frontend
- Comprehensive error handling

**Deliverables**:
- [ ] `api/main.py` - FastAPI app entry
- [ ] `api/routers/books.py` - Book-related endpoints
- [ ] `api/routers/metrics.py` - Metrics endpoints
- [ ] `api/schemas.py` - Pydantic request/response models
- [ ] API unit tests

#### Streamlit Web UI

**Planned Pages**:
- [ ] `1_Browse_Books.py` - Browse all books with search
- [ ] `2_Similar_Books.py` - Query similar books by title
- [ ] `3_Dataset_Management.py` - Upload, refresh data
- [ ] `4_Dashboard.py` - Metrics and performance stats

**Features**:
- Search/filter books by title or author
- Similarity query with adjustable top_k
- Result visualization
- Dataset refresh capability

**Deliverables**:
- [ ] `frontend/app.py` - Main Streamlit entry
- [ ] `frontend/pages/*.py` - 4 page implementations
- [ ] Style configuration

---

### Phase 4: Testing & Optimization (Week 7)
**Status**: ⏳ **NOT STARTED**
**Planned Start**: 2026-04-08
**Target Completion**: 2026-04-14
**Progress**: 0%

Comprehensive testing, performance optimization, experiments, and final documentation.

**Planned Deliverables**:
- [ ] End-to-end integration tests
- [ ] Performance benchmarks (preprocessing, query latency)
- [ ] Scalability experiments (100, 500, 1000 books)
- [ ] LSH parameter tuning experiments
- [ ] Comparison with baseline methods
- [ ] Final project report
- [ ] Presentation slides
- [ ] Performance optimization pass

**Experiment Notebook** (`notebooks/04_experiments.ipynb`):
- [ ] Parameter sensitivity analysis
- [ ] Query latency benchmarks
- [ ] Recall/precision metrics
- [ ] Scalability analysis
- [ ] Result visualizations

**Definition of Done**:
- Test coverage > 80%
- All tests passing
- Performance targets met (query < 1 sec)
- Report complete

---

## Detailed Milestone Schedule

| Week | Phase | Key Milestone | Status | Target Date |
|------|-------|---------------|--------|-------------|
| 1-2 | Foundation | Preprocessing pipeline complete | ✅ Complete | 2026-03-03 |
| 3 | LSH - Shingling | Shingle generation working | ✅ Complete | 2026-03-03 |
| 4 | LSH - MinHash | MinHash signatures computed | ✅ Complete | 2026-03-03 |
| 5 | LSH - Query | LSH index + pipeline | ✅ Complete | 2026-03-03 |
| 6 | Serving | API + UI deployed | ⏳ Pending | 2026-04-07 |
| 7 | Testing/Report | Final report + presentation | ⏳ Pending | 2026-04-14 |

## Success Criteria

### Week 1-2 ✅ ACHIEVED
- [x] Preprocessing pipeline working
- [x] 100 books successfully processed
- [x] 10 unit tests passing
- [x] Docker dev environment ready

### Week 3-5 ✅ ACHIEVED (LSH Algorithm Complete)
- [x] Shingling module complete and tested (6 tests)
- [x] MinHash signatures computed correctly (6 tests)
- [x] LSH banding & bucketing working (6 tests)
- [x] Full pipeline end-to-end tested
- [x] 28/28 integration tests passing
- [x] All modules publicly documented with APIs
- [x] Query engine design ready (implementation Phase 3)

### Week 6 TARGETS (Serving)
- [ ] REST API accepting queries
- [ ] Streamlit UI responsive and usable
- [ ] API + UI communication working end-to-end

### Week 7 TARGETS (Testing/Deployment)
- [ ] All tests passing (coverage > 80%)
- [ ] Performance benchmarks documented
- [ ] Scalability validated
- [ ] Final report complete

## Risk Assessment & Mitigation

| Risk | Severity | Likelihood | Mitigation |
|------|----------|-----------|-----------|
| LSH algorithm correctness issues | High | Medium | Early validation with small dataset, manual similarity checking |
| Spark cluster unavailability | High | Low | Fallback to local Spark mode, Docker environment |
| Query performance below targets | Medium | Medium | Parameter tuning experiments, algorithm optimization |
| API/UI integration delays | Low | Medium | Start implementing in parallel with algorithm |
| Testing coverage gaps | Medium | Medium | TDD approach, pair programming on critical modules |

## Dependency Map

```
Week 1-2 (Foundation) ✅
    ↓
Week 3 (Shingling) ✅
    ↓
Week 4 (MinHash) ✅ — depends on Week 3
    ↓
Week 5 (LSH + Pipeline) ✅ — depends on Week 4
    ↓
Week 6 (API + UI) — depends on Week 5 ✅
    ↓
Week 7 (Testing + Report) — depends on Weeks 5-6
```

**STATUS SUMMARY**: 3 weeks ahead of schedule (all LSH core algorithms complete by 2026-03-03)

## Resource Allocation

| Team Member | Week 1-2 | Week 3-5 | Week 6 | Week 7 |
|-------------|----------|----------|--------|--------|
| Nguyễn Hoàng Kiên | Preprocessing + tests | Shingling + MinHash + tests | API testing | Test coverage, report |
| Ngô Hoài Tú | Docker setup | MinHash + LSH | Frontend UI | Optimization experiments |
| Trần Quốc Việt | Architecture + infra | LSH + Query engine | API implementation | Report + presentation |

## Current Development Focus

### Immediate Next Steps (Week 3)
1. Design shingling algorithm approach
2. Create `src/shingling.py` module
3. Write unit tests for shingle generation
4. Verify output format matches MinHash expectations

### Progress Tracking

Weekly status updates:
- Week 1-2: ✅ COMPLETE (2026-03-03)
- Week 3: ✅ COMPLETE (2026-03-03) — Shingling module + 6 tests
- Week 4: ✅ COMPLETE (2026-03-03) — MinHash module + 6 tests
- Week 5: ✅ COMPLETE (2026-03-03) — LSH module + Pipeline + 6 tests
- Week 6: ⏳ Target 2026-04-07 — API + UI implementation
- Week 7: ⏳ Target 2026-04-14 — Query engine, testing, final report

## Key Decisions & Constraints

1. **Algorithm Choice**: MinHash + LSH (as per course requirements)
2. **Shingle Size**: k=3 for development, configurable for experiments
3. **Hash Functions**: 50 (dev) / 100 (cluster)
4. **LSH Parameters**: 10 bands × 5 rows (tunable)
5. **Data Format**: Parquet for efficient storage/retrieval
6. **Dev Environment**: Docker with local[*] Spark
7. **Cluster Environment**: Spark 3.5+, HDFS for distributed storage

## Related Documentation

- [Project Overview & PDR](./project-overview-pdr.md) — Full requirements and goals
- [System Architecture](./system-architecture.md) — Technical design (updated with MD5 hashing details)
- [Codebase Summary](./codebase-summary.md) — Current code structure (updated with Week 3-5 implementation)
- [Deployment Guide](./deployment-guide.md) — Setup & deployment

## Implementation Highlights

### Code Quality
- **Total LOC Added**: 346 (shingling 62 + minhash 100 + lsh 112 + main 72)
- **Documentation**: Full public API tables for 4 modules
- **Test Coverage**: 18 new tests, 100% pass rate (28/28 total)

### Technology Stack
- **Hashing**: `hashlib.md5` for deterministic, cross-session consistency
- **Spark Integration**: UDF+broadcast for efficient distributed hashing
- **Scalability**: O(1) band lookup, O(K) candidate similarity

### Next Phase (Week 6)
- Implement query engine (`src/query.py`) — Jaccard similarity computation
- REST API endpoints (`api/routers/books.py`)
- Streamlit UI pages (`frontend/pages/2_Similar_Books.py`)

## Document Maintenance

This roadmap updated: 2026-03-03

**Next Review Target**: 2026-03-17 (mid-Week 6)
