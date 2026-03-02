"""CLI entry point: download Gutenberg books and optionally upload to HDFS.

Usage examples:
    # Download 100 books locally
    uv run python -m scripts.download_and_upload_gutenberg --num-books 100

    # Download and upload to HDFS (cluster)
    uv run python -m scripts.download_and_upload_gutenberg --num-books 500 --hdfs-dir /gutenberg
"""

import argparse
import logging
import os
import sys
import time

import pandas as pd

from scripts.generate_sample_dataset import extract_gutenberg_id
from scripts.gutenberg_downloader import DEFAULT_DELAY, download_and_save_book
from scripts.hdfs_uploader import ensure_hdfs_directory, upload_file_to_hdfs

logger = logging.getLogger(__name__)

DEFAULT_CSV = "data/gutenberg_metadata.csv"
DEFAULT_OUTPUT_DIR = "./data/raw"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Project Gutenberg books and optionally upload to HDFS",
    )
    parser.add_argument("--csv", default=DEFAULT_CSV, help="Path to metadata CSV")
    parser.add_argument("--num-books", type=int, default=None, help="Number of books")
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR, help="Local output directory")
    parser.add_argument("--hdfs-dir", default=None, help="If set, upload to HDFS after download")
    parser.add_argument("--start-row", type=int, default=0, help="Starting row in CSV")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="Delay between requests")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    # Load metadata
    if not os.path.exists(args.csv):
        logger.error("CSV not found: %s", args.csv)
        logger.error("Download gutenberg_metadata.csv and place it at data/gutenberg_metadata.csv")
        sys.exit(1)

    df = pd.read_csv(args.csv)
    df = df.iloc[args.start_row:]
    if args.num_books is not None:
        df = df.head(args.num_books)

    end_row = args.start_row + len(df) - 1
    logger.info("Processing %d books (rows %d–%d)", len(df), args.start_row, end_row)

    # Prepare HDFS if needed
    if args.hdfs_dir:
        if not ensure_hdfs_directory(args.hdfs_dir):
            logger.error("Cannot create HDFS directory %s — aborting", args.hdfs_dir)
            sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    success_count = 0
    fail_count = 0

    for _, row in df.iterrows():
        book_id = extract_gutenberg_id(row["Link"])

        result = download_and_save_book(book_id, args.output_dir)
        if result["success"]:
            success_count += 1
            logger.info("OK  pg%d – %s", book_id, row.get("Title", "?"))

            # Optional HDFS upload
            if args.hdfs_dir and result["path"]:
                upload_file_to_hdfs(result["path"], args.hdfs_dir)
        else:
            fail_count += 1
            logger.warning("FAIL pg%d – %s", book_id, result["error"])

        time.sleep(args.delay)

    logger.info("Done. Success: %d  Failed: %d  Total: %d", success_count, fail_count, len(df))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
