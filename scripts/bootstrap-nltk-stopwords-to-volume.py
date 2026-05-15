"""Download NLTK stopwords corpus into ./build/nltk_data/ for upload to UC Volume.

Databricks Serverless restricts outbound internet, so `nltk.download()` at
runtime will fail. This helper downloads the corpus locally with the canonical
folder layout (`corpora/stopwords/`), ready to upload to a UC Volume.

Usage (run locally before Phase 03 upload):
    uv run python scripts/bootstrap-nltk-stopwords-to-volume.py

Then upload ./build/nltk_data/ to /Volumes/<catalog>/<schema>/<volume>/nltk_data/:
    databricks fs cp -r ./build/nltk_data \
        dbfs:/Volumes/<catalog>/<schema>/<volume>/nltk_data --overwrite
"""

import os

import nltk


def main() -> None:
    out = os.path.abspath("./build/nltk_data")
    os.makedirs(out, exist_ok=True)
    nltk.download("stopwords", download_dir=out, quiet=False)
    print(f"\nStopwords corpus written to: {out}")
    print(
        "Next: databricks fs cp -r ./build/nltk_data "
        "dbfs:/Volumes/<catalog>/<schema>/<volume>/nltk_data --overwrite"
    )


if __name__ == "__main__":
    main()
