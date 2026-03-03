"""PySpark preprocessing pipeline for Gutenberg book texts.

Reads raw .txt files, strips Gutenberg headers, cleans text (lowercase, regex),
tokenizes, removes stopwords, and outputs DataFrame(book_id, tokens).
"""

import os

import nltk
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType

from config.settings import config
from scripts.text_cleaning_utils import strip_gutenberg_headers


def _ensure_nltk_stopwords() -> set:
    """Download NLTK English stopwords if missing, return as set."""
    try:
        from nltk.corpus import stopwords
        return set(stopwords.words("english"))
    except LookupError:
        nltk.download("stopwords", quiet=True)
        from nltk.corpus import stopwords
        return set(stopwords.words("english"))


def _make_remove_stopwords_udf(broadcast_stops):
    """Factory for stopword removal UDF with proper broadcast serialization."""
    @F.udf(ArrayType(StringType()))
    def remove_stopwords(tokens):
        if tokens is None:
            return []
        stops = broadcast_stops.value
        return [t for t in tokens if t and len(t) > 1 and t not in stops]
    return remove_stopwords


def create_spark_session() -> SparkSession:
    """Create or get SparkSession using project config."""
    # Set driver memory before JVM starts (only if not already set)
    os.environ.setdefault("PYSPARK_SUBMIT_ARGS", "--driver-memory 4g pyspark-shell")
    return (
        SparkSession.builder
        .master(config.SPARK_MASTER)
        .appName(config.SPARK_APP_NAME)
        .config("spark.executor.memory", config.SPARK_EXECUTOR_MEMORY)
        .config("spark.driver.memory", config.SPARK_DRIVER_MEMORY)
        .getOrCreate()
    )


def load_raw_books(spark: SparkSession) -> DataFrame:
    """Read all .txt files from DATA_RAW_PATH via wholeTextFiles.

    Returns DataFrame with columns (path: string, content: string).
    """
    base = config.DATA_RAW_PATH.rstrip("/") + "/"
    rdd = spark.sparkContext.wholeTextFiles(base + "*.txt")
    return rdd.toDF(["path", "content"])


def preprocess_books(df: DataFrame, spark: SparkSession) -> DataFrame:
    """Full preprocessing pipeline.

    Steps: extract book_id -> strip headers -> lowercase -> regex clean
    -> tokenize -> remove stopwords & single-char tokens.

    Returns DataFrame(book_id: string, tokens: array<string>).
    """
    # Extract book_id from path (e.g. "file:///path/pg10007.txt" -> "pg10007")
    df = df.withColumn(
        "book_id",
        F.regexp_extract(F.col("path"), r"(pg\d+)\.txt", 1),
    )

    # Strip Gutenberg headers via UDF
    strip_headers_udf = F.udf(strip_gutenberg_headers, StringType())
    df = df.withColumn("cleaned_text", strip_headers_udf(F.col("content")))

    # Lowercase
    df = df.withColumn("lowered", F.lower(F.col("cleaned_text")))

    # Remove non-alpha characters (keep letters and spaces)
    df = df.withColumn("alpha_only", F.regexp_replace(F.col("lowered"), "[^a-z\\s]", ""))

    # Tokenize on whitespace
    df = df.withColumn("raw_tokens", F.split(F.col("alpha_only"), "\\s+"))

    # Broadcast stopwords and filter via UDF
    stop_set = _ensure_nltk_stopwords()
    broadcast_stops = spark.sparkContext.broadcast(stop_set)
    remove_stopwords = _make_remove_stopwords_udf(broadcast_stops)
    df = df.withColumn("tokens", remove_stopwords(F.col("raw_tokens")))

    # Select final columns, filter out empty token arrays
    return df.select("book_id", "tokens").filter(F.size(F.col("tokens")) > 0)


def run_preprocessing() -> DataFrame:
    """Entry point: create session, load, preprocess, save Parquet, return result."""
    spark = create_spark_session()
    raw_df = load_raw_books(spark)
    result_df = preprocess_books(raw_df, spark)

    # Save to Parquet (coalesce for dev efficiency)
    result_df.coalesce(1).write.mode("overwrite").parquet(config.DATA_CLEANED_PATH)

    # Read back from Parquet to avoid recomputation
    saved_df = spark.read.parquet(config.DATA_CLEANED_PATH)
    print(f"Saved {saved_df.count()} books to {config.DATA_CLEANED_PATH}")

    return saved_df


if __name__ == "__main__":
    df = run_preprocessing()
    df.show(5, truncate=80)
    print(f"Schema: {df.schema.simpleString()}")
