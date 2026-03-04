# LSH Pipeline Walkthrough

**Last Updated**: 2026-03-04

Step-by-step guide explaining how the LSH book similarity pipeline works, from preprocessed tokens to candidate pair retrieval.

## Pipeline Overview

```
DataFrame(book_id, tokens)     ← Preprocessed Parquet
        ↓
[src/shingling.py]             → DataFrame(book_id, shingles: array<string>)
        ↓
[src/minhash.py]               → DataFrame(book_id, signature: array<int>)
        ↓
[src/lsh.py]                   → DataFrame(book_id, band_id, bucket_hash)
        ↓
Candidate pairs (book_id_1, book_id_2)
        ↓
[src/query.py]                 → DataFrame(book_id, similarity[, Title, Author])
        ↓
Top-K similar books for a given query book
```

## Step 1: k-Shingling (`src/shingling.py`)

**Purpose**: Convert token arrays into overlapping word n-grams (shingles) that capture local text patterns.

**How it works**:
1. Take a book's token array, e.g. `["the", "quick", "brown", "fox", "jumps"]`
2. Create sliding windows of k=3 consecutive tokens
3. Join each window with spaces → `"the quick brown"`, `"quick brown fox"`, `"brown fox jumps"`
4. Deduplicate → final shingle set

**Why shingles?** Similar books share similar word sequences. By comparing shingle sets, we measure textual overlap — this is the foundation for Jaccard similarity.

**Key function**: `generate_shingles(df, k=3)`
- Input: `DataFrame(book_id, tokens: array<string>)`
- Output: `DataFrame(book_id, shingles: array<string>)`
- Books with fewer than k tokens are filtered out

**Config**: `SHINGLE_K = 3` (word-level trigrams)

## Step 2: MinHash Signatures (`src/minhash.py`)

**Purpose**: Compress shingle sets into fixed-length signature vectors that preserve Jaccard similarity.

**The problem**: Comparing raw shingle sets is O(|A| + |B|) per pair, and O(N²) pairs for N books. Too slow.

**MinHash property**: For random hash function h:
```
P(min(h(A)) == min(h(B))) = J(A, B)
```
The probability that two sets produce the same minimum hash equals their Jaccard similarity.

**How it works**:
1. Generate 50 (dev) or 100 (cluster) independent hash functions
2. Each hash function: `h_i(x) = ((a_i × md5(x) + b_i) mod PRIME) mod MAX_HASH`
   - `md5` ensures determinism across sessions (not Python's `hash()`)
   - `(a_i, b_i)` are random coefficients, seeded for reproducibility
3. For each book's shingles, compute `min(h_i(shingle) for all shingles)` per hash function
4. Result: signature vector of length 50 (or 100)

**Jaccard estimation**: Count matching positions between two signatures, divide by length.
```python
estimate_jaccard(sig_a, sig_b) = matches / len(sig_a)
```

**Key function**: `compute_minhash_signatures(df, spark, num_hashes=50)`
- Input: `DataFrame(book_id, shingles: array<string>)`
- Output: `DataFrame(book_id, signature: array<int>)`
- Hash params are broadcast to all Spark executors

**Config**: `MINHASH_NUM_HASHES = 50` (dev) / `100` (cluster)

## Step 3: LSH Banding (`src/lsh.py`)

**Purpose**: Avoid comparing all N² signature pairs. Instead, hash signatures into buckets so only likely-similar books are compared.

**The S-curve insight**: With b bands of r rows:
```
P(candidate) = 1 - (1 - s^r)^b
```
This creates a steep S-shaped curve — books above the threshold are almost certainly candidates, books below are almost certainly not.

**How it works**:
1. Split each signature into b=10 bands of r=5 rows
2. For each band, take the r signature values, serialize to bytes via `struct.pack`
3. Hash the bytes with `md5` → bucket ID (deterministic)
4. Result: each book gets one (band_id, bucket_hash) per band

**Example** (signature length 10, b=2, r=5):
```
Signature: [3, 7, 1, 9, 2, 5, 8, 4, 6, 0]
Band 0: [3, 7, 1, 9, 2] → md5 → bucket_hash_0
Band 1: [5, 8, 4, 6, 0] → md5 → bucket_hash_1
```

**Candidate pair finding**: Self-join LSH index on (band_id, bucket_hash).
- Two books in the same bucket in ANY band → candidate pair
- Filter: `book_id_1 < book_id_2` (no self-pairs, no duplicates)

**Key functions**:
- `build_lsh_index(df, num_bands=10, rows_per_band=5)` → `DataFrame(book_id, band_id, bucket_hash)`
- `find_candidate_pairs(lsh_index_df)` → `DataFrame(book_id_1, book_id_2)`

**Config**: `LSH_NUM_BANDS = 10`, `LSH_ROWS_PER_BAND = 5` → threshold ≈ 0.47

## Step 4: Full Pipeline (`src/main.py`)

**Purpose**: Orchestrate all steps end-to-end.

```python
run_pipeline()
  1. Load preprocessed tokens from Parquet
  2. Generate shingles
  3. Compute MinHash signatures (cached)
  4. Build LSH index (cached)
  5. Save both to Parquet (signatures/ + lsh_index/)
```

**Run**: `LSH_ENV=dev uv run python -m src.main`

**Output files**:
- `data/output/signatures/` — MinHash signatures per book
- `data/output/lsh_index/` — LSH band/bucket index

## Step 5: Query Engine (`src/query.py`)

**Purpose**: Given a `book_id`, find the top-K most similar books using the precomputed LSH index and MinHash signatures.

**Why not just compare all pairs?** The LSH index narrows candidates to books sharing at least one bucket. We only compute exact Jaccard similarity on this small candidate set — not the full N² pairs.

**How it works**:

```
find_similar_books(spark, "pg1234", top_k=10)
│
├── 1. Load signatures + lsh_index from Parquet
├── 2. Lookup query book's signature
│      → If not found → return empty DataFrame
├── 3. Get query book's (band_id, bucket_hash) tuples
├── 4. Join against full index to find candidate book_ids
│      → Filter out query book itself
│      → .distinct() to deduplicate
├── 5. Join candidates with their signatures
├── 6. Broadcast query signature, apply Jaccard UDF
│      → UDF calls estimate_jaccard(query_sig, candidate_sig)
├── 7. Sort desc by similarity, limit top_k
└── 8. (Optional) Enrich with Title/Author from metadata CSV
```

**Step-by-step example**:

Suppose `pg1234` has signature `[3, 7, 1, 9, 2, 5, 8, 4, 6, 0]` and the LSH index has:

```
book_id  | band_id | bucket_hash
---------|---------|------------
pg1234   | 0       | 42
pg1234   | 1       | 99
pg5678   | 0       | 42      ← shares bucket with pg1234 in band 0
pg9999   | 1       | 99      ← shares bucket with pg1234 in band 1
pg0000   | 0       | 77      ← no shared bucket
```

1. **Query buckets**: `[(0, 42), (1, 99)]`
2. **Candidates**: `{pg5678, pg9999}` (share at least one bucket)
3. **Jaccard computation**: compare signatures pairwise via `estimate_jaccard`
4. **Ranking**: sort by similarity descending, limit to `top_k`

**Broadcast UDF pattern**: The query signature is broadcast to all executors once, avoiding repeated serialization per row.

```python
query_sig_bc = spark.sparkContext.broadcast(query_signature)

@F.udf(FloatType())
def jaccard_udf(candidate_sig):
    return float(estimate_jaccard(query_sig_bc.value, candidate_sig))
```

**Metadata enrichment** (`_enrich_with_metadata`):
- Reads `sample_metadata.csv` (columns: `GutenbergID, Title, Author, Bookshelf, Link`)
- Converts `GutenbergID` → `book_id` by prepending `"pg"` (e.g. `17135` → `pg17135`)
- Left-joins results to add `Title` and `Author` columns
- Silently skipped if CSV not available (try/except)

**Edge cases**:
- Unknown `book_id` → returns empty DataFrame with schema `(book_id, similarity)`, no exception
- No candidates (unique buckets) → empty result
- Metadata CSV missing → results returned without Title/Author columns

**Key function**: `find_similar_books(spark, book_id, top_k=10)`
- Input: `book_id` string
- Output: `DataFrame(book_id, similarity[, Title, Author])` sorted desc
- Accepts optional `signatures_df` and `lsh_index_df` params for testing

**Run**:
```bash
# Via Makefile
make query BOOK=pg1234

# Via main pipeline
LSH_ENV=dev uv run python -m src.main query pg1234 10

# Direct module
LSH_ENV=dev uv run python -m src.query pg1234 10
```

**Config**: `DEFAULT_TOP_K = 10`

## Parameter Tuning Guide

| Parameter | Effect of Increasing | Trade-off |
|-----------|---------------------|-----------|
| `SHINGLE_K` | More specific shingles | Fewer matches, higher precision |
| `MINHASH_NUM_HASHES` | More accurate estimates | Slower computation |
| `LSH_NUM_BANDS` | Lower threshold, more candidates | More false positives |
| `LSH_ROWS_PER_BAND` | Higher threshold, fewer candidates | More false negatives |

**Threshold formula**: `t ≈ (1/b)^(1/r)`

| b (bands) | r (rows) | Threshold |
|-----------|----------|-----------|
| 10 | 5 | 0.47 |
| 20 | 5 | 0.37 |
| 5 | 10 | 0.58 |

## Hashing Strategy

All hashing uses `hashlib.md5` for determinism:
- **MinHash shingle hashing**: `int(md5(shingle.encode()).hexdigest(), 16) % PRIME`
- **LSH band hashing**: `int(md5(struct.pack(">Ni", *values)).hexdigest(), 16) % PRIME`
- **PRIME**: `2^31 - 1` (Mersenne prime)

Python's built-in `hash()` is **not used** because it's randomized across sessions (PYTHONHASHSEED).

## Notebook Demo

`notebooks/03_lsh_pipeline_demo.ipynb` demonstrates the full pipeline in two modes:
1. **Pure Python** (cells 6-14): Small 4-doc corpus, step-by-step with print output
2. **PySpark** (cell 16): Full pipeline on 93-book sample using `src` modules
3. **S-curve visualization** (cell 18): matplotlib plot of P(candidate) vs Jaccard similarity
