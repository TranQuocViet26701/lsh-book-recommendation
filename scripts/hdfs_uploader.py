"""Upload local text files to HDFS with retry and exponential back-off.

Wraps ``hdfs dfs`` CLI commands via subprocess.  Only useful in a cluster
environment where the ``hdfs`` binary is on PATH.
"""

import glob
import logging
import os
import subprocess
import time

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_HDFS_BASE = "/project-lsh/datasets/gutenberg_default/raw/"


def ensure_hdfs_directory(hdfs_path: str) -> bool:
    """Create *hdfs_path* (and parents) if it does not exist.  Returns success."""
    try:
        result = subprocess.run(
            ["hdfs", "dfs", "-mkdir", "-p", hdfs_path],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 or "File exists" in result.stderr:
            return True
        logger.error("mkdir failed for %s: %s", hdfs_path, result.stderr.strip())
    except FileNotFoundError:
        logger.error("hdfs CLI not found on PATH — are you on the cluster?")
    return False


def upload_file_to_hdfs(
    local_path: str,
    hdfs_dir: str,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> bool:
    """Upload a single file to HDFS with exponential back-off.  Returns success."""
    for attempt in range(1, max_retries + 1):
        try:
            result = subprocess.run(
                ["hdfs", "dfs", "-put", "-f", local_path, hdfs_dir],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                logger.info("Uploaded %s -> %s", local_path, hdfs_dir)
                return True
            logger.warning(
                "Attempt %d/%d failed for %s: %s",
                attempt,
                max_retries,
                local_path,
                result.stderr.strip(),
            )
        except FileNotFoundError:
            logger.error("hdfs CLI not found on PATH")
            return False
        if attempt < max_retries:
            time.sleep(2**attempt)
    logger.error("Failed to upload %s after %d attempts", local_path, max_retries)
    return False


def upload_directory_to_hdfs(
    local_dir: str,
    hdfs_dir: str,
    pattern: str = "*.txt",
    cleanup: bool = False,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> dict:
    """Upload all files matching *pattern* in *local_dir* to *hdfs_dir*.

    Returns ``{"uploaded": [...], "failed": [...], "total": N}``.
    """
    if not ensure_hdfs_directory(hdfs_dir):
        return {"uploaded": [], "failed": [], "total": 0}

    files = sorted(glob.glob(os.path.join(local_dir, pattern)))
    uploaded: list[str] = []
    failed: list[str] = []

    for filepath in files:
        ok = upload_file_to_hdfs(filepath, hdfs_dir, max_retries=max_retries)
        if ok:
            uploaded.append(filepath)
            if cleanup:
                os.remove(filepath)
        else:
            failed.append(filepath)

    logger.info(
        "Upload complete: %d/%d succeeded, %d failed",
        len(uploaded),
        len(files),
        len(failed),
    )
    return {"uploaded": uploaded, "failed": failed, "total": len(files)}


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(description="Upload files to HDFS")
    parser.add_argument("--local-dir", required=True, help="Local directory with files")
    parser.add_argument("--hdfs-dir", default=DEFAULT_HDFS_BASE, help="Target HDFS path")
    parser.add_argument("--cleanup", action="store_true", help="Remove local files after upload")
    args = parser.parse_args()

    summary = upload_directory_to_hdfs(args.local_dir, args.hdfs_dir, cleanup=args.cleanup)
    print(f"Uploaded: {len(summary['uploaded'])}  Failed: {len(summary['failed'])}")
