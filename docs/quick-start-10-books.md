# Quick Start: Full Pipeline with 10 Books

Run the entire workflow end-to-end — from raw text files to LSH candidate pairs — using just 10 books.

## Prerequisites

```bash
# Install dependencies
uv sync --all-extras

# Verify Java (required by PySpark)
java -version  # Java 11+
```

## Step 0: Prepare 10 Books

Pick any 10 `.txt` files from the sample dataset into a working directory.

```bash
# Create a small working directory
mkdir -p data/demo10

# Copy first 10 books from sample
ls data/sample/*.txt | head -10 | xargs -I{} cp {} data/demo10/
ls data/demo10/  # verify 10 files
```

## Step 1: Preprocessing

Convert raw text into clean token arrays.

```bash
LSH_ENV=dev uv run python -c "
from src.preprocessing import create_spark_session, load_raw_books, preprocess_books
from config.settings import config

spark = create_spark_session()

# Override raw path to use our 10-book directory
rdd = spark.sparkContext.wholeTextFiles('./data/demo10/*.txt')
raw_df = rdd.toDF(['path', 'content'])
print(f'Loaded {raw_df.count()} raw books')

# Preprocess: strip headers, lowercase, tokenize, remove stopwords
tokens_df = preprocess_books(raw_df, spark)
print(f'Preprocessed {tokens_df.count()} books')
tokens_df.show(10, truncate=80)

# Save to Parquet
output_path = './data/output/cleaned/'
tokens_df.coalesce(1).write.mode('overwrite').parquet(output_path)
print(f'Saved to {output_path}')
"
```

**Expected output**: 10 books with token arrays, saved to `data/output/cleaned/`.

**What happens here**:
1. `wholeTextFiles` reads each `.txt` as one record (path, content)
2. Extract `book_id` from filename (e.g., `pg10007`)
3. Strip Project Gutenberg headers/footers
4. Lowercase → remove non-alpha chars → tokenize on whitespace
5. Remove NLTK English stopwords and single-char tokens

## Step 2: Run LSH Pipeline

Now run the LSH pipeline on the preprocessed tokens.

```bash
LSH_ENV=dev uv run python -m src.main
```

**Expected output**:
```
[1/5] Loading tokens from ./data/output/cleaned/
      Loaded 10 books
[2/5] Generating 3-shingles
      10 books with shingles
[3/5] Computing MinHash signatures (n=50)
      10 signatures generated
[4/5] Building LSH index (b=10, r=5)
      100 index rows (10 books × 10 bands)
[5/5] Saving to Parquet
      Saved 10 rows to ./data/output/signatures/ [signatures]
      Saved 100 rows to ./data/output/lsh_index/ [lsh_index]

Pipeline complete in Xs
  Books: 10 → Shingles: 10 → Signatures: 10
  LSH index: 100 rows
```

**What happens here**:
1. **Shingling** — Each book's tokens → sliding window of 3 consecutive words → deduplicated shingle set
2. **MinHash** — 50 hash functions compress each shingle set into a 50-element signature
3. **LSH Banding** — Each signature split into 10 bands of 5 rows, hashed to buckets
4. **Save** — Signatures and LSH index saved as Parquet files

## Step 3: Inspect Results

```bash
LSH_ENV=dev uv run python -c "
from src.preprocessing import create_spark_session
from src.lsh import find_candidate_pairs

spark = create_spark_session()

# Check signatures
sig_df = spark.read.parquet('./data/output/signatures/')
print('=== Signatures ===')
sig_df.show(10, truncate=60)
print(f'Signature length: {len(sig_df.first()[\"signature\"])}')

# Check LSH index
lsh_df = spark.read.parquet('./data/output/lsh_index/')
print(f'\n=== LSH Index ({lsh_df.count()} rows) ===')
lsh_df.show(10, truncate=False)

# Find candidate pairs
pairs_df = find_candidate_pairs(lsh_df)
print(f'\n=== Candidate Pairs ({pairs_df.count()}) ===')
pairs_df.show(20, truncate=False)
"
```

## Step 4: Estimate Similarity Between Candidates

```bash
LSH_ENV=dev uv run python -c "
from src.preprocessing import create_spark_session
from src.minhash import estimate_jaccard
from src.lsh import find_candidate_pairs

spark = create_spark_session()
sig_df = spark.read.parquet('./data/output/signatures/')
lsh_df = spark.read.parquet('./data/output/lsh_index/')

# Get all signatures as dict
sigs = {row['book_id']: row['signature'] for row in sig_df.collect()}

# Get candidate pairs
pairs = find_candidate_pairs(lsh_df).collect()

print(f'Found {len(pairs)} candidate pairs\n')
print(f'{\"Book 1\":<12} {\"Book 2\":<12} {\"Est. Jaccard\":>12}')
print('-' * 38)
for row in sorted(pairs, key=lambda r: -estimate_jaccard(sigs[r['book_id_1']], sigs[r['book_id_2']])):
    j = estimate_jaccard(sigs[row['book_id_1']], sigs[row['book_id_2']])
    print(f'{row[\"book_id_1\"]:<12} {row[\"book_id_2\"]:<12} {j:>12.3f}')
"
```

## All-in-One Script

Run the entire pipeline in a single command:

```bash
LSH_ENV=dev uv run python -c "
# --- Setup ---
from src.preprocessing import create_spark_session, preprocess_books
from src.shingling import generate_shingles
from src.minhash import compute_minhash_signatures, estimate_jaccard
from src.lsh import build_lsh_index, find_candidate_pairs

spark = create_spark_session()

# --- Step 1: Load & preprocess 10 books ---
rdd = spark.sparkContext.wholeTextFiles('./data/demo10/*.txt')
raw_df = rdd.toDF(['path', 'content'])
tokens_df = preprocess_books(raw_df, spark)
print(f'[1] Preprocessed {tokens_df.count()} books')

# --- Step 2: Shingling ---
shingles_df = generate_shingles(tokens_df)
print(f'[2] Generated shingles for {shingles_df.count()} books')

# --- Step 3: MinHash ---
sig_df = compute_minhash_signatures(shingles_df, spark)
sig_df.cache()
print(f'[3] Computed {sig_df.count()} signatures')

# --- Step 4: LSH ---
lsh_df = build_lsh_index(sig_df)
print(f'[4] Built LSH index: {lsh_df.count()} rows')

# --- Step 5: Find similar books ---
pairs_df = find_candidate_pairs(lsh_df)
pairs = pairs_df.collect()
sigs = {r['book_id']: r['signature'] for r in sig_df.collect()}

print(f'\n=== {len(pairs)} Candidate Pairs ===')
print(f'{\"Book 1\":<12} {\"Book 2\":<12} {\"Est. Jaccard\":>12}')
print('-' * 38)
for row in sorted(pairs, key=lambda r: -estimate_jaccard(sigs[r['book_id_1']], sigs[r['book_id_2']])):
    j = estimate_jaccard(sigs[row['book_id_1']], sigs[row['book_id_2']])
    print(f'{row[\"book_id_1\"]:<12} {row[\"book_id_2\"]:<12} {j:>12.3f}')
print('\nDone!')
"
```

## Using the Full 94-Book Sample

To run on all sample books instead of 10:

```bash
# Step 1: Preprocess (uses data/sample/ by default)
LSH_ENV=dev uv run python -c "from src.preprocessing import run_preprocessing; run_preprocessing()"

# Step 2: Run LSH pipeline
LSH_ENV=dev uv run python -m src.main
```

Or simply:
```bash
make run
```

## Output Files

After running the pipeline:

```
data/output/
├── cleaned/       # Parquet: DataFrame(book_id, tokens)
├── signatures/    # Parquet: DataFrame(book_id, signature)
└── lsh_index/     # Parquet: DataFrame(book_id, band_id, bucket_hash)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `Java not found` | Install Java 11+: `brew install openjdk@11` |
| `No Parquet at cleaned/` | Run preprocessing first (Step 1) |
| `0 candidate pairs` | Normal for very different books — try more books |
| `OutOfMemoryError` | Increase memory: edit `SPARK_DRIVER_MEMORY` in `config/settings.py` |
