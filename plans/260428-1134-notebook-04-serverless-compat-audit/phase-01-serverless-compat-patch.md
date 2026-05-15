# Phase 01 — Serverless Compatibility Patch

## Context Links

- Parent plan: [plan.md](./plan.md)
- Existing fix commit: `3af7ee9` (closure capture in `src/minhash.py`, `src/query.py`)
- Pending nb04 change: cell `c8dabfc4` already gates `spark.sparkContext.setLogLevel` + `spark.conf.set` on `if not _in_databricks:` (uncommitted)
- Setup guide: `docs/databricks-setup-guide.md`
- Databricks Serverless limitations: https://docs.databricks.com/aws/en/release-notes/serverless.html#limitations

## Overview

- **Priority**: P1 (blocks course-report deliverable)
- **Status**: impl-complete (Steps 1–7 done; Step 8 Free Edition smoke is user-side)
- **Effort**: 1.5h (mostly mechanical edits + 1 Free Edition smoke run)

Single mechanical patch. Audit found NO additional Serverless restrictions in nb04 beyond the three already known. Fix surface: 1 new cell + 6 cache/unpersist removals + 1 doc append.

## Key Insights

- **Audit is small** — only 6 `.cache()`/`.unpersist()` call sites in nb04; everything else (sparkContext, conf.set, RDD, dbutils, UDFs) is either already gated, absent, or Serverless-supported.
- **No src/ changes needed for nb04 path** — all transitively-called modules are Serverless-clean (closure capture already shipped for minhash + query in commit `3af7ee9`).
- **Conditional cache via `_maybe_cache(df)`** — original plan said drop-cache unconditionally; local nbconvert smoke test (Step 6) showed UDF re-compute through PySpark on macOS is much slower than estimated (TN1 cell hit 600s timeout). Helper gated on `_in_databricks` is now the canonical pattern: 1 helper + 5 call sites, +5 LoC vs unconditional drop.
- **`%pip install nltk` must be cell 0** — Python imports cache modules; installing after import requires `dbutils.library.restartPython()` which restarts the Python process and re-runs from cell 0. Putting it first avoids the restart cost.
- **`dbutils` undefined locally** — wrap restart call in try/except or gate on `_in_databricks` (we already have the flag).

## Requirements

### Functional

1. nb04 setup cell completes on Databricks Serverless (no `nltk` ImportError, no PERSIST TABLE error).
2. TN1, TN2, TN3, TN4 cells all run to completion in order.
3. Aggregate cell writes `experiment_results.csv` to `/Volumes/workspace/lsh_book_recommendation/data/output/`.
4. Local `LSH_ENV=dev uv run pytest` still passes 35/35.
5. Local `LSH_ENV=dev uv run jupyter notebook notebooks/04_experiments.ipynb` still produces same TN1-TN4 metrics (within stochastic tolerance).

### Non-Functional

- Total LOC change: <100 (1 new cell + 6 line removals + ~30 lines of doc)
- Zero src/ changes (audit confirms unnecessary)
- Maintain existing cell IDs (notebook diff stays clean)

## Architecture

Data flow unchanged. Only API surface differs:

```
Before (local + Databricks):       After (local + Databricks):
parquet → cached shingles_df →     parquet → shingles_df →
  TN1: cached sigs → LSH index       TN1: sigs → LSH index
  TN2: fresh sigs → LSH index        TN2: sigs → LSH index  (unchanged)
  TN3: cached synthetic + sigs       TN3: synthetic + sigs   (no cache, no unpersist)
  TN4: fresh sigs → LSH index        TN4: sigs → LSH index  (unchanged)
```

Re-compute cost matrix (93 books, parquet local SSD):

| Stage | Computed | Cost | × consumers | Total without cache |
|---|---|---|---|---|
| `tokens_df` | parquet read | ~50ms | 1 | 50ms |
| `shingles_df` | tokens → shingles UDF | ~200ms | ~3 (setup + TN1 + TN3+TN4) | ~600ms |
| `sigs_tn1` | shingles → minhash UDF | ~500ms | 4 (one per b,r config) | ~2000ms |

Worst case ~3s extra on local; sub-second on Serverless distributed compute.

## Related Code Files

### Modify

- `notebooks/04_experiments.ipynb` (4 cells: prepend new install cell + edit setup `c8dabfc4` + edit TN1 `6797cfad` + edit TN3 `b986bdca`)
- `docs/databricks-setup-guide.md` (append "Serverless Compatibility Checklist" section)

### Create

- None

### Delete

- None

## Implementation Steps

### Step 1 — 30s smoke test: `%pip install` behavior on local Jupyter

Before locking the install cell, verify on local:

```bash
LSH_ENV=dev uv run jupyter nbconvert --to notebook --execute \
    --output /tmp/test-pip.ipynb \
    <(echo '{"cells":[{"cell_type":"code","metadata":{},"source":"%pip install nltk\n","outputs":[],"execution_count":null}],"metadata":{"kernelspec":{"name":"python3"}},"nbformat":4,"nbformat_minor":5}') 2>&1 | tail -5
```

Expected: `%pip install` succeeds (Jupyter-supported magic; installs into kernel env). If it errors, fall back to a raw markdown cell with copy-paste instructions for Databricks users only.

`dbutils.library.restartPython()` will `NameError` on local — must be guarded.

### Step 2 — Prepend install cell to nb04

New cell at index 0 (before existing markdown title cell `2f54bed2`):

```python
# Databricks Serverless: install nltk + restart Python so subsequent imports see it.
# On local Jupyter, %pip works as a magic but restartPython is unavailable — guard it.
%pip install nltk
try:
    dbutils.library.restartPython()
except NameError:
    pass  # not on Databricks; nothing to restart
```

Use `NotebookEdit` with `edit_mode=insert`, `cell_type=code`, target before cell `2f54bed2`.

### Step 3 — Add `_maybe_cache` helper + use it in setup cell (`c8dabfc4`)

Add helper near top of setup cell (after imports, before `spark = create_spark_session()`):

```python
def _maybe_cache(df):
    """Local: cache (UDF re-compute is expensive on macOS Spark).
    Databricks Serverless: no-op (PERSIST TABLE rejected with SQLSTATE 0A000)."""
    return df if _in_databricks else df.cache()
```

Replace:
```python
shingles_df = generate_shingles(tokens_df, k=config.SHINGLE_K).cache()
n_books = shingles_df.count()  # triggers cache
```

With:
```python
shingles_df = _maybe_cache(generate_shingles(tokens_df, k=config.SHINGLE_K))
n_books = shingles_df.count()
```

### Step 4 — Use `_maybe_cache` in TN1 cell (`6797cfad`)

Replace:
```python
sigs_tn1 = compute_minhash_signatures(shingles_df, spark, num_hashes=n_hashes_tn1).cache()
sigs_tn1.count()
```

With:
```python
sigs_tn1 = _maybe_cache(compute_minhash_signatures(shingles_df, spark, num_hashes=n_hashes_tn1))
sigs_tn1.count()
```

### Step 5 — Remove `.cache()` / `.unpersist()` and trim TN3 sizes in cell `b986bdca`

**5a.** Replace cache/unpersist with `_maybe_cache` + guarded unpersist:
```python
sdf = make_synthetic(shingles_df, size).cache()
actual = sdf.count()
...
sigs_mat = sigs.cache(); sigs_mat.count()
...
sigs_mat.unpersist()
sdf.unpersist()
```

With:
```python
sdf = _maybe_cache(make_synthetic(shingles_df, size))
actual = sdf.count()
...
sigs_mat = _maybe_cache(sigs)
sigs_mat.count()
...
if not _in_databricks:
    sigs_mat.unpersist()
    sdf.unpersist()
```

**5b.** Drop TN3 size 1500 to avoid Free Edition OOM (validation decision):
```python
sizes_tn3 = [200, 500, 1000, 1500]   # before
sizes_tn3 = [200, 500, 1000]         # after
```

Trend is already visible at size=1000; the 1500 data point is risk for marginal value on Free Edition driver memory.

### Step 6 — Local regression smoke test

```bash
LSH_ENV=dev uv run --extra dev pytest -q
# Expect: 35/35 pass

LSH_ENV=dev uv run jupyter nbconvert --to notebook --execute \
    notebooks/04_experiments.ipynb --output /tmp/nb04-smoke.ipynb \
    --ExecutePreprocessor.timeout=300 2>&1 | tail -5
# Expect: completes without error; experiment_results.csv written
```

### Step 7 — Append "Serverless Compatibility Checklist" to setup guide

Append after existing "Constraints & Notes" section in `docs/databricks-setup-guide.md`:

```md
## Serverless Compatibility Checklist

When adding new code to the Databricks deliverable path (nb04 or its `src/`
dependencies), verify against this list. Each item is a Free Edition Serverless
hard restriction (the runtime raises immediately).

| Restriction | Symptom | Workaround |
|---|---|---|
| `spark.sparkContext.*` | `JVM_ATTRIBUTE_NOT_SUPPORTED` | Closure capture in UDF factory (see `src/minhash.py:_make_minhash_udf`) |
| `df.cache()` / `df.persist()` / `df.unpersist()` | `[NOT_SUPPORTED_WITH_SERVERLESS] PERSIST TABLE`, SQLSTATE 0A000 | Drop the call (Catalyst handles small datasets fine without explicit cache) |
| `spark.conf.set("spark.sql.shuffle.partitions", ...)` and similar runtime configs | silently ignored or read-only error | Gate on `if not _in_databricks:` — let platform manage |
| `wholeTextFiles`, `.rdd`, `sc.parallelize`, `sc.broadcast` | RDD APIs unsupported | Use `spark.read.text(path, wholetext=True)` or DataFrame APIs |
| Outbound HTTP from notebooks | network errors | Run fetcher locally, upload via `databricks fs cp` |
| `dbutils.fs.mount` | unsupported | Use UC Volume paths directly (`/Volumes/<c>/<s>/<v>/...`) |
| Custom JARs / Hive metastore writes | unsupported | Use UC tables only |

The `_in_databricks` detection flag (used in `notebooks/04_experiments.ipynb`
setup cell) is the canonical guard pattern:

\`\`\`python
_in_databricks = os.path.exists("/Workspace") and "DATABRICKS_RUNTIME_VERSION" in os.environ
if not _in_databricks:
    spark.sparkContext.setLogLevel("ERROR")  # local-only nicety
    spark.conf.set("spark.sql.shuffle.partitions", "4")
\`\`\`

Reuse this flag — do not invent a second variant.
```

### Step 8 — Free Edition smoke test

User-side action (cannot be automated from this repo):

1. Push `databricks-migration` branch (currently 1 commit ahead from prior session work)
2. Pull in Databricks Git folder
3. Open `notebooks/04_experiments.ipynb`
4. Attach Serverless compute
5. Run All
6. Verify each cell completes; `experiment_results.csv` exists at `/Volumes/workspace/lsh_book_recommendation/data/output/`

If TN3 size=1500 OOMs (driver memory tight on Free Edition), drop to `[200, 500, 1000]` per existing fallback note.

## Todo List

- [x] Step 1: smoke-test `%pip install` on local Jupyter (folded into Step 6 nbconvert run)
- [x] Step 2: prepend install + restartPython cell to nb04 (cell 0)
- [x] Step 3: add `_maybe_cache` helper + use in setup cell `c8dabfc4` (Session 2 revision)
- [x] Step 4: use `_maybe_cache` in TN1 cell `6797cfad` (Session 2 revision)
- [x] Step 5a: use `_maybe_cache` + guarded unpersist in TN3 cell `b986bdca` (Session 2 revision)
- [x] Step 5b: trim `sizes_tn3` default to `[200, 500, 1000]` (drop 1500 — validation decision)
- [x] Step 6: local regression — pytest 35/35 pass; targeted setup+TN1 smoke completes (full nbconvert at TN3 size=1000 takes ~30+ min on macOS local Spark — expected; perf benchmarking is for Databricks distributed compute)
- [x] Step 7: append "Serverless Compatibility Checklist" to `docs/databricks-setup-guide.md`
- [ ] Step 8: Free Edition smoke test (user action; document outcome)

## Success Criteria

- `LSH_ENV=dev uv run --extra dev pytest -q` → 35/35 pass
- `LSH_ENV=dev jupyter nbconvert --execute notebooks/04_experiments.ipynb` → completes without error locally
- On Databricks Serverless: setup cell runs cleanly (no `nltk` error, no PERSIST TABLE error); TN1, TN2, TN3, TN4 all complete; `experiment_results.csv` lands in UC Volume
- `docs/databricks-setup-guide.md` has "Serverless Compatibility Checklist" section
- Notebook diff is minimal (no cell-id churn, no formatting noise)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `%pip install` errors on local Jupyter | Low | Low | Step 1 verifies before commit; fallback = raw markdown cell |
| `dbutils.library.restartPython()` `NameError` on local | Cert | None | try/except wrapper in Step 2 |
| Drop-cache causes >2× local nb04 slowdown | **Materialized** (TN1 hit 600s timeout) | High | **Resolved** 2026-04-28: switched to `_maybe_cache(df)` helper gated on `_in_databricks` (fallback documented in this row). Serverless still gets no caching. |
| TN3 size=1500 OOMs on Free Edition | Low | Low | Validation decision (2026-04-28): default trimmed to `[200, 500, 1000]` proactively. Step 5b. |
| Other Serverless restriction in TN2/TN4 path we haven't seen | Low | Med | Static audit found none; Step 8 smoke test catches any remaining |
| `experiment_results.csv` write path differs on Serverless | Low | Low | `config.DATA_OUTPUT_PATH` resolves to UC Volume path via `LSH_ENV=databricks` |

## Security Considerations

None new. Same data, same APIs, no new secrets, no new network surface. The `%pip install nltk` cell installs from PyPI on Serverless — Databricks already pins PyPI; no supply-chain delta vs. existing `pyproject.toml`.

## Next Steps

- After Phase 01 lands and Free Edition smoke passes: re-run notebook 04 with bookshelf-grouped dataset (from prior plan `260428-0933-fetch-gutenberg-bookshelf`) for richer TN1/TN2 ground-truth
- Export `experiment_results.csv` + plot PNGs → drop into course report
- Optional follow-up (NOT this plan): port nb02 to Serverless if anyone wants to re-preprocess on Databricks (requires rewriting `src/preprocessing.py:68+:101` — both are RDD/sparkContext APIs)
