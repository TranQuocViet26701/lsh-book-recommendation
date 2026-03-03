"""Unit tests for src/preprocessing.py pipeline."""

from pyspark.sql.types import ArrayType, StringType

from scripts.text_cleaning_utils import strip_gutenberg_headers
from src.preprocessing import _ensure_nltk_stopwords, preprocess_books

# -- Test data ----------------------------------------------------------------

GUTENBERG_TEXT = """
*** START OF THE PROJECT GUTENBERG EBOOK TEST ***
This is the actual book content. It has Numbers123 and special-chars!
The quick brown fox jumps over the lazy dog.
Some more text with unicode \u201cleft quote\u201d and em-dash\u2014here.
*** END OF THE PROJECT GUTENBERG EBOOK TEST ***
"""

PLAIN_TEXT = "Hello World! 123 Test-Case the is a"


# -- Tests: text_cleaning_utils -----------------------------------------------

def test_strip_gutenberg_headers_removes_start_marker():
    """Start marker line is stripped from output text."""
    result = strip_gutenberg_headers(GUTENBERG_TEXT)
    assert "*** START OF" not in result
    assert "actual book content" in result


def test_strip_gutenberg_headers_preserves_body():
    result = strip_gutenberg_headers(GUTENBERG_TEXT)
    assert "quick brown fox" in result


# -- Tests: preprocessing pipeline --------------------------------------------

def test_book_id_extraction(spark):
    """book_id extracted correctly from file path."""
    data = [("file:///data/sample/pg12345.txt", "some text")]
    df = spark.createDataFrame(data, ["path", "content"])
    result = preprocess_books(df, spark)
    row = result.collect()[0]
    assert row["book_id"] == "pg12345"


def test_lowercase_and_regex_clean(spark):
    """Output tokens are lowercase alpha only, no numbers or special chars."""
    data = [("file:///test/pg99999.txt", "Hello World! 123 Test-Case stuff")]
    df = spark.createDataFrame(data, ["path", "content"])
    result = preprocess_books(df, spark)
    tokens = result.collect()[0]["tokens"]
    for t in tokens:
        assert t == t.lower(), f"Token not lowercase: {t}"
        assert t.isalpha(), f"Token not alpha: {t}"


def test_tokenization_splits_whitespace(spark):
    """Text is split into individual word tokens."""
    data = [("file:///test/pg99999.txt", "castle styria people mountains")]
    df = spark.createDataFrame(data, ["path", "content"])
    result = preprocess_books(df, spark)
    tokens = result.collect()[0]["tokens"]
    assert "castle" in tokens
    assert "styria" in tokens
    assert "people" in tokens
    assert "mountains" in tokens


def test_stopword_removal(spark):
    """Common English stopwords are removed from tokens."""
    stops = _ensure_nltk_stopwords()
    data = [("file:///test/pg99999.txt", "the quick brown fox is a very lazy dog")]
    df = spark.createDataFrame(data, ["path", "content"])
    result = preprocess_books(df, spark)
    tokens = result.collect()[0]["tokens"]
    for t in tokens:
        assert t not in stops, f"Stopword not removed: {t}"


def test_single_char_tokens_filtered(spark):
    """Single-character tokens are filtered out."""
    data = [("file:///test/pg99999.txt", "a i hello b world")]
    df = spark.createDataFrame(data, ["path", "content"])
    result = preprocess_books(df, spark)
    tokens = result.collect()[0]["tokens"]
    for t in tokens:
        assert len(t) > 1, f"Single-char token not filtered: {t}"


def test_preprocess_books_schema(spark):
    """Output schema has book_id (string) and tokens (array<string>)."""
    data = [("file:///test/pg99999.txt", "hello world example text")]
    df = spark.createDataFrame(data, ["path", "content"])
    result = preprocess_books(df, spark)
    assert result.schema["book_id"].dataType == StringType()
    assert result.schema["tokens"].dataType == ArrayType(StringType())


def test_preprocess_books_no_stopwords_in_output(spark):
    """End-to-end: no NLTK stopwords in final output."""
    stops = _ensure_nltk_stopwords()
    data = [
        ("file:///test/pg00001.txt", GUTENBERG_TEXT),
        ("file:///test/pg00002.txt", "the and but or which shall not every"),
    ]
    df = spark.createDataFrame(data, ["path", "content"])
    result = preprocess_books(df, spark)
    for row in result.collect():
        for t in row["tokens"]:
            assert t not in stops, f"Stopword '{t}' in book {row['book_id']}"


def test_empty_text_produces_no_rows(spark):
    """Empty or stopword-only text results in filtered-out rows."""
    data = [("file:///test/pg99999.txt", "the is a an")]
    df = spark.createDataFrame(data, ["path", "content"])
    result = preprocess_books(df, spark)
    assert result.count() == 0
