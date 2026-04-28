"""Fetch Project Gutenberg books grouped by Bookshelves for LSH experiments.

Notebook-callable. Writes raw .txt to ``config.DATA_RAW_PATH`` as ``pg<id>.txt``
(matches ``src.preprocessing`` regex contract). Run locally; on Databricks
Serverless outbound is blocked — fetcher raises with a CLI upload hint.

NOTE: filename uses underscores (Python import requirement). This is a
documented exception to the repo's kebab-case rule. See plan.md.

Public API:
    load_pg_catalog(force_refresh=False) -> pd.DataFrame
    fetch_bookshelf(shelf_name, max_books=30, ...) -> list[Path]
    fetch_bookshelves(shelf_names, per_shelf_limit=30, ...) -> dict[str, list[Path]]
"""

import gzip
import io
import logging
import os
import time
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from config.settings import config

logger = logging.getLogger(__name__)

CATALOG_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz"
TXT_URL_PRIMARY = "https://www.gutenberg.org/files/{id}/{id}-0.txt"
TXT_URL_FALLBACK = "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt"
USER_AGENT = "lsh-book-recommendation/0.2 (research; contact via repo)"
TIMEOUT_SEC = 30
MIN_BODY_BYTES = 1024


def _in_databricks() -> bool:
    """Detect Databricks Serverless runtime (outbound HTTP is blocked there)."""
    return os.path.exists("/Workspace") and "DATABRICKS_RUNTIME_VERSION" in os.environ


def _raw_dir() -> Path:
    return Path(config.DATA_RAW_PATH)


def _catalog_cache_path() -> Path:
    # Sit catalog next to raw dir: dev -> ./data/pg_catalog.csv,
    # databricks -> /Volumes/<c>/<s>/<v>/pg_catalog.csv
    return _raw_dir().parent / "pg_catalog.csv"


def _http_get(url: str, *, retry: int = 1) -> requests.Response:
    """GET with 1 retry on Timeout/ConnectionError. Raises on Databricks outbound block."""
    headers = {"User-Agent": USER_AGENT}
    last_exc: Optional[Exception] = None
    for attempt in range(retry + 1):
        try:
            return requests.get(url, headers=headers, timeout=TIMEOUT_SEC)
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            if attempt < retry:
                time.sleep(1.0)
                continue
            if _in_databricks():
                raise RuntimeError(
                    "Outbound HTTP failed on Databricks Serverless (expected: "
                    "outbound is restricted). Run this fetcher LOCALLY, then upload:\n\n"
                    f"  databricks fs cp -r ./data/sample/ "
                    f"dbfs:{config.DATA_RAW_PATH} --overwrite\n"
                ) from e
            raise
    # Unreachable; placate type-checkers.
    raise RuntimeError(f"_http_get exhausted retries: {last_exc}")


def load_pg_catalog(force_refresh: bool = False) -> pd.DataFrame:
    """Load the PG catalog CSV. Cache to disk; honor ``force_refresh``.

    Returns DataFrame with columns including:
        Text#, Type, Issued, Title, Language, Authors, Subjects, LoCC, Bookshelves
    """
    cache = _catalog_cache_path()
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists() and not force_refresh:
        return pd.read_csv(cache, dtype=str).fillna("")
    logger.info("Downloading PG catalog -> %s", cache)
    resp = _http_get(CATALOG_URL)
    resp.raise_for_status()
    raw = gzip.decompress(resp.content)
    df = pd.read_csv(io.BytesIO(raw), dtype=str).fillna("")
    df.to_csv(cache, index=False)
    return df


def _download_book_txt(book_id: str) -> Optional[bytes]:
    """Try /files first, fall back to /cache/epub. Return bytes or None on miss."""
    for url_tpl in (TXT_URL_PRIMARY, TXT_URL_FALLBACK):
        url = url_tpl.format(id=book_id)
        try:
            resp = _http_get(url)
        except Exception as e:
            logger.warning("pg%s: %s failed: %s", book_id, url, e)
            continue
        if resp.status_code == 200 and resp.content and len(resp.content) > MIN_BODY_BYTES:
            return resp.content
    return None


def fetch_bookshelf(
    shelf_name: str,
    max_books: int = 30,
    language: str = "en",
    catalog_df: Optional[pd.DataFrame] = None,
    sleep_sec: float = 0.5,
) -> list[Path]:
    """Filter catalog by Bookshelves substring + Language, download up to ``max_books``."""
    df = catalog_df if catalog_df is not None else load_pg_catalog()
    mask = (
        df["Bookshelves"].str.contains(shelf_name, case=False, na=False)
        & df["Language"].str.contains(language, case=False, na=False)
        & (df["Type"] == "Text")
    )
    selected = df.loc[mask].head(max_books)
    raw_dir = _raw_dir()
    raw_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    skipped: list[str] = []
    for book_id in selected["Text#"].tolist():
        target = raw_dir / f"pg{book_id}.txt"
        if target.exists() and target.stat().st_size > MIN_BODY_BYTES:
            saved.append(target)
            continue
        body = _download_book_txt(book_id)
        if body is None:
            skipped.append(book_id)
            continue
        target.write_bytes(body)
        saved.append(target)
        time.sleep(sleep_sec)
    if skipped:
        logger.warning("Shelf=%r skipped %d books: %s", shelf_name, len(skipped), skipped)
    logger.info("Shelf=%r saved %d books to %s", shelf_name, len(saved), raw_dir)
    return saved


def fetch_bookshelves(
    shelf_names: list[str],
    per_shelf_limit: int = 30,
    language: str = "en",
) -> dict[str, list[Path]]:
    """Multi-shelf entrypoint. Returns ``{shelf_name: [saved Paths]}``."""
    catalog = load_pg_catalog()
    return {
        name: fetch_bookshelf(
            name,
            max_books=per_shelf_limit,
            language=language,
            catalog_df=catalog,
        )
        for name in shelf_names
    }
