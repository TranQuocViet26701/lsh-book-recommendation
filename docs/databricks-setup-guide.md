# Databricks Free Edition Setup Guide

End-to-end setup for running `notebooks/04_experiments.ipynb` on Databricks Free Edition (Serverless).

---

## Prerequisites

- Databricks account (Free Edition — see Step 1)
- GitHub Personal Access Token (PAT) with `Contents: Read & Write` on this repo
- Local repo cloned at `databricks-migration` branch
- Pre-cleaned parquet artifact at `data/output/cleaned/*.parquet` (93 books, validated)

---

## Step 1 — Sign Up for Free Edition

1. Visit https://login.databricks.com/?dbx_source=www&intent=SIGN_UP
2. Pick **Free Edition** (NOT the 14-day Premium trial)
3. Verify email → land on workspace home

---

## Step 2 — Bootstrap NLTK Stopwords Locally

Databricks Serverless restricts outbound internet, so `nltk.download()` at runtime fails. Pre-bundle the corpus:

```bash
cd /path/to/lsh-book-recommendation
uv run python scripts/bootstrap-nltk-stopwords-to-volume.py
# Produces ./build/nltk_data/corpora/stopwords/
```

---

## Step 3 — Create UC Catalog / Schema / Volume

Databricks UI:

1. Sidebar → **Catalog**
2. If `workspace` catalog missing → create it (Free Edition usually pre-creates)
3. Inside `workspace` → **Create schema** → name: `lsh_book_recommendation`
4. Inside the schema → **Create volume** → type: **Managed** → name: `data`
5. Inside `data` volume → create folders: `cleaned`, `nltk_data`, `output`

> If your catalog/schema/volume names differ, set env vars in the notebook:
> `LSH_DBX_CATALOG`, `LSH_DBX_SCHEMA`, `LSH_DBX_VOLUME`.

---

## Step 4 — Upload Data to UC Volume

### Option A — UI Upload

- `data/cleaned` → **Upload to this volume** → drag all files from `./data/output/cleaned/`
- `data/nltk_data` → **Upload** → drag `./build/nltk_data/corpora/` (preserve folder structure)

### Option B — Databricks CLI (recommended for many files)

```bash
uv tool install databricks-cli
databricks configure --token   # paste workspace URL + workspace PAT (from User Settings)

databricks fs cp -r ./data/output/cleaned \
    dbfs:/Volumes/workspace/lsh_book_recommendation/data/cleaned --overwrite

databricks fs cp -r ./build/nltk_data \
    dbfs:/Volumes/workspace/lsh_book_recommendation/data/nltk_data --overwrite

# Verify
databricks fs ls dbfs:/Volumes/workspace/lsh_book_recommendation/data/cleaned
```

---

## Refreshing the Dataset

To refetch books grouped by Gutenberg Bookshelves (richer TN1/TN2 ground-truth — books in the same shelf share vocabulary):

```bash
# 1. Run fetcher LOCALLY (Databricks Serverless blocks outbound HTTP)
LSH_ENV=dev uv run python -c "
from scripts.fetch_gutenberg_bookshelf import fetch_bookshelves
fetch_bookshelves(['Detective Fiction', \"Children's Literature\", 'Science Fiction'], 30)
"

# 2. Preprocess locally → parquet
LSH_ENV=dev uv run python -c "from src.preprocessing import run_preprocessing; run_preprocessing()"

# 3. Upload parquet to Volume (replaces the cleaned dataset)
databricks fs cp -r ./data/output/cleaned \
    dbfs:/Volumes/workspace/lsh_book_recommendation/data/cleaned --overwrite
```

The fetcher caches the PG catalog CSV at `./data/pg_catalog.csv` (~20 MB) on first run; subsequent calls reuse it. Re-running `fetch_bookshelf(...)` with the same args is idempotent (already-downloaded `pg<id>.txt` files are skipped).

> **Why bookshelves?** A 100-book random sample yields very few TN1/TN2 ground-truth pairs (J ≥ 0.5). Books from the same shelf (e.g. all detective fiction) share more vocabulary, producing a richer evaluation set.

---

## Step 5 — Link GitHub via Personal Access Token

1. **GitHub** → Settings → Developer settings → **Personal access tokens** → **Fine-grained tokens** → **Generate new token**
   - Resource owner: your account
   - Repository access: select `lsh-book-recommendation`
   - Permissions: **Contents → Read & Write**, **Metadata → Read**
   - Expiration: 90 days
2. **Databricks** → top-right avatar → **Settings** → **Linked accounts** → **Add Git credential**
   - Provider: GitHub
   - Username: your GitHub handle
   - Token: paste PAT
3. Save

---

## Step 6 — Clone Repo as Git Folder

1. Sidebar → **Workspace** → **Repos** (or **Git folders**) → your username folder → **Add → Add repo**
2. URL: `https://github.com/<your-user>/lsh-book-recommendation.git`
3. **Create repo**
4. After clone → click repo → Git icon in toolbar → branch dropdown → switch to `databricks-migration`
5. Clone path: `/Workspace/Repos/<user>/lsh-book-recommendation/`

---

## Step 7 — Open Notebook 04 + Attach Serverless

1. Repos sidebar → `lsh-book-recommendation/notebooks/04_experiments.ipynb`
2. Top-right compute selector → **Serverless** (only option on Free Edition)
3. Wait for green "attached" indicator (~30s)

---

## Step 8 — Run Setup Cell (Smoke Test)

Run **only the first setup cell** of notebook 04. Expected output:

```
Books: 93
Total pairs: 4278
Ground-truth pairs (J >= 0.5): 5
```

**Troubleshooting:**

- `nltk.LookupError` → confirm `NLTK_DATA` env var matches Volume path; rerun setup cell
- `parquet path not found` → list Volume contents:
  ```python
  dbutils.fs.ls("/Volumes/workspace/lsh_book_recommendation/data/cleaned")
  ```

---

## Step 9 — Run All Experiments

Execute cells in order: TN1 → TN1 plots → TN2 → TN2 plots → TN3 → TN3 plots → TN4 → Aggregate.

**TN3 fallback:** If size=1500 OOMs, edit `sizes_tn3 = [200, 500, 1000]` and re-run that cell.

---

## Step 10 — Export Results to Local

```bash
databricks fs cp \
    dbfs:/Volumes/workspace/lsh_book_recommendation/data/output/experiment_results.csv \
    ./reports/experiment_results.csv

# Plot PNGs (if savefig used)
databricks fs cp -r \
    dbfs:/Volumes/workspace/lsh_book_recommendation/data/output/plots \
    ./reports/plots --overwrite
```

Or via UI: Catalog Explorer → file → **Download**.

---

## Architecture Reference

```
Local laptop                      Databricks Free Edition
─────────────                     ──────────────────────
data/output/cleaned/*.parquet  ─► /Volumes/workspace/lsh_book_recommendation/data/cleaned/
build/nltk_data/                ─► /Volumes/workspace/lsh_book_recommendation/data/nltk_data/
github.com/<user>/lsh-...       ─► /Workspace/Repos/<user>/lsh-book-recommendation/
```

---

## Constraints & Notes

- **Serverless-only:** no `--master local[*]`, no `PYSPARK_SUBMIT_ARGS`; `spark` auto-injected
- **2.5h notebook timeout** — TN3 size 1500 is the riskiest cell
- **Outbound internet restricted** → NLTK corpus pre-bundled (Step 2)
- UC Volume path pattern: `/Volumes/<catalog>/<schema>/<volume>/...`

---

## See Also

- Implementation plan: `plans/260428-0843-databricks-migration-experiments/plan.md`
- Free Edition limits: https://docs.databricks.com/aws/en/getting-started/free-edition-limitations
- UC Volumes docs: https://docs.databricks.com/aws/en/volumes/volume-files
- Repos docs: https://docs.databricks.com/aws/en/repos/
