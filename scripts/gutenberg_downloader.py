"""Download a single Project Gutenberg book by ID.

Tries three URL strategies in order:
1. Primary  – /ebooks/{id}.txt.utf-8
2. Cache    – /cache/epub/{id}/pg{id}.txt
3. Scrape   – parse the book page for a "Plain Text UTF-8" link

Applies text cleaning from scripts.text_cleaning_utils before saving.
"""

import logging
import os
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from scripts.text_cleaning_utils import clean_gutenberg_text

logger = logging.getLogger(__name__)

# URL templates
GUTENBERG_PRIMARY_URL = "https://www.gutenberg.org/ebooks/{book_id}.txt.utf-8"
GUTENBERG_CACHE_URL = "https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"
GUTENBERG_BOOK_PAGE = "https://www.gutenberg.org/ebooks/{book_id}"

REQUEST_TIMEOUT = 30
DEFAULT_DELAY = 1.5  # seconds between requests (polite crawling)
USER_AGENT = "LSH-Book-Recommendation/1.0 (Academic Project; HCMUT)"
MIN_TEXT_LENGTH = 100  # minimum chars to consider a download valid


def fetch_with_retry(url: str, max_retries: int = 3) -> requests.Response | None:
    """GET *url* with exponential back-off.  Returns Response on 200, else None."""
    headers = {"User-Agent": USER_AGENT}
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers=headers)
            if resp.status_code == 200:
                return resp
            logger.warning("Attempt %d: %s returned %d", attempt, url, resp.status_code)
        except requests.RequestException as exc:
            logger.warning("Attempt %d: %s error – %s", attempt, url, exc)
        if attempt < max_retries:
            wait = 2**attempt
            time.sleep(wait)
    return None


def scrape_text_link(book_id: int) -> str | None:
    """Fallback: scrape the Gutenberg book page for a Plain Text UTF-8 link."""
    page = fetch_with_retry(GUTENBERG_BOOK_PAGE.format(book_id=book_id), max_retries=2)
    if page is None:
        return None
    try:
        soup = BeautifulSoup(page.content, "html.parser")
        tag = soup.find("a", string="Plain Text UTF-8")
        if tag and tag.get("href"):
            href = tag["href"]
            if href.startswith("/"):
                return f"https://www.gutenberg.org{href}"
            # Only allow gutenberg.org URLs for security
            if urlparse(href).netloc in ("www.gutenberg.org", "gutenberg.org"):
                return href
    except Exception as exc:  # noqa: BLE001
        logger.warning("Scrape failed for book %d: %s", book_id, exc)
    return None


def download_book_text(book_id: int) -> str | None:
    """Download raw text for *book_id*.  Returns text string or None."""
    # Strategy 1 – primary URL
    resp = fetch_with_retry(GUTENBERG_PRIMARY_URL.format(book_id=book_id))
    if resp and len(resp.text) > MIN_TEXT_LENGTH:
        return resp.text

    # Strategy 2 – cache URL
    resp = fetch_with_retry(GUTENBERG_CACHE_URL.format(book_id=book_id))
    if resp and len(resp.text) > MIN_TEXT_LENGTH:
        return resp.text

    # Strategy 3 – scrape book page for direct link
    link = scrape_text_link(book_id)
    if link:
        resp = fetch_with_retry(link)
        if resp and len(resp.text) > MIN_TEXT_LENGTH:
            return resp.text

    return None


def download_and_save_book(book_id: int, output_dir: str) -> dict:
    """Download, clean, and save a Gutenberg book.

    Returns a result dict: {id, path, success, error}.
    """
    result: dict = {"id": book_id, "path": None, "success": False, "error": None}
    try:
        raw_text = download_book_text(book_id)
        if raw_text is None:
            result["error"] = "All download strategies failed"
            return result

        cleaned = clean_gutenberg_text(raw_text)
        if len(cleaned.strip()) < MIN_TEXT_LENGTH:
            result["error"] = "Cleaned text too short"
            return result

        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"pg{book_id}.txt")
        with open(filepath, "w", encoding="utf-8") as fh:
            fh.write(cleaned)

        result["path"] = filepath
        result["success"] = True
    except Exception as exc:  # noqa: BLE001
        result["error"] = str(exc)
    return result


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Download a single Gutenberg book")
    parser.add_argument("--book-id", type=int, required=True)
    parser.add_argument("--output-dir", default="./data/raw")
    args = parser.parse_args()

    res = download_and_save_book(args.book_id, args.output_dir)
    status = "OK" if res["success"] else f"FAIL ({res['error']})"
    print(f"Book {res['id']}: {status}  {res.get('path', '')}")
