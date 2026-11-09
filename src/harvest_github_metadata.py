
from __future__ import annotations

import sys
import pickle
import logging
from pathlib import Path

from semrepo.github.github_client import GitHubClient
from semrepo.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

PILOT_SIZE = 2  # Run on a few examples; set to None to process all repositories
PILOT_LIMIT = 10  # Caps issues/contributors per repository


def load_repository_urls(pkl_path: Path) -> list[str]:
    with pkl_path.open("rb") as f:
        data = pickle.load(f)
    return data[:PILOT_SIZE] if PILOT_SIZE else data


if __name__ == "__main__":
    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/github_urls")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/out-jsonl")

    pkl_files = sorted(input_dir.glob("*.pkl"))
    if not pkl_files:
        logging.warning("No .pkl files found in %s", input_dir.resolve())
        sys.exit(0)

    logging.info("Found %d .pkl files", len(pkl_files))

    client = GitHubClient(tokens=[])  # Unauthenticated

    for input_file in pkl_files:
        collection_source = input_file.name
        logging.info("Processing collection: %s", collection_source)

        repository_urls = load_repository_urls(input_file)
        logging.info("Loaded %d repository URLs", len(repository_urls))

        if not repository_urls:
            logging.warning("No repository URLs found in %s; skipping", input_file.name)
            continue

        collection_output_dir = output_dir / input_file.stem

        summary = run_pipeline(
            repository_urls,
            collection_output_dir,
            client,
            collection_source,
            max_issues=PILOT_LIMIT,
            max_contributors=PILOT_LIMIT,
        )

        logging.info("Completed collection: %s", collection_source)
        logging.info("Resolution outcomes: %s", summary["resolution_counts"])
        logging.info("Records collected: %s", summary["totals"])
        logging.info("Output written to: %s", collection_output_dir.resolve())

    logging.info("All collections processed.")


# Expected folder structure
# Input:
# data/github_urls/
# ├── 1_5000.pkl
# ├── 5001_10000.pkl
# ├── 10001_15000.pkl
# └── 15001_20000.pkl

# Output:
# data/out-jsonl/
# ├── 1_5000/
# ├── 5001_10000/
# ├── 10001_15000/
# └── 15001_20000/

# python harvest_github_metadata.py data/github_urls/ data/out-test

# 2026-11-07 15:19:22,134 INFO Found 1 .pkl files
# 2026-11-07 15:19:22,135 INFO Processing collection: 1_5000.pkl
# 2026-11-07 15:19:22,141 INFO Loaded 2 repository URLs
# 2026-11-07 15:19:26,113 INFO Completed collection: 1_5000.pkl
# 2026-11-07 15:19:26,113 INFO Resolution outcomes: {'Resolved': 2}
# 2026-11-07 15:19:26,113 INFO Records collected: {'issues': 10, 'contributions': 8, 'languages': 1}
# 2026-11-07 15:19:26,114 INFO Output written to: /home/yunisusan/semrepo-pipeline/data/out-test/1_5000
# 2026-11-07 15:19:26,114 INFO All collections processed.