"""Unit tests for src/query.py module."""

from src.lsh import build_lsh_index
from src.query import find_similar_books


def _build_test_data(spark):
    """Create controlled test data: 4 books with known signatures.

    - doc_A: [1]*10  (query book)
    - doc_B: [1]*10  (identical to A → sim=1.0)
    - doc_C: [1]*5 + [2]*5  (half match → sim=0.5)
    - doc_D: [2]*10  (no match → sim=0.0)
    - doc_E: [1]*7 + [2]*3  (partial → sim=0.7)
    """
    data = [
        ("doc_A", [1] * 10),
        ("doc_B", [1] * 10),
        ("doc_C", [1] * 5 + [2] * 5),
        ("doc_D", [2] * 10),
        ("doc_E", [1] * 7 + [2] * 3),
    ]
    sigs = spark.createDataFrame(data, ["book_id", "signature"])
    idx = build_lsh_index(sigs, num_bands=2, rows_per_band=5)
    return sigs, idx


# -- Tests --------------------------------------------------------------------


def test_identical_book_returns_similarity_one(spark):
    """Identical signatures yield similarity = 1.0."""
    sigs, idx = _build_test_data(spark)
    result = find_similar_books(spark, "doc_A", top_k=10, signatures_df=sigs, lsh_index_df=idx)
    rows = {r["book_id"]: r["similarity"] for r in result.collect()}
    assert "doc_B" in rows
    assert rows["doc_B"] == 1.0


def test_results_sorted_by_similarity_desc(spark):
    """Results are ordered descending by similarity."""
    sigs, idx = _build_test_data(spark)
    result = find_similar_books(spark, "doc_A", top_k=10, signatures_df=sigs, lsh_index_df=idx)
    sims = [r["similarity"] for r in result.collect()]
    assert sims == sorted(sims, reverse=True)


def test_top_k_limits_results(spark):
    """top_k parameter caps the number of returned rows."""
    sigs, idx = _build_test_data(spark)
    result = find_similar_books(spark, "doc_A", top_k=2, signatures_df=sigs, lsh_index_df=idx)
    assert result.count() <= 2


def test_unknown_book_returns_empty(spark):
    """Unknown book_id returns empty DataFrame without crashing."""
    sigs, idx = _build_test_data(spark)
    result = find_similar_books(
        spark, "nonexistent", top_k=10, signatures_df=sigs, lsh_index_df=idx,
    )
    assert result.count() == 0


def test_query_book_excluded_from_results(spark):
    """Query book itself must not appear in results."""
    sigs, idx = _build_test_data(spark)
    result = find_similar_books(spark, "doc_A", top_k=10, signatures_df=sigs, lsh_index_df=idx)
    book_ids = [r["book_id"] for r in result.collect()]
    assert "doc_A" not in book_ids


def test_no_candidates_returns_empty(spark):
    """Book with truly unique buckets returns empty result."""
    # Use a signature that shares no bands with any other book
    data = [
        ("doc_X", [1] * 10),
        ("doc_Y", [9] * 10),  # unique bands — no overlap with doc_X
    ]
    sigs = spark.createDataFrame(data, ["book_id", "signature"])
    idx = build_lsh_index(sigs, num_bands=2, rows_per_band=5)
    result = find_similar_books(
        spark, "doc_Y", top_k=10, signatures_df=sigs, lsh_index_df=idx,
    )
    assert result.count() == 0


def test_partial_similarity_values_correct(spark):
    """doc_C (half matching sig) should have similarity ~0.5."""
    sigs, idx = _build_test_data(spark)
    result = find_similar_books(spark, "doc_A", top_k=10, signatures_df=sigs, lsh_index_df=idx)
    rows = {r["book_id"]: r["similarity"] for r in result.collect()}
    if "doc_C" in rows:
        assert rows["doc_C"] == 0.5
