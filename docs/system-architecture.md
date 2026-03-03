# System Architecture

**Last Updated**: 2026-03-03
**Version**: 0.1.0
**Project**: LSH Book Recommendation

## Overview

LSH Book Recommendation implements a distributed Locality-Sensitive Hashing system on Apache Spark for large-scale book similarity detection. The architecture separates data ingestion, batch processing, and query serving into distinct layers with clear responsibilities.

## Architectural Pattern

### Pattern Classification
**Primary Pattern**: Data Pipeline with Query Service
**Secondary Patterns**:
- Pipeline Pattern (data ingestion → processing → storage)
- Event-Driven Pattern (Streamlit triggers queries)
- API Gateway Pattern (FastAPI exposes query engine)

### Design Philosophy
- **Separation of Concerns**: Distinct layers for ingestion, compute, and serving
- **Scalability**: Distributed processing via Spark RDDs
- **Accessibility**: Web UI and REST API for different use cases
- **Reproducibility**: Configuration-driven processing with environment variables

## System Components

### Layer 1: Data Ingestion

#### 1.1 Gutenberg Downloader
**Location**: `scripts/gutenberg_downloader.py`
**Responsibility**: Fetch book metadata and content from Project Gutenberg

**Key Functions**:
- Search Project Gutenberg catalog by genre/language
- Download book metadata (title, author, language)
- Fetch raw text content from Gutenberg mirrors
- Handle rate limiting and failures gracefully

**Input**: Query parameters (genre, language, count)
**Output**: Text files + metadata CSV to `data/raw/`

#### 1.2 Text Preprocessing
**Location**: `scripts/text_cleaning_utils.py`
**Responsibility**: Normalize and clean text data

**Operations**:
- Lowercase conversion
- Whitespace normalization
- Punctuation handling
- Stop word filtering (optional)
- Token validation

#### 1.3 HDFS Integration
**Location**: `scripts/hdfs_uploader.py`
**Responsibility**: Upload processed data to Hadoop Distributed File System

**Operations**:
- Connect to HDFS cluster
- Create directory structure
- Upload files with replication
- Verify uploads

**Target**: `hdfs:///project-lsh/datasets/gutenberg_*/raw/`

### Layer 2: Batch Processing (Spark)

#### 2.1 Preprocessing Pipeline
**Location**: `src/preprocessing.py`
**Status**: Implemented (93 books validated)
**Input**: Raw `.txt` files from `DATA_RAW_PATH`
**Output**: `DataFrame(book_id: string, tokens: array<string>)` — Parquet at `data/output/cleaned/`

**Pipeline Steps**:
1. `load_raw_books(spark)` — `wholeTextFiles` → `DataFrame(path, content)`
2. Extract `book_id` via regex from file path (`pg\d+`)
3. Strip Gutenberg headers (delegates to `scripts/text_cleaning_utils.strip_gutenberg_headers`)
4. Lowercase via `F.lower`
5. Regex clean — remove non-alpha chars (`[^a-z\s]`)
6. Tokenize on whitespace (`F.split`)
7. Broadcast NLTK English stopwords; filter single-char tokens and stopwords via UDF
8. `run_preprocessing()` saves Parquet then reads back to avoid recomputation

**Dependencies**: `nltk>=3.8` (stopwords corpus, auto-downloaded on first run)

#### 2.2 Shingling Module
**Location**: `src/shingling.py`
**Status**: Implemented (62 LOC)
**Input**: DataFrame(book_id, tokens: array<string>)
**Output**: DataFrame(book_id, shingles: array<string>)

**Algorithm**:
```
For each book's token array:
  1. Create sliding windows of k consecutive tokens
  2. Join each window with spaces (e.g., [a, b, c] → "a b c")
  3. Deduplicate shingles (convert to set, keep as array)
  4. Filter out books with <k tokens (return empty arrays)
```

**Configuration**: `SHINGLE_K=3` (dev/cluster) — customizable in settings.py
**Public API**: `generate_shingles(df, k)`, `run_shingling(input_path)`

#### 2.3 MinHash Computation
**Location**: `src/minhash.py`
**Status**: Implemented (100 LOC)
**Input**: DataFrame(book_id, shingles: array<string>)
**Output**: DataFrame(book_id, signature: array<int>)

**Algorithm**:
```
For each shingle set:
  1. Generate N independent hash functions: h_i(x) = ((a_i × md5(x) + b_i) mod PRIME) mod MAX_HASH
  2. For each hash function, compute minimum hash over all shingles
  3. Return signature = [h1_min, h2_min, ..., hN_min] (length N)
```

**Hash Function**: Universal hashing with md5 determinism
- Base hash: `hashlib.md5(shingle).hexdigest()` → int
- Parameters: random (a, b) pairs seeded with 42 for reproducibility
- Collision-resistant, deterministic across sessions

**Configuration**: `MINHASH_NUM_HASHES=50` (dev) / `100` (cluster)
**Public API**: `compute_minhash_signatures(df, spark, num_hashes)`, `estimate_jaccard(sig_a, sig_b)`, `run_minhash(input_path)`

#### 2.4 LSH Indexing
**Location**: `src/lsh.py`
**Status**: Implemented (112 LOC)
**Input**: DataFrame(book_id, signature: array<int>)
**Output**: DataFrame(book_id, band_id, bucket_hash)

**Algorithm**:
```
For each signature:
  1. Split into b bands of r rows each (b × r ≤ signature length)
  2. For each band, serialize row values to bytes, hash via md5 → 32-bit int
  3. Return array of (band_id, bucket_hash) tuples
  4. Explode to one row per (book, band, bucket) triplet
```

**Band Hashing**: md5 for determinism
- Pack integers as struct: `struct.pack(f">>{len}i", *row_values)`
- Hash bytes: `hashlib.md5(data).hexdigest()` → int mod PRIME

**Candidate Pair Finding**: Self-join on (band_id, bucket_hash)
- Books in same bucket in any band → candidate pair
- Deduplication: book_id_1 < book_id_2 (no self-pairs)

**Parameters**:
- `LSH_NUM_BANDS=10` (dev) / `20` (cluster) — Number of bands
- `LSH_ROWS_PER_BAND=5` (both) — Rows per band
- Constraint: `num_bands × rows_per_band ≤ num_hashes`

**Public API**: `build_lsh_index(df, num_bands, rows_per_band)`, `find_candidate_pairs(lsh_index_df)`, `run_lsh(input_path)`

#### 2.5 Evaluation Module
**Location**: `src/evaluation/`
**Input**: Query results vs ground truth
**Output**: Performance metrics

**Metrics**:
- Precision: Correct results / Total returned
- Recall: Correct results / Total true positives
- F1 Score: Harmonic mean of precision & recall

### Layer 3: Query Service

#### 3.1 FastAPI Server
**Location**: `api/main.py`
**Responsibility**: Expose LSH index via REST API

**Architecture**:
```
FastAPI App
├── CORS middleware
├── Health check endpoint
├── Routers:
│   ├── /health → status
│   ├── /query → similarity search
│   ├── /dataset/info → statistics
│   └── /dataset/books → listing
└── Pydantic models for validation
```

**Key Endpoints**:

| Endpoint | Method | Purpose | Response |
|----------|--------|---------|----------|
| `/health` | GET | Service status | `{"status": "ok"}` |
| `/query` | POST | Find similar books | `QueryResponse(results=[...])` |
| `/dataset/info` | GET | Dataset statistics | `{"total_books": N, ...}` |
| `/dataset/books` | GET | List all books | `[{"id": "...", "title": "..."}, ...]` |

**Schemas** (`api/schemas.py`):
```python
class QueryRequest(BaseModel):
    book_id: str
    top_k: int = 10

class SimilarBook(BaseModel):
    id: str
    title: str
    author: str
    similarity: float

class QueryResponse(BaseModel):
    query_book: str
    results: List[SimilarBook]
    execution_time: float
```

#### 3.2 Query Engine
**Location**: `src/query/`
**Responsibility**: Execute similarity searches

**Algorithm**:
```
Given query book:
  1. Retrieve query book signature
  2. Hash signature into LSH buckets
  3. Retrieve all books in matching buckets
  4. Compute exact Jaccard similarity with candidates
  5. Sort by similarity, return top-K
```

**Complexity**:
- Bucket lookup: O(1) average
- Exact similarity: O(K * shingle_set_size)
- Total: O(K * average_bucket_size)

### Layer 4: User Interface

#### 4.1 Streamlit Frontend
**Location**: `frontend/app.py`
**Responsibility**: Interactive web interface for similarity search

**Pages**:
1. **Search** - Enter book title, get similar books
2. **Dataset** - Browse all available books
3. **Settings** - Configure LSH parameters (if admin)
4. **About** - Project information

**Architecture**:
```
Streamlit App
├── Session state (query history)
├── API client (FastAPI integration)
├── Pages:
│   ├── search.py (query interface)
│   ├── dataset.py (book browser)
│   └── settings.py (configuration)
└── Components (reusable UI)
```

**Data Flow**:
```
User Input (Streamlit)
    ↓
API Call (FastAPI)
    ↓
Query Engine (Spark)
    ↓
LSH Index Lookup
    ↓
Result Formatting
    ↓
Display in Streamlit
```

## Configuration Management

### Environment-Based Configuration
**Pattern**: External configuration via environment variables

**File Structure**:
```
config/
├── dev.env              # Development settings
├── cluster.env          # Cluster settings
└── settings.py          # Configuration class
```

**Settings Class** (`config/settings.py`):
Contains two dataclasses:
- `DevConfig`: Local mode (Spark local[*], 2GB memory, ./data/sample/)
- `ClusterConfig`: Cluster mode (Spark master, 4GB memory, HDFS paths)

Selected via `LSH_ENV` environment variable.

**Key Configuration Parameters**:
```python
# Both modes
SPARK_APP_NAME = "LSH-Book-Recommendation"
SHINGLE_K = 3
LSH_ROWS_PER_BAND = 5

# Dev mode
SPARK_MASTER = "local[*]"
SPARK_DRIVER_MEMORY = "2g"
SPARK_EXECUTOR_MEMORY = "2g"
MINHASH_NUM_HASHES = 50
LSH_NUM_BANDS = 10
DATA_RAW_PATH = "./data/sample/"

# Cluster mode
SPARK_MASTER = "spark://master:7077"
SPARK_DRIVER_MEMORY = "4g"
SPARK_EXECUTOR_MEMORY = "4g"
MINHASH_NUM_HASHES = 100
LSH_NUM_BANDS = 20
DATA_RAW_PATH = "hdfs:///project-lsh/datasets/gutenberg_default/raw/"
```

**Loading**:
```bash
# Development
LSH_ENV=dev python -m scripts.download_and_upload_gutenberg

# Cluster
LSH_ENV=cluster spark-submit --master spark://master:7077 src/main.py
```

## Data Flow Diagrams

### Batch Processing Pipeline
```
Project Gutenberg
        ↓
[scripts/gutenberg_downloader.py]
        ↓
data/raw/  (text files)
        ↓
HDFS  (via scripts/hdfs_uploader.py)
        ↓
[src/preprocessing.py] → DataFrame(book_id, tokens) → Parquet (data/output/cleaned/)
        ↓
[src/shingling] → shingle sets
        ↓
[src/minhash] → signatures
        ↓
[src/lsh] → buckets
        ↓
LSH Index  (persisted)
```

### Query Flow
```
Streamlit UI
    ↓
FastAPI /query endpoint
    ↓
[src/query] Query Engine
    ├─ Hash query book to LSH buckets
    ├─ Retrieve candidates from buckets
    └─ Compute exact Jaccard similarity
    ↓
Sorted Results
    ↓
Response to Streamlit
    ↓
Display Results
```

## Performance Considerations

### Batch Processing
**Complexity**: O(N × M) where N=books, M=avg_doc_length
**Optimization**:
- RDD caching of intermediate results
- Partitioning by book ID
- Parquet format for storage

### Query Performance
**Complexity**: O(log(N) + K) where N=books, K=top-k results
- LSH bucket lookup: O(log(N)) via Spark SQL
- Similarity computation: O(K × avg_bucket_size)
- Target: <100ms response time for 100K books

### Storage
- Raw text: ~1GB per 1000 books
- Parquet (processed): ~200MB per 1000 books
- LSH index: ~500MB per 1000 books

## Scalability Architecture

### Horizontal Scaling (Spark)
- **Partitioning**: Books distributed across executors
- **Parallelism**: RDD operations parallelized
- **Storage**: HDFS replication factor (default 3)

### Vertical Scaling (Query Service)
- **Caching**: In-memory LSH index
- **Connection Pooling**: Spark SQL connections
- **Batch Queries**: Multiple queries in parallel

### Bottlenecks & Solutions
| Bottleneck | Solution |
|-----------|----------|
| HDFS I/O | Parquet columnar format, caching |
| Spark shuffle | Partitioning strategy, band selection |
| API response | Result pagination, query optimization |
| Memory | RDD persistence tuning, executor config |

## Deployment Architecture

### Development Mode
```
Local Machine
├── Python venv
├── Local Spark (1 executor)
├── data/sample/ (local storage)
└── Services:
    ├── FastAPI (localhost:8000)
    └── Streamlit (localhost:8501)
```

**Setup**:
```bash
make sync              # Install dependencies
make download-sample   # Download sample data
make api              # Start API
make ui               # Start UI (separate terminal)
```

### Cluster Mode
```
Hadoop Cluster
├── HDFS (data storage)
├── Spark (1 master + N executors)
├── Services:
│   ├── FastAPI (on master)
│   └── Streamlit (on master)
└── ssh tunnel for local access
```

**Setup**:
```bash
make cluster-deploy        # Copy code to cluster
make cluster-upload        # Upload data to HDFS
make cluster-run          # Run pipeline on Spark
make cluster-ui           # Start Streamlit on cluster
```

## Error Handling & Resilience

### Input Validation
- **Gutenberg API**: Retry on network failure (3 attempts)
- **File Upload**: Verify file integrity via checksum
- **Query**: Validate book ID exists in index

### Fault Tolerance
- **Spark**: RDD replication (default 3x)
- **HDFS**: Data replication across nodes
- **API**: Graceful degradation (return partial results)

### Monitoring & Logging
- **Application Logs**: FastAPI/Streamlit logs to stdout
- **Spark Logs**: Spark history server on cluster
- **Metrics**: Execution time, query count (in response headers)

## Security Considerations

### Data Security
- **HDFS**: Standard Hadoop permissions (not enabled in dev)
- **API**: No authentication in dev, ready for production OAuth
- **Secrets**: Configuration via environment variables (never hardcoded)

### Input Validation
- **Query Engine**: Validate book ID format
- **API**: Pydantic schema validation
- **Frontend**: User input sanitization in Streamlit

## Extension Points

### Adding New LSH Parameters
1. Update `config/settings.py`
2. Add environment variable
3. Pass to `src/lsh/` module
4. Rebuild index

### Adding New Data Sources
1. Create new downloader in `scripts/`
2. Implement text cleaning
3. Upload to HDFS
4. Update preprocessing pipeline

### Custom Similarity Metrics
1. Extend `src/query/` module
2. Implement similarity function
3. Update response schema
4. Add to API endpoint

## References

### Internal Documentation
- [Project Overview & PDR](./project-overview-pdr.md)
- [Codebase Summary](./codebase-summary.md)
- [Code Standards](./code-standards.md)

### External Resources
- [Apache Spark Documentation](https://spark.apache.org/docs/)
- [Project Gutenberg](https://www.gutenberg.org/)
- [LSH Theory](https://en.wikipedia.org/wiki/Locality-sensitive_hashing)
- [Jaccard Similarity](https://en.wikipedia.org/wiki/Jaccard_index)

## Unresolved Questions

1. **Exact vs Approximate**: When should we use exact Jaccard vs LSH approximation?
2. **Parameter Tuning**: How to automatically optimize NUM_BANDS and ROWS_PER_BAND?
3. **Incremental Indexing**: Can we support adding new books without full recomputation?
4. **Multi-Language Support**: How to handle books in different languages?
