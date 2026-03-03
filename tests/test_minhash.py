"""Unit tests for src/minhash.py module."""

from pyspark.sql.types import ArrayType, IntegerType, StringType

from src.minhash import compute_minhash_signatures, estimate_jaccard


# -- Tests --------------------------------------------------------------------


def test_signature_length(spark):
    """Signature length equals num_hashes parameter."""
    data = [("doc1", ["ab", "bc", "cd"])]
    df = spark.createDataFrame(data, ["book_id", "shingles"])
    result = compute_minhash_signatures(df, spark, num_hashes=20).collect()
    assert len(result[0]["signature"]) == 20


def test_determinism(spark):
    """Same input + same seed → same signature across calls."""
    data = [("doc1", ["ab", "bc", "cd", "de"])]
    df = spark.createDataFrame(data, ["book_id", "shingles"])
    sig1 = compute_minhash_signatures(df, spark, num_hashes=50).collect()[0]["signature"]
    sig2 = compute_minhash_signatures(df, spark, num_hashes=50).collect()[0]["signature"]
    assert sig1 == sig2


def test_jaccard_approximation(spark):
    """MinHash estimate approximates true Jaccard within ±0.15 tolerance.

    doc_A shingles = {ab, bc, cd, de} (4)
    doc_B shingles = {ab, bc, cd, ef} (4)
    J(A,B) = |{ab,bc,cd}| / |{ab,bc,cd,de,ef}| = 3/5 = 0.6
    """
    data = [
        ("doc_A", ["ab", "bc", "cd", "de"]),
        ("doc_B", ["ab", "bc", "cd", "ef"]),
    ]
    df = spark.createDataFrame(data, ["book_id", "shingles"])
    result = compute_minhash_signatures(df, spark, num_hashes=100).collect()
    sigs = {row["book_id"]: row["signature"] for row in result}
    est = estimate_jaccard(sigs["doc_A"], sigs["doc_B"])
    assert abs(est - 0.6) <= 0.15, f"Expected ~0.6, got {est}"


def test_identical_sets_jaccard(spark):
    """Identical shingle sets → estimate_jaccard ≈ 1.0."""
    data = [
        ("doc_A", ["ab", "bc", "cd"]),
        ("doc_B", ["ab", "bc", "cd"]),
    ]
    df = spark.createDataFrame(data, ["book_id", "shingles"])
    result = compute_minhash_signatures(df, spark, num_hashes=100).collect()
    sigs = {row["book_id"]: row["signature"] for row in result}
    est = estimate_jaccard(sigs["doc_A"], sigs["doc_B"])
    assert est == 1.0


def test_disjoint_sets_jaccard(spark):
    """Completely disjoint shingle sets → estimate_jaccard ≈ 0.0."""
    data = [
        ("doc_A", ["ab", "bc", "cd", "de", "ef"]),
        ("doc_B", ["gh", "hi", "ij", "jk", "kl"]),
    ]
    df = spark.createDataFrame(data, ["book_id", "shingles"])
    result = compute_minhash_signatures(df, spark, num_hashes=100).collect()
    sigs = {row["book_id"]: row["signature"] for row in result}
    est = estimate_jaccard(sigs["doc_A"], sigs["doc_B"])
    assert est <= 0.15, f"Expected ~0.0, got {est}"


def test_schema_correct(spark):
    """Output schema has book_id (string) and signature (array<int>)."""
    data = [("doc1", ["ab", "bc", "cd"])]
    df = spark.createDataFrame(data, ["book_id", "shingles"])
    result = compute_minhash_signatures(df, spark, num_hashes=10)
    assert result.schema["book_id"].dataType == StringType()
    assert result.schema["signature"].dataType == ArrayType(IntegerType())
