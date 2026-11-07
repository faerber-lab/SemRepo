"""
WP4.7 -- Small-scale pipeline pilot: run the real pipeline (src/semrepo/
pipeline.py) end to end against a handful of real repositories.

Matches the project proposal's WP4 output checklist item "successful
execution on 10 repositories". Runs unauthenticated by default
(GitHubClient with an empty token list -- see github_client.py), so this
can be run by anyone without a personal access token, at the cost of
GitHub's public 60-requests/hour limit. max_issues/max_contributors are
capped at 20 for this pilot specifically to keep total API usage
predictable regardless of how large any individual repository is.

This script can simply be re-run after an interruption: src/semrepo/
pipeline.py's checkpoint logic skips URLs and repository IDs already
present in output_dir rather than redoing them.
"""

from __future__ import annotations

import logging
from pathlib import Path

from semrepo.github.github_client import GitHubClient
from semrepo.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

COLLECTION_SOURCE = "run_small_example.py (WP4.7 pilot)"
PILOT_LIMIT = 20  # caps issues/contributors per repo -- see module docstring

PILOT_REPOSITORY_URLS = [
    "https://github.com/octocat/Hello-World",
    "https://github.com/octocat/Spoon-Knife",
    "https://github.com/octocat/octocat.github.io",
    "https://github.com/github/gitignore",
    "https://github.com/github/linguist",
    "https://github.com/pallets/flask",
    "https://github.com/psf/requests",
    "https://github.com/sindresorhus/awesome",
    "https://github.com/facebook/create-react-app",
    "https://github.com/torvalds/linux",
]

if __name__ == "__main__":
    output_dir = Path("data/pilot")
    client = GitHubClient(tokens=[])  # unauthenticated -- see github_client.py

    summary = run_pipeline(
        PILOT_REPOSITORY_URLS, output_dir, client, COLLECTION_SOURCE,
        max_issues=PILOT_LIMIT, max_contributors=PILOT_LIMIT,
    )

    print("\n--- Pilot summary ---")
    print("Resolution outcomes:", summary["resolution_counts"])
    print("Records collected:", summary["totals"])
    print(f"Output written to: {output_dir.resolve()}")