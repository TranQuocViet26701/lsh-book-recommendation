"""Unit tests for src/shingling.py module."""

from pyspark.sql.types import ArrayType, StringType, StructField, StructType

from src.shingling import generate_shingles

# Schema for test DataFrames with empty token lists
_TOKENS_SCHEMA = StructType([
    StructField("book_id", StringType(), True),
    StructField("tokens", ArrayType(StringType()), True),
])


# -- Tests --------------------------------------------------------------------


def test_basic_trigrams(spark):
    """k=3 produces correct word trigrams from token array."""
    data = [("doc1", ["a", "b", "c", "d"])]
    df = spark.createDataFrame(data, ["book_id", "tokens"])
    result = generate_shingles(df, k=3).collect()
    shingles = set(result[0]["shingles"])
    assert shingles == {"a b c", "b c d"}


def test_deduplication(spark):
    """Repeated tokens don't produce duplicate shingles."""
    data = [("doc1", ["a", "b", "c", "a", "b", "c"])]
    df = spark.createDataFrame(data, ["book_id", "tokens"])
    result = generate_shingles(df, k=3).collect()
    shingles = result[0]["shingles"]
    assert len(shingles) == len(set(shingles))


def test_short_tokens_filtered(spark):
    """Fewer than k tokens → book filtered out (empty shingles)."""
    data = [("doc1", ["a", "b"])]
    df = spark.createDataFrame(data, ["book_id", "tokens"])
    result = generate_shingles(df, k=3)
    assert result.count() == 0


def test_empty_tokens_filtered(spark):
    """Empty token list → book filtered out."""
    data = [("doc1", [])]
    df = spark.createDataFrame(data, _TOKENS_SCHEMA)
    result = generate_shingles(df, k=3)
    assert result.count() == 0


def test_bigrams_with_k2(spark):
    """k=2 produces correct word bigrams."""
    data = [("doc1", ["x", "y", "z"])]
    df = spark.createDataFrame(data, ["book_id", "tokens"])
    result = generate_shingles(df, k=2).collect()
    shingles = set(result[0]["shingles"])
    assert shingles == {"x y", "y z"}


def test_schema_correct(spark):
    """Output schema has book_id (string) and shingles (array<string>)."""
    data = [("doc1", ["a", "b", "c", "d"])]
    df = spark.createDataFrame(data, ["book_id", "tokens"])
    result = generate_shingles(df, k=3)
    assert result.schema["book_id"].dataType == StringType()
    assert result.schema["shingles"].dataType == ArrayType(StringType())
