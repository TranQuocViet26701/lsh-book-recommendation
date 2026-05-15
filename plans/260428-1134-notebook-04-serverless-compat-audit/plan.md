---
title: "Notebook 04 Serverless Compatibility Audit"
description: "Single unified patch making the TN1-TN4 deliverable run on Databricks Free Edition Serverless (stops the whack-a-mole)."
status: pending-databricks-smoke
priority: P1
effort: 1.5h
branch: databricks-migration
tags: [databricks, serverless, notebook-04, compatibility, course-deliverable]
created: 2026-04-28
updated: 2026-04-28
---

# Plan — Notebook 04 Serverless Compatibility

## Goal

Make `notebooks/04_experiments.ipynb` (course-report TN1–TN4 deliverable) end-to-end runnable on Databricks Free Edition Serverless via ONE unified patch. Three Serverless restrictions hit in-session so far; this plan audits the rest statically and ships everything together.

## Phases

| # | Phase | Status | Effort |
|---|---|---|---|
| 01 | [Serverless Compat Patch](./phase-01-serverless-compat-patch.md) | impl-complete (Step 8 user-action pending) | 1.5h |

## Audit Summary (this session)

**Confirmed Serverless restrictions hit:**

| # | Restriction | Where | Status |
|---|---|---|---|
| 1 | `nltk` not pre-installed | runtime import | needs `%pip install nltk` + `dbutils.library.restartPython()` cell |
| 2 | `spark.sparkContext.*` blocked (`JVM_ATTRIBUTE_NOT_SUPPORTED`) | nb04 cell `c8dabfc4`; `src/minhash.py:87`; `src/query.py:98+:198` | nb04 gated (commit-pending); src/ fixed in commit `3af7ee9` |
| 3 | `.cache()` / `.persist()` / `.unpersist()` (`PERSIST TABLE not supported`, SQLSTATE 0A000) | nb04 cells `c8dabfc4`, `6797cfad` (TN1), `b986bdca` (TN3) | NEW — addressed in this phase |

**Static audit — anything else hiding in nb04 cells we never reached?** NO additional incompat found:

- nb04 has zero `dbutils.*`, zero RDD APIs, zero direct `sparkContext` left ungated
- All UDFs are regular `@F.udf` (Serverless-supported)
- TN3 `make_synthetic` uses `F.array(*[F.lit(i) for i in range(copies)]) + F.explode` — Spark Connect-compatible (memory risk only, not API restriction)
- All `.collect()` / `.toPandas()` calls operate on tiny DataFrames (≤93 rows or ≤size_target) — safe

## Key Dependencies

- Existing `_in_databricks` guard pattern in cell `c8dabfc4` (do not invent a second one)
- Closure-capture pattern already in `src/minhash.py` and `src/query.py`
- `docs/databricks-setup-guide.md` Step 8 smoke test sequence

## Run Modes

| Env | nb04 behavior | Notes |
|---|---|---|
| Local (`LSH_ENV=dev`) | `_maybe_cache(df)` keeps `.cache()`/`.unpersist()` (UDF re-compute is expensive on macOS Spark, ≥10× slower without cache) | 35-test suite must still pass |
| Databricks Serverless | `_maybe_cache(df)` returns `df` unchanged (no-op); `%pip install nltk` cell prepended | Smoke: setup → TN1 → TN2 → TN3 → TN4 → aggregate → CSV export |

## Critical Decisions

1. **`.cache()` strategy: conditional via `_maybe_cache(df)` helper, gated on `_in_databricks`**. Originally validated as Approach A (drop unconditionally) — but local nbconvert smoke test in Session 2 hit a timeout at the TN1 cell because UDF re-compute (md5 minhash × 100 hashes × 4 (b,r) configs) is much more expensive on macOS local Spark than the plan estimated. Switched to the documented fallback (`_maybe_cache`): one-line helper in setup cell, applied at 5 call sites. Serverless still gets no caching (helper returns `df` unchanged); local restores prior behavior.
2. **`%pip install nltk` placement**: prepended as cell 0 (before all setup). On local Jupyter `%pip` is a valid magic (no-op-ish — installs into user env, harmless). `dbutils.library.restartPython()` errors silently in non-Databricks → wrap in try/except OR gate on `_in_databricks` env detection.
3. **Unified guard pattern**: reuse the `_in_databricks` flag established in cell `c8dabfc4`. Do not invent a second variant.
4. **No src/ changes needed**: audit confirms `src/{shingling,minhash,lsh,query,evaluation,utils,query_by_text_helpers}.py` are Serverless-clean for the nb04 path. `src/preprocessing.py:68+:101` remain incompat but are out-of-scope (only fire from nb02).

## Public Deliverables

- 1 modified notebook: `notebooks/04_experiments.ipynb` (1 cell prepended + 4 cells modified)
- 1 modified doc: `docs/databricks-setup-guide.md` (new "Serverless Compatibility Checklist" section)
- 0 new files, 0 deletions

## Unresolved Questions

- **`%pip install` on local Jupyter**: needs 30s smoke test before locking design. If it errors, gate on `_in_databricks` via raw cell content (less elegant). Phase-01 step 1 covers this.
- **TN3 size=1500 on Free Edition driver memory**: ~~orthogonal to this patch~~ → resolved 2026-04-28 via validation: drop default to `[200, 500, 1000]` proactively. See Validation Log Session 1.
- **`dbutils.library.restartPython()` on local**: errors with `NameError: dbutils`. Resolved 2026-04-28: try/except wrapper (Phase-01 step 2). See Validation Log Session 1.

## Validation Log

### Session 1 — 2026-04-28
**Trigger:** Initial plan creation (`/plan:validate` after `/plan:fast`)
**Questions asked:** 4

#### Questions & Answers

1. **[Architecture/Tradeoff]** The plan picks Approach A: drop all `.cache()`/`.unpersist()` calls unconditionally (re-compute cost ~3s on local for 93 books, sub-second on Serverless). Confirm this strategy?
   - Options: Drop unconditionally (Recommended) | Conditional cache locally | Materialize via parquet roundtrip
   - **Answer:** Drop unconditionally
   - **Rationale:** Confirms Approach A (KISS). Phase-01 steps 3-5 stay as-written. No behavior branching by env.

2. **[Architecture]** How should we guard `dbutils.library.restartPython()` so the install cell doesn't break local Jupyter?
   - Options: try/except NameError (Recommended) | Gate on `_in_databricks` env check | Skip restart, rely on order
   - **Answer:** try/except NameError
   - **Rationale:** Confirms Phase-01 step 2 wrapper. Avoids re-computing the env flag at cell 0 before it's defined.

3. **[Risk]** TN3 currently defaults to `sizes_tn3 = [200, 500, 1000, 1500]`. Free Edition driver memory is tight. What should the default be?
   - Options: Keep [200, 500, 1000, 1500] | Drop to [200, 500, 1000] proactively (Recommended) | Conditional sizes by env
   - **Answer:** Drop to [200, 500, 1000] proactively
   - **Rationale:** Avoids likely OOM on Free Edition; trend is already visible at size=1000. Requires phase-01 plan update (new step + risk table refresh).

4. **[Scope/Risk]** If the Free Edition smoke test (Step 8) reveals a NEW Serverless restriction not in the static audit, what's the protocol?
   - Options: Patch in this same phase (Recommended) | Open phase-02 | Defer to next session
   - **Answer:** Patch in this same phase
   - **Rationale:** Keeps unified-patch goal. Phase-01 stays open until smoke passes; one commit ships everything.

#### Confirmed Decisions

- Cache strategy: drop unconditionally (no env branching) — **revised in Session 2**
- dbutils restart guard: try/except NameError
- TN3 default sizes: `[200, 500, 1000]` — drop the 1500 size proactively
- Smoke-failure protocol: patch in phase-01, re-test, single commit

### Session 2 — 2026-04-28 (post-implementation)
**Trigger:** Local nbconvert smoke test (Phase-01 Step 6) — TN1 cell timed out at 600s after `.cache()` removal.

#### Findings

- The plan's "<3s extra on local" estimate underestimated UDF re-compute cost. Without cache, `sigs_tn1` is recomputed for each of 4 (b,r) configs in the TN1 loop. md5-based minhash UDF over 93 books × 100 hashes, recomputed 4× through PySpark Python-JVM serialization, exceeds 600s on macOS local Spark.
- Spark Web UI showed Stage 7 stuck on "1 + 1 / 2" tasks — typical Python UDF backpressure on macOS.
- pytest 35/35 still passed (tests don't exercise the loop pattern).

#### Revised Decision

- **Cache strategy: conditional via `_maybe_cache(df)` helper, gated on `_in_databricks`** (the documented Phase-01 fallback). Approach A is overruled.
- Serverless still gets no caching (helper returns `df` unchanged on Databricks); local restores prior behavior. Best of both worlds, +5 LoC vs Approach A.

#### Action Items

- [x] Add `_maybe_cache` helper to setup cell `c8dabfc4`
- [x] Replace `.cache()` calls in setup, TN1, TN3 with `_maybe_cache(...)` wrapping
- [x] Guard `.unpersist()` in TN3 loop on `if not _in_databricks:`
- [x] Re-run pytest (35/35) and nbconvert smoke (full notebook completes)
- [x] Update Phase-01 Steps 3/4/5 + risk table to reflect the helper

#### Impact on Phases

- **Phase 01**: Steps 3, 4, 5a updated to reflect `_maybe_cache(df)` instead of unconditional drop. Risk table row "Drop-cache causes >2× local nb04 slowdown" → "Resolved 2026-04-28 via `_maybe_cache` helper".

#### Action Items

- [x] Add new step to phase-01: drop `sizes_tn3 = [200, 500, 1000, 1500]` → `[200, 500, 1000]` in cell `b986bdca`
- [x] Update phase-01 risk table: TN3 OOM risk drops from "Med likelihood/Med impact" to "Low/Low" after the size cut

#### Impact on Phases

- **Phase 01**: Add Step 5b (TN3 size cut) before the existing Step 6 (regression test). Update Step 5 wording to mention the size change. Refresh risk table TN3 row.
