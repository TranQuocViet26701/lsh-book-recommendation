import os
import sys
import time
import argparse

# =====================================================================
# WINDOWS ENVIRONMENT FIX: PREVENT PYTHON WORKER CONNECTION TIMEOUTS
# Forces Spark to use the exact Python executable from the virtual env
# =====================================================================
os.environ["PYSPARK_PYTHON"] = sys.executable
os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
os.environ["SPARK_LOCAL_IP"] = "127.0.0.1"
# =====================================================================

# Import EXACT functions from your team's modules
from src.preprocessing import create_spark_session, load_raw_books, preprocess_books
from src.shingling import generate_shingles

# Import the config manager
from config.settings import config 

def run_preparation_pipeline(output_path):
    """
    Executes the end-to-end data preparation for Pairwise pipeline: 
    Raw Text -> Cleaned Tokens -> k-Shingles -> Parquet.
    """
    print("\n" + "="*50)
    print("🚀 STARTING DATA PREPARATION PAIRWISE PIPELINE (FORCED LOCAL MODE)")
    print("="*50)
    
    # =====================================================================
    # BULLETPROOF LOCAL OVERRIDE (Bypasses HDFS localhost:9000 issues)
    # Get absolute Windows path and force the file:/// URI scheme
    # =====================================================================
    current_dir = os.path.abspath(os.getcwd())
    safe_dir = current_dir.replace("\\", "/")
    
    local_raw_path = f"file:///{safe_dir}/data/sample/raw_texts/"
    
    print(f"[*] Overriding HDFS config to local path:\n    {local_raw_path}")
    
    # Override the config variable running in RAM
    config.DATA_RAW_PATH = local_raw_path
    # =====================================================================
    
    start_time = time.time()

    # Step 1: Start Spark using the team's custom builder
    print("\n[*] Step 1: Initializing Spark Session...")
    spark = create_spark_session()
    spark.sparkContext.setLogLevel("WARN")

    # Step 2: Load Raw Books 
    print(f"[*] Step 2: Loading raw texts...")
    try:
        raw_df = load_raw_books(spark)
    except Exception as e:
        print(f"[!] Error loading text. Please ensure raw data exists. Details: {e}")
        spark.stop()
        return

    # Step 3: Preprocess / Clean Text
    print("[*] Step 3: Cleaning text, tokenizing, and removing stopwords...")
    clean_df = preprocess_books(raw_df, spark)

    # Step 4: Generate Shingles
    print(f"[*] Step 4: Generating {config.SHINGLE_K}-shingles...")
    shingled_df = generate_shingles(clean_df)

    # Step 5: Save to Parquet
    # Force the output path to use file:/// as well for safety
    safe_output = f"file:///{safe_dir}/{output_path