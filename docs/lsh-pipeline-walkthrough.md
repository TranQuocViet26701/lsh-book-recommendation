# LSH Pipeline Walkthrough

**Last Updated**: 2026-03-03

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
