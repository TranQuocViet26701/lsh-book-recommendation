"""Pure-Python helpers for query-by-text: shingling, minhash, band hashing.

These mirror the Spark UDF logic in src.shingling, src.minhash, and src.lsh
but run without Spark, producing compatible outputs for LSH index lookup.
"""

import hashlib
import random
import struct

from config.settings import config

LARGE_PRIME = (1 << 31) - 1
MAX_HASH = (1 << 31) - 1


def shingle_text(text: str, k: int = None) -> list:
    """Create word k-shingles from raw text."""
    if k is None:
        k = config.SHINGLE_K
    words = text.lower().split()
    if len(words) < k:
        return []
    return list(set(" ".join(words[i:i + k]) for i in range(len(words) - k + 1)))


def minhash_shingles(shingles: list, num_hashes: int = None) -> list:
    """Compute MinHash signature from shingle list.

    Uses same seed=42 and hash logic as src.minhash for compatible signatures.
    """
    if num_hashes is None:
        num_hashes = config.MINHASH_NUM_HASHES

    # Same seed=42 as src.minhash._generate_hash_params
    rng = random.Random(42)
    hash_params = [
        (rng.randint(1, LARGE_PRIME - 1), rng.randint(0, LARGE_PRIME - 1))
        for _ in range(num_hashes)
    ]

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


def compute_band_hashes(signature: list, num_bands: int = None, rows_per_band: int = None) -> list:
    """Compute (band_id, bucket_hash) pairs from signature.

    Uses same md5 band hashing as src.lsh._make_band_hash_udf.
    """
    if num_bands is None:
        num_bands = config.LSH_NUM_BANDS
    if rows_per_band is None:
        rows_per_band = config.LSH_ROWS_PER_BAND

    result = []
    for i in range(num_bands):
        band_values = signature[i * rows_per_band:(i + 1) * rows_per_band]
        data = struct.pack(f">{len(band_values)}i", *band_values)
        bucket = int(hashlib.md5(data).hexdigest(), 16) % LARGE_PRIME
        result.append((i, bucket))
    return result
