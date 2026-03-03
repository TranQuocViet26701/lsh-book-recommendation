# Code Standards & Codebase Structure

**Last Updated**: 2026-03-03
**Version**: 0.1.0
**Project**: LSH Book Recommendation System
**Applies To**: All code in this repository

## Core Development Principles

### YAGNI (You Aren't Gonna Need It)
- Implement features only when needed, not for hypothetical future requirements
- Start simple, refactor when necessary
- Avoid over-engineering and premature optimization

### KISS (Keep It Simple, Stupid)
- Prefer straightforward solutions
- Write code that's easy to understand and modify
- Choose clarity over cleverness

### DRY (Don't Repeat Yourself)
- Eliminate code duplication
- Extract common logic into reusable functions/modules
- Maintain single source of truth

## File Organization & Naming

### Directory Structure
```
lsh-book-recommendation/
├── config/               # Configuration (dev/cluster modes)
├── src/                  # Core pipeline (FLAT FILES, not subdirs)
├── api/                  # FastAPI server
├── frontend/             # Streamlit UI
├── scripts/              # Data ingestion utilities
├── tests/                # Unit & integration tests
├── notebooks/            # Jupyter exploration
├── data/                 # Datasets (sample/ + output/)
├── docker/               # Dev environment
├── docs/                 # Documentation
└── plans/                # Implementation plans
```

### File Naming Conventions

**Python Modules**: Use kebab-case for file names with descriptive intent
```python
# Good: clearly indicates purpose
text_cleaning_utils.py
gutenberg_downloader.py
hdfs_uploader.py
generate_sample_dataset.py

# Avoid: vague names
utils.py       # ✗ too generic
helper.py      # ✗ too generic
```

**Test Files**: `test_{module_name}.py`
```
test_preprocessing.py
test_shingling.py
test_minhash.py
test_lsh.py
```

**Configuration**: Environment-specific files
```
dev.env       # Development environment
cluster.env   # Cluster/production environment
settings.py   # Configuration loader
```

**Documentation**: Kebab-case with descriptive names
```
project-overview-pdr.md
system-architecture.md
deployment-guide.md
code-standards.md
```

## Python Code Style

### Module Structure
Every Python module should have:
1. Module docstring describing purpose
2. Imports (stdlib, third-party, local)
3. Type hints on all functions
4. Functions/classes with docstrings
5. `if __name__ == "__main__"` guard for executables

```python
"""Module purpose: what does this module do?

Key functions:
- function_name(): description
"""

from typing import Dict, List
from pyspark.sql import DataFrame, SparkSession
import nltk

def process_data(df: DataFrame) -> DataFrame:
    """Transform input DataFrame and return results.

    Args:
        df: Input DataFrame with columns [id, text]

    Returns:
        DataFrame with columns [id, tokens]
    """
    # Implementation
    pass

if __name__ == "__main__":
    main()
```

### Function Guidelines
- Keep functions < 30 lines (consider splitting if longer)
- Name functions with verb-noun pattern: `load_books()`, `clean_text()`, `strip_headers()`
- Use type hints for all parameters and return values
- Add docstrings with Args, Returns, Raises sections
- Handle errors explicitly with try-except

### Configuration & Constants
- Store configs in `config/settings.py`, not hardcoded
- Use dataclasses for configuration objects
- Environment-specific values via env vars (LSH_ENV)
- Access via: `from config.settings import config`

### Imports
- Organize: stdlib → third-party → local
- Use absolute imports: `from config.settings import config`
- Avoid `from module import *`
- Keep import count reasonable (< 20 imports per file)

## Testing Standards

### Unit Test Structure
```python
import pytest
from pyspark.sql import SparkSession

def test_function_name(spark: SparkSession):
    """Test description: what behavior is being validated."""
    # Arrange: set up test data
    # Act: call the function
    # Assert: verify results
    pass
```

### Testing Checklist
- [ ] Positive cases (happy path)
- [ ] Edge cases (empty data, single item, nulls)
- [ ] Error handling (invalid input, exceptions)
- [ ] Performance constraints (if applicable)

### Test File Location
```
tests/
├── conftest.py           # Shared fixtures (SparkSession)
├── test_preprocessing.py # Tests for src/preprocessing.py
├── test_shingling.py
├── test_minhash.py
└── test_lsh.py
```

### Running Tests
```bash
make test                    # Run all tests (from Makefile)
LSH_ENV=dev uv run pytest    # Custom execution
```

## Spark Code Patterns

### SparkSession Management
```python
from config.settings import config

def create_spark_session() -> SparkSession:
    """Create SparkSession from configuration."""
    return (SparkSession
        .builder
        .master(config.SPARK_MASTER)
        .appName(config.SPARK_APP_NAME)
        .config("spark.driver.memory", config.SPARK_DRIVER_MEMORY)
        .config("spark.executor.memory", config.SPARK_EXECUTOR_MEMORY)
        .getOrCreate())
```

### DataFrame Operations
- Use Spark SQL functions: `F.lower()`, `F.split()`, `F.explode()`
- For complex logic, create UDFs with type hints
- Cache frequently accessed DataFrames: `df.cache()`
- Show schema before transformations: `df.printSchema()`

### Reading/Writing Data
```python
# Reading Parquet (preferred format)
df = spark.read.parquet("path/to/data.parquet")

# Reading text files
df = spark.read.text("path/to/files")

# Writing Parquet with overwrite
df.write.mode("overwrite").parquet("output/path")
```

## Data Pipeline Conventions

### Module Responsibility
- **preprocessing.py**: Raw text → tokenized DataFrame
- **shingling.py**: Tokens → k-shingles
- **minhash.py**: Shingles → signatures
- **lsh.py**: Signatures → bucket assignments
- **query.py**: Query input → similar books
- **evaluation.py**: Results → metrics

### Data Flow Contracts
Each module should document:
- **Input Schema**: Column names, types, constraints
- **Output Schema**: Column names, types, meaning
- **Transformations**: Key operations performed
- **Side Effects**: Files written, external calls

Example:
```python
def preprocess_books(df: DataFrame) -> DataFrame:
    """Clean and tokenize raw book text.

    Input:  DataFrame(path: string, content: string)
    Output: DataFrame(book_id: string, tokens: array<string>)

    Raises:
        ValueError: If input schema doesn't match expected
    """
```

## Error Handling

### Patterns to Use
```python
# Explicit error handling
try:
    result = risky_operation()
except ValueError as e:
    logger.error(f"Invalid input: {e}")
    raise
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
    raise RuntimeError(f"Operation failed: {e}") from e
```

### Logging
```python
import logging

logger = logging.getLogger(__name__)

logger.info("Processing started")
logger.warning("Potential issue: {value}")
logger.error("Failed to process: {error}")
```

## Documentation Requirements

### Docstring Format
Use Google-style docstrings:
```python
def function_name(param1: str, param2: int) -> Dict[str, int]:
    """One-line description of what function does.

    Longer description explaining algorithm, edge cases, or important notes.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value and its structure

    Raises:
        ValueError: When param1 is empty
        TypeError: When param2 is not int

    Example:
        >>> result = function_name("test", 42)
        >>> result["count"]
        42
    """
```

### README Requirements for Modules
If a module is complex, add inline documentation:
- Module docstring at top
- Complex algorithm explanation
- Example usage
- Known limitations

## Security & Configuration

### Secrets Management
- Never commit `.env` files
- Use `.env.example` as template
- Load via `config.settings.py`
- No API keys in code

### Data Privacy
- Project Gutenberg data is public domain
- No user data collection
- Document data retention policies

## Code Review Checklist

- [ ] Follows naming conventions (kebab-case for files)
- [ ] Type hints on all functions
- [ ] Docstrings present and accurate
- [ ] No hardcoded paths/credentials
- [ ] Tests included and passing
- [ ] Handles errors explicitly
- [ ] Under 200 lines for most modules
- [ ] No duplicate code

## Performance Optimization

### Spark Optimization Hints
- Use DataFrame API instead of RDD for better optimization
- Partition data for parallel processing
- Cache intermediate results: `.cache()` or `.persist()`
- Use broadcast variables for small lookup tables: `F.broadcast(df)`
- Monitor Spark UI (localhost:4040) during execution

### Common Bottlenecks
- Reading/writing unoptimized file formats (use Parquet)
- Shuffling large datasets without partitioning
- Collecting large DataFrames to driver: avoid `.collect()` for big data

## Development Workflow

### Making Changes
1. Read existing code and tests
2. Understand the module's responsibility
3. Make minimal, focused changes
4. Add tests for new functionality
5. Run: `make test` and `make lint`
6. Commit with conventional format: `feat:`, `fix:`, `test:`, `docs:`

### Running the Pipeline
```bash
# Development mode (local Spark)
LSH_ENV=dev make run

# Full test + lint
make test
make lint

# Docker development
make docker
docker exec -it lsh-dev bash
```

## File Size Management

Target code file sizes:
- Most modules: < 150 lines
- Large modules (preprocessing.py): 100-200 lines acceptable
- Test files: 100-200 lines per test module
- Never exceed 500 lines (split if necessary)

If a file approaches 200 LOC, consider:
- Extract utility functions into a separate module
- Split into domain-specific submodules
- Use composition over large classes

## Version Control

### Commit Message Format
Use conventional commits:
```
feat: add shingling module
fix: correct stopword filtering in preprocessing
test: add 10 new tests for LSH
docs: update deployment guide
chore: update dependencies
```

### Branch Strategy
- Work on feature branches: `feature/shingling-algorithm`
- Keep main stable
- Squash/rebase before merging to main

## Continuous Integration

### Pre-commit Checks
- Linting: `ruff check .`
- Formatting: `ruff format .`
- Tests: `pytest -v`

### GitHub Actions
- Automatically run tests on PR
- Block merge if tests fail
- No secrets in CI logs

## Related Documentation

- [Project Overview & PDR](./project-overview-pdr.md)
- [System Architecture](./system-architecture.md)
- [Codebase Summary](./codebase-summary.md)
- [Deployment Guide](./deployment-guide.md)
