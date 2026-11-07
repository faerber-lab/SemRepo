from __future__ import annotations

import pickle
import logging
from pathlib import Path

from semrepo.github.github_client import GitHubClient
from semrepo.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

COLLECTION_SOURCE = "1_5000.pkl"
PILOT_SIZE = 3 # run on few examples
PILOT_LIMIT = 20 # caps issues/contributors per repo -- see module docstring

def load_repository_urls(pkl_path: Path) -> list[str]:
    with pkl_path.open("rb") as f:
        data = pickle.load(f)
    return data[:PILOT_SIZE]

if __name__ == "__main__":
    input_file = Path("1_5000.pkl") #src-v1\crawling-gitHub-metadata\github_links\1_5000.pkl
    output_dir = Path("data/pilot")

    PILOT_REPOSITORY_URLS = load_repository_urls(input_file)

    logging.info("Loaded %d repository URLs", len(PILOT_REPOSITORY_URLS))

    client = GitHubClient(tokens=[]) # unauthenticated -- see github_client.py

    summary = run_pipeline(
        PILOT_REPOSITORY_URLS,
        output_dir,
        client,
        COLLECTION_SOURCE,
        max_issues=PILOT_LIMIT,
        max_contributors=PILOT_LIMIT,
    )

    print("\n--- Pilot summary ---")
    print("Resolution outcomes:", summary["resolution_counts"])
    print("Records collected:", summary["totals"])
    print(f"Output written to: {output_dir.resolve()}")
