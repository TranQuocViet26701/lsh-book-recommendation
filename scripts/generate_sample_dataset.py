"""Generate a stratified 100-book sample dataset from Gutenberg metadata.

Reads gutenberg_metadata.csv, selects ~8 books from each of the top-12
categories (by Bookshelf), downloads them via gutenberg_downloader, and
writes data/sample/sample_metadata.csv.
"""

import logging
import os
import time
import asyncio

import pandas as pd

from scripts.gutenberg_downloader import DEFAULT_DELAY, download_and_save_book

logger = logging.getLogger(__name__)

BOOKS_PER_CATEGORY = 8
TOTAL_BOOKS = 100
DEFAULT_OUTPUT_DIR = "./data/sample"
DEFAULT_CSV_PATH = "./data/gutenberg_metadata.csv"


def extract_gutenberg_id(link: str) -> int:
    """Parse the numeric book ID from a Gutenberg URL like .../ebooks/84."""
    return int(str(link).strip().rstrip("/").split("/")[-1])


def load_metadata(csv_path: str) -> pd.DataFrame:
    """Load metadata CSV, drop rows missing Author or Bookshelf, add GutenbergID."""
    df = pd.read_csv(csv_path)
    df = df.dropna(subset=["Author", "Bookshelf"])
    df["GutenbergID"] = df["Link"].apply(extract_gutenberg_id)
    return df.reset_index(drop=True)


def select_stratified_books(df: pd.DataFrame, n_per_cat: int = BOOKS_PER_CATEGORY) -> pd.DataFrame:
    """Pick top-12 categories, take first *n_per_cat* books each, fill to TOTAL_BOOKS."""
    top_categories = df["Bookshelf"].value_counts().head(12).index.tolist()
    selections: list[pd.DataFrame] = []

    for cat in top_categories:
        subset = df[df["Bookshelf"] == cat].head(n_per_cat)
        selections.append(subset)

    # Preserve original df indices for correct exclusion during fill
    selected_orig = pd.concat(selections)

    # Fill remaining slots from books not yet selected
    if len(selected_orig) < TOTAL_BOOKS:
        remaining = df[~df.index.isin(selected_orig.index)]
        extra = remaining.head(TOTAL_BOOKS - len(selected_orig))
        selected_orig = pd.concat([selected_orig, extra])

    return selected_orig.head(TOTAL_BOOKS).reset_index(drop=True)

async def download_books_async(row: pd.Series, output_dir: str) -> int: 
    book_id = row["GutenbergID"]
    filepath = os.path.join(output_dir, f"pg{book_id}.txt")

    # Resumability: skip already-downloaded files
    if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
        logger.info(f"Skip pg{book_id} (already exists)")
        return 1

    result = await asyncio.to_thread(download_and_save_book, book_id, output_dir)
    if result["success"]:
        logger.info(f"Downloaded pg{book_id} – {row['Title']}")
        return 0
    else:
        logger.warning("Failed pg%d – %s: %s", book_id, row["Title"], result["error"])
        return -1


async def generate_sample(csv_path: str, output_dir: str) -> dict:
    """Main pipeline: load metadata -> select books -> download -> save metadata CSV."""

    if not os.path.exists(csv_path):
        logger.error("Metadata CSV not found at %s", csv_path)
        return {"error": "Metadata CSV not found"}

    logger.info("Loading metadata from %s", csv_path)
    df = load_metadata(csv_path)
    logger.info("Loaded %d books with Author + Bookshelf", len(df))

    selected = select_stratified_books(df)
    logger.info(
        "Selected %d books across %d categories",
        len(selected),
        selected["Bookshelf"].nunique(),
    )

    os.makedirs(output_dir, exist_ok=True)

    tasks = [download_books_async(row, output_dir) for _, row in selected.iterrows()]

    results = await asyncio.gather(*tasks)

    downloaded = len([x for x in results if x == 0])
    failed = len([x for x in results if x == -1])
    skipped = len([x for x in results if x == 1])

    # Save sample metadata CSV
    meta_path = os.path.join(output_dir, "sample_metadata.csv")
    selected[["GutenbergID", "Title", "Author", "Bookshelf", "Link"]].to_csv(meta_path, index=False)
    logger.info("Metadata saved to %s", meta_path)

    summary = {
        "total_selected": len(selected),
        "downloaded": downloaded,
        "skipped": skipped,
        "failed": failed,
        "categories": selected["Bookshelf"].nunique(),
        "metadata_path": meta_path,
    }
    logger.info("Summary: %s", summary)
    return summary


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Generate 100-book sample dataset")
    parser.add_argument("--csv", default=DEFAULT_CSV_PATH, help="Path to gutenberg_metadata.csv. Default: %(default)s")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Output directory. Default: %(default)s")
    args = parser.parse_args()

    asyncio.run(generate_sample(csv_path=args.csv, output_dir=args.output_dir))
