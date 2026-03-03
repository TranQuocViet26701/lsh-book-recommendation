"""Unit tests for src/lsh.py module."""

from src.lsh import build_lsh_index, find_candidate_pairs


# -- Tests --------------------------------------------------------------------


def test_band_count(spark):
    """Each book produces exactly num_bands rows in LSH index."""
    # Signature of length 10 → 2 bands × 5 rows
    data = [("doc1", list(range(10)))]
    df = spark.createDataFrame(data, ["book_id", "signature"])
    result = build_lsh_index(df, num_bands=2, rows_per_band=5)
    assert result.count() == 2


def test_identical_signatures_share_all_buckets(spark):
    """Books with identical signatures share ALL bucket hashes."""
    sig = list(range(10))
    data = [("doc_A", sig), ("doc_B", sig)]
    df = spark.createDataFrame(data, ["book_id", "signature"])
    result = build_lsh_index(df, num_bands=2, rows_per_band=5)

    # Group by (band_id, bucket_hash) and count distinct book_ids
    rows = result.collect()
    buckets_a = {(r["band_id"], r["bucket_hash"]) for r in rows if r["book_id"] == "doc_A"}
    buckets_b = {(r["band_id"], r["bucket_hash"]) for r in rows if r["book_id"] == "doc_B"}
    assert buckets_a == buckets_b


def test_different_signatures_differ(spark):
    """Books with completely different signatures share few or no buckets."""
    data = [
        ("doc_A", list(range(10))),
        ("doc_B", list(range(100, 110))),
    ]
    df = spark.createDataFrame(data, ["book_id", "signature"])
    result = build_lsh_index(df, num_bands=2, rows_per_band=5)

    rows = result.collect()
    buckets_a = {(r["band_id"], r["bucket_hash"]) for r in rows if r["book_id"] == "doc_A"}
    buckets_b = {(r["band_id"], r["bucket_hash"]) for r in rows if r["book_id"] == "doc_B"}
    shared = buckets_a & buckets_b
    assert len(shared) == 0, f"Expected no shared buckets, got {len(shared)}"


def test_candidate_pairs_similar_books(spark):
    """Identical signature books appear as candidate pairs."""
    sig = list(range(10))
    data = [("doc_A", sig), ("doc_B", sig), ("doc_C", list(range(100, 110)))]
    df = spark.createDataFrame(data, ["book_id", "signature"])
    index = build_lsh_index(df, num_bands=2, rows_per_band=5)
    pairs = find_candidate_pairs(index).collect()

    pair_set = {(r["book_id_1"], r["book_id_2"]) for r in pairs}
    assert ("doc_A", "doc_B") in pair_set


def test_no_self_pairs(spark):
    """No book is paired with itself."""
    sig = list(range(10))
    data = [("doc_A", sig), ("doc_B", sig)]
    df = spark.createDataFrame(data, ["book_id", "signature"])
    index = build_lsh_index(df, num_bands=2, rows_per_band=5)
    pairs = find_candidate_pairs(index).collect()

    for r in pairs:
        assert r["book_id_1"] != r["book_id_2"]


def test_no_duplicate_pairs(spark):
    """Each candidate pair appears exactly once."""
    sig = list(range(10))
    data = [("doc_A", sig), ("doc_B", sig), ("doc_C", sig)]
    df = spark.createDataFrame(data, ["book_id", "signature"])
    index = build_lsh_index(df, num_bands=2, rows_per_band=5)
    pairs = find_candidate_pairs(index).collect()

    pair_list = [(r["book_id_1"], r["book_id_2"]) for r in pairs]
    assert len(pair_list) == len(set(pair_list))
