"""LSH banding and bucketing module.

Input:  DataFrame(book_id: string, signature: array<int>)
Output: DataFrame(book_id: string, band_id: int, bucket_hash: int)

Splits MinHash signatures into b bands of r rows each,
hashes each band to a bucket using hashlib.md5 for determinism.
Two books are candidate pairs if they share ANY bucket in ANY band.
"""

import hashlib
import struct

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, IntegerType, StructField, StructType

from config.settings import config

# Schema for band hash UDF output
_BAND_STRUCT = StructType([
    StructField("band_id", IntegerType(), False),
    StructField("bucket_hash", IntegerType(), False),
])


def _hash_band(values: list) -> int:
    """Deterministic band hash using md5.

    Serializes integer values to bytes, hashes via md5,
    returns a positive 32-bit integer.
    """
    data = struct.pack(f">{len(values)}i", *values)
    digest = hashlib.md5(data).hexdigest()
    return int(digest, 16) % ((1 << 31) - 1)


def _make_band_hash_udf(num_bands: int, rows_per_band: int):
    """Factory for LSH banding UDF.

    Returns UDF that splits signature into bands and hashes each band.
    """
    @F.udf(ArrayType(_BAND_STRUCT))
    def band_hash(signature):
        if not signature:
            return []
        result = []
        for i in range(num_bands):
            start = i * rows_per_band
            end = start + rows_per_band
            band_values = signature[start:end]
            # Deterministic hash via md5
            data = struct.pack(f">{len(band_values)}i", *band_values)
            digest = hashlib.md5(data).hexdigest()
            bucket = int(digest, 16) % ((1 << 31) - 1)
            result.append((i, bucket))
        return result
    return band_hash


def build_lsh_index(
    df: DataFrame,
    num_bands: int = None,
    rows_per_band: int = None,
) -> DataFrame:
    """Build LSH index by splitting signatures into bands and hashing.

    Args:
        df: DataFrame with columns (book_id, signature).
        num_bands: Number of bands (default: config.LSH_NUM_BANDS).
        rows_per_band: Rows per band (default: config.LSH_ROWS_PER_BAND).

    Returns:
        DataFrame(book_id, band_id, bucket_hash) — one row per book per band.
    """
    if num_bands is None:
        num_bands = config.LSH_NUM_BANDS
    if rows_per_band is None:
        rows_per_band = config.LSH_ROWS_PER_BAND

    band_udf = _make_band_hash_udf(num_bands, rows_per_band)
    result = df.withColumn("bands", band_udf(F.col("signature")))
    result = result.select("book_id", F.explode("bands").alias("band"))
    result = result.select(
        "book_id",
        F.col("band.band_id").alias("band_id"),
        F.col("band.bucket_hash").alias("bucket_hash"),
    )
    return result


def find_candidate_pairs(lsh_index_df: DataFrame) -> DataFrame:
    """Find candidate pairs by self-joining on (band_id, bucket_hash).

    Returns DataFrame(book_id_1, book_id_2) with distinct pairs
    where book_id_1 < book_id_2 (no self-pairs or duplicates).
    """
    a = lsh_index_df.alias("a")
    b = lsh_index_df.alias("b")

    pairs = a.join(
        b,
        (F.col("a.band_id") == F.col("b.band_id"))
        & (F.col("a.bucket_hash") == F.col("b.bucket_hash"))
        & (F.col("a.book_id") < F.col("b.book_id")),
    )
    return pairs.select(
        F.col("a.book_id").alias("book_id_1"),
        F.col("b.book_id").alias("book_id_2"),
    ).distinct()


def run_lsh(input_path: str = None) -> DataFrame:
    """Entry point: load signatures, build LSH index."""
    from src.preprocessing import create_spark_session
    from src.minhash import run_minhash

    spark = create_spark_session()
    if input_path:
        sig_df = spark.read.parquet(input_path)
    else:
        sig_df = run_minhash()
    return build_lsh_index(sig_df)


if __name__ == "__main__":
    df = run_lsh()
    df.show(20, truncate=False)
    print(f"Schema: {df.schema.simpleString()}")
    print(f"Total rows: {df.count()}")
