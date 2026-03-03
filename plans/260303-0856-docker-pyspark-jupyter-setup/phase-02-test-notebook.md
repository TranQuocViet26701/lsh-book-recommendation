# Phase 02 -- Test Notebook

## Context Links

- [plan.md](./plan.md)
- [Phase 01](./phase-01-docker-configuration.md)
- [Current notebook](/notebooks/01_data_exploration.ipynb)
- [text_cleaning_utils.py](/scripts/text_cleaning_utils.py)
- [config/settings.py](/config/settings.py)

## Overview

- **Priority**: P1
- **Status**: completed
- **Description**: Replace stub notebook `01_data_exploration.ipynb` with real working Spark-based data exploration

## Key Insights

- Current notebook has 16 cells; first 7 work (os-based), rest are TODO stubs
- Notebook uses `sys.path.insert(0, '..')` hack -- replace with clean import (PYTHONPATH=/app set in Phase 01)
- DevConfig: `DATA_RAW_PATH = "./data/sample/"`, `SPARK_MASTER = "local[*]"`
- `scripts.clean_gutenberg_text()` is the main text cleaning function to demo
- 94 .txt files in data/sample/, named pg{ID}.txt
- Notebook language: mix of Vietnamese headers (keep for team) + English code/comments
- Working dir inside container: `/app` (notebooks run from `/app/notebooks`, but PYTHONPATH=/app handles imports)

## Requirements

### Functional
- SparkSession initializes with `local[*]` master using config
- Load all .txt files from `data/sample/` into a Spark DataFrame
- Show basic stats: file count, avg/min/max word count per book
- Demo `clean_gutenberg_text` on sample text
- Show data is ready for LSH pipeline (cleaned text sample, word count distribution)

### Non-Functional
- Notebook runs end-to-end in < 30 seconds on sample data
- Clear markdown headers for each section
- No `sys.path` hacks

## Architecture

```
Notebook execution flow:
1. Import config, scripts
2. Create SparkSession(local[*])
3. Read .txt files into RDD -> DataFrame
4. Compute stats (word count, file size, line count)
5. Demo text cleaning with scripts.clean_gutenberg_text
6. Show cleaned text stats
7. Summarize readiness for LSH pipeline
8. Stop SparkSession
```

## Related Code Files

### Modify
- `notebooks/01_data_exploration.ipynb` -- full rewrite of notebook cells

### Read-only references
- `scripts/text_cleaning_utils.py` -- `clean_gutenberg_text()` function
- `scripts/__init__.py` -- exports `clean_gutenberg_text`
- `config/settings.py` -- `DevConfig` with paths and Spark config

## Implementation Steps

### Cell-by-cell specification

**Cell 0 (markdown):**
```markdown
# 01 -- Data Exploration with PySpark

Explore the Project Gutenberg sample dataset using PySpark in local mode.

**Goals:**
- Load book .txt files into Spark
- Compute basic statistics (count, word count, file size)
- Demo text cleaning pipeline
- Verify data readiness for LSH
```

**Cell 1 (code) -- Setup & Imports:**
```python
from config.settings import config
from scripts import clean_gutenberg_text

print(f"Environment: {config.ENV}")
print(f"Spark master: {config.SPARK_MASTER}")
print(f"Data path: {config.DATA_RAW_PATH}")
```

No `sys.path` hack needed -- PYTHONPATH=/app handles it.

**Cell 2 (code) -- Initialize SparkSession:**
```python
from pyspark.sql import SparkSession

spark = (
    SparkSession.builder
    .master(config.SPARK_MASTER)
    .appName(config.SPARK_APP_NAME)
    .config("spark.driver.memory", config.SPARK_DRIVER_MEMORY)
    .config("spark.executor.memory", config.SPARK_EXECUTOR_MEMORY)
    .config("spark.ui.showConsoleProgress", "false")
    .getOrCreate()
)

sc = spark.sparkContext
print(f"Spark version: {spark.version}")
print(f"Master: {sc.master}")
print(f"Parallelism: {sc.defaultParallelism}")
```

**Cell 3 (markdown):**
```markdown
## 1. Load Book Files
Read all .txt files from `data/sample/` into a Spark DataFrame.
```

**Cell 4 (code) -- Load files into DataFrame:**
```python
import os

sample_dir = config.DATA_RAW_PATH
files = [f for f in os.listdir(sample_dir) if f.endswith(".txt")]
print(f"Found {len(files)} book files")

# Read all text files using wholeTextFiles (returns (path, content) pairs)
rdd = sc.wholeTextFiles(f"file://{os.path.abspath(sample_dir)}/*.txt")
print(f"RDD partitions: {rdd.getNumPartitions()}")
print(f"Total books loaded: {rdd.count()}")
```

**Cell 5 (code) -- Create DataFrame with book metadata:**
```python
from pyspark.sql import Row
from pyspark.sql.types import StructType, StructField, StringType, IntegerType

def parse_book(pair):
    path, content = pair
    filename = os.path.basename(path)
    book_id = filename.replace("pg", "").replace(".txt", "")
    lines = content.split("\n")
    words = content.split()
    return Row(
        book_id=book_id,
        filename=filename,
        num_lines=len(lines),
        num_words=len(words),
        num_chars=len(content),
    )

books_df = rdd.map(parse_book).toDF()
books_df.cache()
books_df.show(10, truncate=False)
```

**Cell 6 (markdown):**
```markdown
## 2. Basic Statistics
```

**Cell 7 (code) -- Aggregate stats:**
```python
from pyspark.sql import functions as F

stats = books_df.agg(
    F.count("book_id").alias("total_books"),
    F.mean("num_words").cast("int").alias("avg_words"),
    F.min("num_words").alias("min_words"),
    F.max("num_words").alias("max_words"),
    F.mean("num_chars").cast("int").alias("avg_chars"),
    F.sum("num_words").alias("total_words"),
)
stats.show(truncate=False)
```

**Cell 8 (code) -- Word count distribution:**
```python
import pandas as pd
import matplotlib.pyplot as plt

pdf = books_df.select("book_id", "num_words").toPandas()

fig, ax = plt.subplots(figsize=(10, 4))
ax.hist(pdf["num_words"], bins=30, edgecolor="black", alpha=0.7)
ax.set_xlabel("Word Count")
ax.set_ylabel("Number of Books")
ax.set_title("Word Count Distribution Across Sample Books")
ax.axvline(pdf["num_words"].mean(), color="red", linestyle="--", label=f"Mean: {pdf['num_words'].mean():.0f}")
ax.legend()
plt.tight_layout()
plt.show()
```

**Cell 9 (markdown):**
```markdown
## 3. Text Cleaning Demo
Use `scripts.clean_gutenberg_text()` to strip Gutenberg headers/footers and normalize text.
```

**Cell 10 (code) -- Demo cleaning on a single book:**
```python
# Pick one book to demonstrate cleaning
sample_path, sample_content = rdd.first()
sample_name = os.path.basename(sample_path)

print(f"Book: {sample_name}")
print(f"Raw length: {len(sample_content)} chars")
print(f"\n--- RAW (first 300 chars) ---")
print(sample_content[:300])

cleaned = clean_gutenberg_text(sample_content)
print(f"\n--- CLEANED (first 300 chars) ---")
print(cleaned[:300])
print(f"\nCleaned length: {len(cleaned)} chars")
print(f"Reduction: {(1 - len(cleaned)/len(sample_content))*100:.1f}%")
```

**Cell 11 (code) -- Clean all books and compare:**
```python
from pyspark.sql.functions import udf
from pyspark.sql.types import StringType, IntegerType

# Register UDF for cleaning
clean_udf = udf(clean_gutenberg_text, StringType())
word_count_udf = udf(lambda text: len(text.split()) if text else 0, IntegerType())

# Reload with content column
books_with_text = rdd.map(
    lambda pair: Row(
        book_id=os.path.basename(pair[0]).replace("pg", "").replace(".txt", ""),
        raw_text=pair[1],
    )
).toDF()

cleaned_df = (
    books_with_text
    .withColumn("cleaned_text", clean_udf("raw_text"))
    .withColumn("raw_words", word_count_udf("raw_text"))
    .withColumn("cleaned_words", word_count_udf("cleaned_text"))
    .select("book_id", "raw_words", "cleaned_words")
)

cleaned_df.cache()
cleaned_df.show(10)

# Summary
cleaned_df.agg(
    F.mean("raw_words").cast("int").alias("avg_raw_words"),
    F.mean("cleaned_words").cast("int").alias("avg_cleaned_words"),
).show()
```

**Cell 12 (markdown):**
```markdown
## 4. Data Readiness for LSH Pipeline

The data is ready for the LSH pipeline:
- Books loaded into Spark DataFrames
- Text cleaning removes Gutenberg boilerplate
- Each book has a unique ID (from filename)
- Cleaned text ready for: shingling -> minhash -> LSH bucketing

**Next steps:** `02_preprocessing_demo.ipynb`
```

**Cell 13 (code) -- Sample cleaned output:**
```python
# Show a sample of cleaned text to verify quality
sample_cleaned = cleaned_df.join(
    books_with_text, on="book_id"
).select("book_id", "cleaned_words").orderBy(F.desc("cleaned_words"))

print("Top 10 books by word count (after cleaning):")
sample_cleaned.show(10, truncate=False)
```

**Cell 14 (code) -- Stop SparkSession:**
```python
spark.stop()
print("SparkSession stopped. Data exploration complete.")
```

### Important Notes for Implementation

1. **Working directory**: Notebook runs from `/app/notebooks` in container but PYTHONPATH=/app means imports resolve from `/app`
2. **File paths**: `config.DATA_RAW_PATH` is `./data/sample/` which resolves relative to `/app` (working_dir in compose)
3. **wholeTextFiles**: Spark method that reads each file as a single record (path, content); ideal for book-sized text files
4. **UDF for cleaning**: Register `clean_gutenberg_text` as a Spark UDF to apply across all books in parallel
5. **matplotlib**: Already in pyproject.toml dependencies; works in Jupyter inline

## Todo List

- [x] Replace all cells in `notebooks/01_data_exploration.ipynb` with spec above
- [x] Verify notebook structure: 15 cells (8 code + 7 markdown including title)
- [x] Ensure no `sys.path` hacks remain
- [x] Ensure `clean_gutenberg_text` imported from `scripts` package
- [x] Ensure SparkSession uses `config.SPARK_MASTER` (local[*])
- [x] Include matplotlib histogram for word count distribution
- [x] End with `spark.stop()` to clean up resources

## Success Criteria

1. All cells execute without errors inside Docker container
2. SparkSession starts in local[*] mode
3. All ~94 sample books loaded into DataFrame
4. Statistics displayed (count, avg/min/max words)
5. Word count histogram renders inline
6. `clean_gutenberg_text` runs on all books via UDF
7. Before/after cleaning comparison shown
8. No `sys.path` manipulation in any cell

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `wholeTextFiles` OOM on large books | Low (sample is small) | Medium | 94 books ~50MB total; 2g driver memory sufficient |
| matplotlib not rendering in Jupyter | Low | Low | Already works in standard Jupyter; `%matplotlib inline` if needed |
| UDF serialization fails for clean_gutenberg_text | Low | High | Function is pure Python, no closures; should serialize fine |
| Notebook working dir mismatch | Medium | High | Use `os.path.abspath` with config paths; PYTHONPATH handles imports |

## Security Considerations

- No credentials or secrets in notebook
- All data is public domain (Project Gutenberg)
- Notebook in git; no sensitive outputs committed (just stats)

## Next Steps

- After this notebook works, team can proceed to `02_preprocessing_demo.ipynb` (shingling)
- Docker environment validated and ready for full pipeline development
