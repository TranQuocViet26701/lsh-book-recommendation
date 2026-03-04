"""Full LSH pipeline: preprocessing → shingling → MinHash → LSH → save.

Usage:
    LSH_ENV=dev uv run python -m src.main
"""

import time

from config.settings import config
from src.lsh import build_lsh_index
from src.minhash import compute_minhash_signatures
from src.preprocessing import create_spark_session
from src.shingling import generate_shingles


def run_pipeline():
    """Execute the full LSH pipeline end-to-end.

    Steps:
        1. Load preprocessed tokens from Parquet
        2. Generate k-shingles
        3. Compute MinHash signatures
        4. Build LSH banding index
        5. Save signatures and LSH index to Parquet

    Returns:
        Tuple of (signatures_df, lsh_index_df).
    """
    spark = create_spark_session()
    t0 = time.time()

    # Step 1: Load preprocessed tokens
    print(f"[1/5] Loading tokens from {config.DATA_CLEANED_PATH}")
    tokens_df = spark.read.parquet(config.DATA_CLEANED_PATH)
    book_count = tokens_df.count()
    print(f"      Loaded {book_count} books")

    # Step 2: Shingling
    print(f"[2/5] Generating {config.SHINGLE_K}-shingles")
    shingles_df = generate_shingles(tokens_df)
    shingle_count = shingles_df.count()
    print(f"      {shingle_count} books with shingles")

    # Step 3: MinHash signatures
    print(f"[3/5] Computing MinHash signatures (n={config.MINHASH_NUM_HASHES})")
    signatures_df = compute_minhash_signatures(shingles_df, spark)
    signatures_df.cache()
    sig_count = signatures_df.count()
    print(f"      {sig_count} signatures generated")

    # Step 4: LSH banding
    print(f"[4/5] Building LSH index (b={config.LSH_NUM_BANDS}, r={config.LSH_ROWS_PER_BAND})")
    lsh_index_df = build_lsh_index(signatures_df)
    lsh_index_df.cache()
    lsh_count = lsh_index_df.count()
    print(f"      {lsh_count} index rows ({sig_count} books × {config.LSH_NUM_BANDS} bands)")

    # Step 5: Save to Parquet
    print("[5/5] Saving to Parquet")
    _save_parquet(signatures_df, config.DATA_SIGNATURES_PATH, "signatures")
    _save_parquet(lsh_index_df, config.DATA_LSH_INDEX_PATH, "lsh_index")

    elapsed = time.time() - t0
    print(f"\nPipeline complete in {elapsed:.1f}s")
    print(f"  Books: {book_count} → Shingles: {shingle_count} → Signatures: {sig_count}")
    print(f"  LSH index: {lsh_count} rows")

    return signatures_df, lsh_index_df


def _save_parquet(df, path: str, label: str):
    """Save DataFrame to Parquet with read-back verification."""
    df.coalesce(1).write.mode("overwrite").parquet(path)
    # Read back and verify
    from src.preprocessing import create_spark_session
    spark = create_spark_session()
    saved = spark.read.parquet(path)
    count = saved.count()
    print(f"      Saved {count} rows to {path} [{label}]")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "query":
        from src.query import run_query

        bid = sys.argv[2] if len(sys.argv) > 2 else None
        if not bid:
            print("Usage: python -m src.main query <book_id> [top_k]")
            sys.exit(1)
        k = int(sys.argv[3]) if len(sys.argv) > 3 else None
        results = run_query(bid, k)
        results.show(truncate=False)
        print(f"Found {results.count()} similar books for '{bid}'")
    else:
        run_pipeline()
