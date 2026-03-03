"""Word-level k-shingling module.

Input:  DataFrame(book_id: string, tokens: array<string>)
Output: DataFrame(book_id: string, shingles: array<string>)

Shingles are sliding windows of k consecutive tokens joined by space.
Example: tokens [a, b, c, d] with k=3 → shingles ["a b c", "b c d"]
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import ArrayType, StringType

from config.settings import config


def _create_shingles_udf(k: int):
    """Factory for k-shingling UDF.

    Returns UDF that converts token array to deduplicated shingle array.
    """
    @F.udf(ArrayType(StringType()))
    def shingle(tokens):
        if not tokens or len(tokens) < k:
            return []
        shingles = [" ".join(tokens[i:i + k]) for i in range(len(tokens) - k + 1)]
        return list(set(shingles))
    return shingle


def generate_shingles(df: DataFrame, k: int = None) -> DataFrame:
    """Generate word-level k-shingles from token arrays.

    Args:
        df: DataFrame with columns (book_id, tokens).
        k: Shingle size (default: config.SHINGLE_K).

    Returns:
        DataFrame(book_id, shingles: array<string>) with empty arrays filtered out.
    """
    if k is None:
        k = config.SHINGLE_K

    shingle_udf = _create_shingles_udf(k)
    result = df.withColumn("shingles", shingle_udf(F.col("tokens")))
    result = result.select("book_id", "shingles").filter(F.size("shingles") > 0)
    return result


def run_shingling(input_path: str = None) -> DataFrame:
    """Entry point: load preprocessed tokens, generate shingles.

    Args:
        input_path: Path to preprocessed Parquet (default: config.DATA_CLEANED_PATH).

    Returns:
        DataFrame(book_id, shingles).
    """
    from src.preprocessing import create_spark_session

    spark = create_spark_session()
    path = input_path or config.DATA_CLEANED_PATH
    tokens_df = spark.read.parquet(path)
    return generate_shingles(tokens_df)


if __name__ == "__main__":
    df = run_shingling()
    df.show(5, truncate=80)
    print(f"Schema: {df.schema.simpleString()}")
    print(f"Books: {df.count()}")
