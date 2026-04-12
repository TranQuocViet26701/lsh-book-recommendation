import os
import sys
import time
import argparse
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, udf
from pyspark.sql.types import DoubleType

# =====================================================================
# WINDOWS ENVIRONMENT FIX: PREVENT PYTHON WORKER CONNECTION TIMEOUTS
# Forces Spark to use the exact Python executable from the virtual env
# =====================================================================
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
os.environ["SPARK_LOCAL_IP"] = "127.0.0.1"
# =====================================================================

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def calculate_exact_jaccard(list_a, list_b):
    """
    Calculates the exact Jaccard similarity between two lists of elements.
    """
    if not list_a or not list_b:
        return 0.0
    set_a = set(list_a)
    set_b = set(list_b)
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return float(intersection) / union

# ==========================================
# CORE PIPELINE LOGIC
# ==========================================

def run_baseline_pipeline(spark, input_path, output_path, threshold, sample_limit):
    """
    Executes the exact pairwise matching pipeline (Brute-force approach O(N^2)).
    """
    print("\n" + "="*50)
    print(f"🚀 STARTING EXACT PAIRWISE BASELINE PIPELINE")
    print("="*50)
    
    # =====================================================================
    # FORCE ABSOLUTE LOCAL PATHS (Bypasses HDFS localhost:9000 issues)
    # =====================================================================
    current_dir = os.path.abspath(os.getcwd()).replace("\\", "/")
    safe_input_path = f"file:///{current_dir}/{input_path.strip('./')}"
    safe_output_path = f"file:///{current_dir}/{output_path.strip('./')}"
    # =====================================================================

    # 1. Load Data
    print(f"[*] Reading shingled data from:\n    {safe_input_path}")
    try:
        df = spark.read.parquet(safe_input_path)
    except Exception as e:
        print(f"[!] Error: Could not read input data. Details: {e}")
        return

    # 2. Apply Data Limit 
    if sample_limit and sample_limit > 0:
        print(f"[*] Applying data limit: Processing only {sample_limit} books.")
        df = df.limit(sample_limit)
        
    total_records = df.count()
    total_pairs = (total_records * (total_records - 1)) // 2
    
    print(f"[*] Total books to process: {total_records}")
    print(f"[*] Total pairs to evaluate: {total_pairs:,} pairs")

    start_time = time.time()

    # 3. Register UDF 
    jaccard_udf = udf(calculate_exact_jaccard, DoubleType())

    # 4. Perform Cross Join 
    df_a = df.alias("a")
    df_b = df.alias("b")
    pairs_df = df_a.crossJoin(df_b).filter(col("a.book_id") < col("b.book_id"))

    # 5. Compute Similarity and Filter
    print("[*] Executing Spark transformations and calculating exact Jaccard distances... Please wait.")
    results_df = pairs_df.withColumn(
        "jaccard_similarity", 
        jaccard_udf(col("a.shingles"), col("b.shingles"))
    ).filter(col("jaccard_similarity") >= threshold)

    # 6. Trigger Action and Cache
    final_df = results_df.cache() 
    match_count = final_df.count()
    
    execution_time = time.time() - start_time
    
    # 7. Print Execution Report
    print("\n" + "="*50)
    print("📊 BASELINE EXECUTION SUMMARY")
    print("="*50)
    print(f"- Execution Time       : {execution_time:.2f} seconds")
    if execution_time > 0:
        print(f"- Processing Rate      : {total_pairs / execution_time:,.0f} pairs/second")
    print(f"- Pairs Found (>= {threshold}): {match_count} pairs")
    print("="*50)

    # 8. Save Results
    if match_count > 0:
        print(f"\n[*] Saving baseline candidate pairs to file...")
        output_df = final_df.select(
            col("a.book_id").alias("book_id_A"),
            col("b.book_id").alias("book_id_B"),
            col("jaccard_similarity")
        )
        output_df.write.mode("overwrite").parquet(safe_output_path)
        print(f"[*] Results successfully saved at:\n    {safe_output_path}")
    else:
        print(f"\n[*] No book pairs found meeting the similarity threshold of {threshold}.")

# ==========================================
# ENTRY POINT
# ==========================================

def main():
    parser = argparse.ArgumentParser(description="Exact Pairwise Baseline Pipeline")
    parser.add_argument("--input", type=str, required=True, help="Path to input parquet")
    parser.add_argument("--output", type=str, default="data/sample/baseline_results.parquet", help="Path to save results")
    parser.add_argument("--threshold", type=float, default=0.4, help="Jaccard similarity threshold")
    parser.add_argument("--limit", type=int, default=100, help="Number of books to process")
    
    args = parser.parse_args()

    print("[*] Initializing Spark Session...")
    spark = SparkSession.builder \
        .appName("BookRecommendation_ExactBaseline") \
        .config("spark.sql.crossJoin.enabled", "true") \
        .master("local[*]") \
        .getOrCreate()

    spark.sparkContext.setLogLevel("WARN")

    run_baseline_pipeline(
        spark=spark, 
        input_path=args.input, 
        output_path=args.output, 
        threshold=args.threshold,
        sample_limit=args.limit
    )
    
    spark.stop()
    print("[*] Spark Session stopped. Pipeline finished.")

if __name__ == "__main__":
    main()