"""Query engine — find similar books via LSH lookup and Jaccard ranking.

Input:  book_id (string)
Output: DataFrame(book_id: string, similarity: float[, Title, Author])

Flow: load signatures + LSH index → find same-bucket candidates →
      compute Jaccard similarity via MinHash → rank top-K → enrich metadata.
"""

import logging
import sys

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import FloatType, StringType, StructField, StructType

from config.settings import config
from src.minhash import estimate_jaccard
from src.query_by_text_helpers import (
    shingle_text, minhash_shingles, compute_band_hashes,
)

logger = logging.getLogger(__name__)

# Schema for empty result DataFrame
_EMPTY_SCHEMA = StructType([
    StructField("book_id", StringType(), False),
    StructField("similarity", FloatType(), False),
])


def _make_jaccard_udf(query_signature):
    """Factory for Jaccard similarity UDF. Captures query_signature via closure.

    Closure capture replaces sparkContext.broadcast — the signature (~400 bytes for
    100 hashes) is serialized once when the UDF is registered. This avoids the
    sparkContext attribute access that Databricks Serverless blocks.
    """

    @F.udf(FloatType())
    def jaccard_udf(candidate_sig):
        return float(estimate_jaccard(query_signature, candidate_sig))

    return jaccard_udf


def find_similar_books(
    spark: SparkSession,
    book_id: str,
    top_k: int = None,
    signatures_df: DataFrame = None,
    lsh_index_df: DataFrame = None,
) -> DataFrame:
    """Find top-K similar books for a given book_id using LSH.

    Args:
        spark: Active SparkSession.
        book_id: Target book identifier (e.g. "pg1234").
        top_k: Number of results (default: config.DEFAULT_TOP_K).
        signatures_df: Pre-loaded signatures (optional, loads from Parquet if None).
        lsh_index_df: Pre-loaded LSH index (optional, loads from Parquet if None).

    Returns:
        DataFrame(book_id, similarity[, Title, Author]) sorted desc by similarity.
    """
    if top_k is None:
        top_k = config.DEFAULT_TOP_K

    # Load from Parquet if not provided
    if signatures_df is None:
        signatures_df = spark.read.parquet(config.DATA_SIGNATURES_PATH)
    if lsh_index_df is None:
        lsh_index_df = spark.read.parquet(config.DATA_LSH_INDEX_PATH)

    # Get query book's signature
    query_row = signatures_df.filter(F.col("book_id") == book_id).first()
    if query_row is None:
        logger.warning("Book '%s' not found in signatures", book_id)
        return spark.createDataFrame([], _EMPTY_SCHEMA)

    query_signature = query_row["signature"]

    # Get query book's buckets
    query_buckets = (
        lsh_index_df
        .filter(F.col("book_id") == book_id)
        .select("band_id", "bucket_hash")
    )

    # Find candidate books sharing any bucket
    candidates = (
        lsh_index_df
        .join(query_buckets, ["band_id", "bucket_hash"])
        .filter(F.col("book_id") != book_id)
        .select("book_id")
        .distinct()
    )

    # Join candidates with their signatures
    candidate_sigs = candidates.join(signatures_df, "book_id")

    # Compute Jaccard similarity via closure-captured UDF (Serverless-compatible)
    jaccard_udf = _make_jaccard_udf(query_signature)

    result = (
        candidate_sigs
        .withColumn("similarity", jaccard_udf(F.col("signature")))
        .select("book_id", "similarity")
        .orderBy(F.desc("similarity"))
        .limit(top_k)
    )

    # Optional metadata enrichment
    result = _enrich_with_metadata(result, spark)
    return result


def _enrich_with_metadata(df: DataFrame, spark: SparkSession) -> DataFrame:
    """Join metadata (Title, Author) if CSV exists. Returns df unchanged on failure."""
    metadata_path = getattr(
        config, "DATA_METADATA_PATH", "data/sample/sample_metadata.csv"
    )
    try:
        if metadata_path.endswith(".csv"):
            meta_df = spark.read.csv(metadata_path, header=True, inferSchema=True)
        else:
            meta_df = spark.read.csv(
                metadata_path + "/*.csv", header=True, inferSchema=True,
            )

        # Prepend "pg" to GutenbergID to match book_id format
        meta_df = meta_df.withColumn(
            "book_id",
            F.concat(F.lit("pg"), F.col("GutenbergID").cast("string")),
        ).select("book_id", "Title", "Author")

        return df.join(meta_df, on="book_id", how="left").select(
            "book_id", "similarity", "Title", "Author"
        )
    except Exception:
        logger.debug("Metadata enrichment skipped — CSV not available")
        return df


def find_similar_by_text(
    spark: SparkSession,
    text: str,
    top_k: int = None,
    signatures_df: DataFrame = None,
    lsh_index_df: DataFrame = None,
) -> DataFrame:
    """Find top-K similar books for arbitrary input text using LSH.

    Processes text through shingle → minhash → band hash pipeline,
    then looks up candidates in the saved LSH index.

    Args:
        spark: Active SparkSession.
        text: Raw input text to query with.
        top_k: Number of results (default: config.DEFAULT_TOP_K).
        signatures_df: Pre-loaded signatures (optional).
        lsh_index_df: Pre-loaded LSH index (optional).

    Returns:
        DataFrame(book_id, similarity[, Title, Author]) sorted desc by similarity.
    """
    if top_k is None:
        top_k = config.DEFAULT_TOP_K

    # Process query text: shingle → minhash → band hashes
    shingles = shingle_text(text)
    if not shingles:
        logger.warning("Input text too short to produce shingles (need >= %d words)", config.SHINGLE_K)
        return spark.createDataFrame([], _EMPTY_SCHEMA)

    query_signature = minhash_shingles(shingles)
    query_bands = compute_band_hashes(query_signature)

    # Load from Parquet if not provided
    if signatures_df is None:
        signatures_df = spark.read.parquet(config.DATA_SIGNATURES_PATH)
    if lsh_index_df is None:
        lsh_index_df = spark.read.parquet(config.DATA_LSH_INDEX_PATH)

    # Build a small DataFrame of query band/bucket pairs for join
    query_bands_df = spark.createDataFrame(
        query_bands, schema=["band_id", "bucket_hash"]
    )

    # Find candidate books sharing any bucket with the query
    candidates = (
        lsh_index_df
        .join(query_bands_df, ["band_id", "bucket_hash"])
        .select("book_id")
        .distinct()
    )

    # Join candidates with their signatures
    candidate_sigs = candidates.join(signatures_df, "book_id")

    # Compute Jaccard similarity via closure-captured UDF (Serverless-compatible)
    jaccard_udf = _make_jaccard_udf(query_signature)

    result = (
        candidate_sigs
        .withColumn("similarity", jaccard_udf(F.col("signature")))
        .select("book_id", "similarity")
        .orderBy(F.desc("similarity"))
        .limit(top_k)
    )

    result = _enrich_with_metadata(result, spark)
    return result


def run_query(book_id: str, top_k: int = None) -> DataFrame:
    """Entry point: create Spark session and find similar books."""
    from src.preprocessing import create_spark_session

    spark = create_spark_session()
    return find_similar_books(spark, book_id, top_k)


def run_query_by_text(text: str, top_k: int = None) -> DataFrame:
    """Entry point: create Spark session and find similar books by text."""
    from src.preprocessing import create_spark_session

    spark = create_spark_session()
    return find_similar_by_text(spark, text, top_k)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m src.query <book_id> [top_k]")
        print("       python -m src.query --text 'some text content' [top_k]")
        sys.exit(1)

    if sys.argv[1] == "--text":
        if len(sys.argv) < 3:
            print("Error: --text requires a text argument")
            sys.exit(1)
        txt = sys.argv[2]
        k = int(sys.argv[3]) if len(sys.argv) > 3 else None
        results = run_query_by_text(txt, k)
        results.show(truncate=False)
        print(f"Found {results.count()} similar books for input text")
    else:
        bid = sys.argv[1]
        k = int(sys.argv[2]) if len(sys.argv) > 2 else None
        results = run_query(bid, k)
        results.show(truncate=False)
        print(f"Found {results.count()} similar books for '{bid}'")
