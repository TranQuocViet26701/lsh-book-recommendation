"""MinHash signature generation module.

Input:  DataFrame(book_id: string, shingles: array<string>)
Output: DataFrame(book_id: string, signature: array<int>)

Uses universal hashing: h_i(x) = ((a_i * hash(x) + b_i) % PRIME) % MAX_HASH
where hash(x) uses hashlib.md5 for cross-session determinism.
"""

import hashlib
import random

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, IntegerType

from config.settings import config

# Mersenne prime — large enough for 32-bit hash space
LARGE_PRIME = (1 << 31) - 1
MAX_HASH = (1 << 31) - 1


def _stable_hash(s: str) -> int:
    """Deterministic hash using md5, returns positive int < LARGE_PRIME."""
    return int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16) % LARGE_PRIME


def _generate_hash_params(num_hashes: int, seed: int = 42) -> list:
    """Generate (a, b) coefficient pairs for universal hash functions.

    Args:
        num_hashes: Number of hash functions to generate.
        seed: Random seed for reproducibility.

    Returns:
        List of (a, b) tuples.
    """
    rng = random.Random(seed)
    return [
        (rng.randint(1, LARGE_PRIME - 1), rng.randint(0, LARGE_PRIME - 1))
        for _ in range(num_hashes)
    ]


def _make_minhash_udf(hash_params):
    """Factory for MinHash UDF. Captures hash_params via closure (Serverless-compatible).

    Closure capture replaces sparkContext.broadcast — the params (~1KB for 100 hashes)
    are serialized once when the UDF is registered, mirroring broadcast semantics
    without the JVM sparkContext access blocked on Databricks Serverless.

    The UDF computes: for each hash function h_i, min over all shingles of
    ((a_i * md5(shingle) + b_i) % PRIME) % MAX_HASH.
    """
    @F.udf(ArrayType(IntegerType()))
    def minhash(shingles):
        if not shingles:
            return []
        signature = []
        for a, b in hash_params:
            min_val = MAX_HASH
            for s in shingles:
                h = int(hashlib.md5(s.encode("utf-8")).hexdigest(), 16) % LARGE_PRIME
                val = ((a * h + b) % LARGE_PRIME) % MAX_HASH
                if val < min_val:
                    min_val = val
            signature.append(min_val)
        return signature
    return minhash


def compute_minhash_signatures(
    df: DataFrame, spark: SparkSession, num_hashes: int = None
) -> DataFrame:
    """Compute MinHash signatures for each book's shingle set.

    Args:
        df: DataFrame with columns (book_id, shingles).
        spark: Active SparkSession (kept for API stability; no longer required).
        num_hashes: Signature length (default: config.MINHASH_NUM_HASHES).

    Returns:
        DataFrame(book_id, signature: array<int>).
    """
    if num_hashes is None:
        num_hashes = config.MINHASH_NUM_HASHES

    hash_params = _generate_hash_params(num_hashes)
    minhash_udf = _make_minhash_udf(hash_params)

    result = df.withColumn("signature", minhash_udf(F.col("shingles")))
    return result.select("book_id", "signature")


def estimate_jaccard(sig_a: list, sig_b: list) -> float:
    """Estimate Jaccard similarity from two MinHash signatures.

    Returns fraction of positions where signatures agree.
    """
    if not sig_a or not sig_b or len(sig_a) != len(sig_b):
        return 0.0
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / len(sig_a)


def run_minhash(input_path: str = None) -> DataFrame:
    """Entry point: load shingles, compute MinHash signatures."""
    from src.preprocessing import create_spark_session
    from src.shingling import run_shingling

    spark = create_spark_session()
    shingles_df = run_shingling(input_path)
    return compute_minhash_signatures(shingles_df, spark)


if __name__ == "__main__":
    df = run_minhash()
    df.show(5, truncate=80)
    print(f"Schema: {df.schema.simpleString()}")
    print(f"Books: {df.count()}")
