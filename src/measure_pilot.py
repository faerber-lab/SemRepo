"""
Pilot measurement for the full-scale harvest: how many GitHub API calls
and how much time does one repository cost?

Runs the normal pipeline (semrepo.pipeline.run_pipeline) on a small random
sample of URLs from one .pkl collection, with a thin wrapper around the
GitHub client that counts every request by endpoint type. Nothing in the
pipeline itself is changed.

Usage (from the repository root):

    export SEMREPO_GITHUB_TOKENS=ghp_xxx          # one or more, comma-separated
    python3 src/measure_pilot.py src/data/github_urls/1_5000.pkl 20 data/measure/run1

Arguments: <pkl file> <sample size> <output dir> [max_issues] [max_contributors]
Limits default to "none" (= full collection, the realistic worst case).
Output goes to <output dir>/ (JSONL, same as harvest_github_metadata.py)
plus <output dir>/measurement.json with the numbers.
"""

from __future__ import annotations

import json
import logging
import os
import pickle
import random
import sys
import time
from collections import Counter
from pathlib import Path

from semrepo.github.github_client import GitHubClient
from semrepo.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("measure_pilot")

TOTAL_URLS = 200_000        # approx. size of all 40 collections in src/data/github_urls
RATE_PER_TOKEN = 5_000      # GitHub primary limit, requests/hour per user account
RANDOM_SEED = 42            # fixed, so the same sample can be re-drawn


def _endpoint(path: str) -> str:
    p = path.split("?")[0]
    if p.startswith("/users/"):
        return "profile (/users)"
    for key in ("contributors", "issues", "languages", "commits"):
        if f"/{key}" in p:
            return key
    if p.startswith("/repos/") and p.count("/") == 3:
        return "repository"
    return "other"


class CountingClient:
    """Forwards everything to the real client and counts get() calls."""

    def __init__(self, inner):
        self._inner = inner
        self.calls = Counter()
        self.statuses = Counter()

    def get(self, path, *args, **kwargs):
        self.calls[_endpoint(path)] += 1
        response = self._inner.get(path, *args, **kwargs)
        self.statuses[getattr(response, "status_code", "error")] += 1
        return response

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _remaining(client) -> int | None:
    """GET /rate_limit is free (does not count against the limit)."""
    try:
        data = client.get("/rate_limit").json()
        return data["resources"]["core"]["remaining"]
    except Exception:
        return None


def _parse_limit(value: str | None):
    return None if value in (None, "none", "None") else int(value)


def main() -> None:
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    pkl_path, sample_size, output_dir = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    max_issues = _parse_limit(sys.argv[4] if len(sys.argv) > 4 else None)
    max_contributors = _parse_limit(sys.argv[5] if len(sys.argv) > 5 else None)

    tokens = [t.strip() for t in os.environ.get("SEMREPO_GITHUB_TOKENS", "").split(",") if t.strip()]
    if not tokens:
        sys.exit("SEMREPO_GITHUB_TOKENS is not set -- unauthenticated access is limited to 60 requests/hour.")

    with pkl_path.open("rb") as f:
        all_urls = list(pickle.load(f))
    sample = random.Random(RANDOM_SEED).sample(all_urls, min(sample_size, len(all_urls)))
    logger.info("Sampled %d of %d URLs from %s (seed %d)", len(sample), len(all_urls), pkl_path.name, RANDOM_SEED)

    real_client = GitHubClient(tokens=tokens)
    client = CountingClient(real_client)

    remaining_before = _remaining(real_client)
    start = time.monotonic()
    summary = run_pipeline(
        sample, output_dir, client, pkl_path.name,
        max_issues=max_issues, max_contributors=max_contributors,
    )
    elapsed = time.monotonic() - start
    remaining_after = _remaining(real_client)

    total_calls = sum(client.calls.values())
    collected = summary["resolution_counts"].get("Resolved", 0) + summary["resolution_counts"].get("Renamed", 0) \
        + summary["resolution_counts"].get("Transferred", 0) - summary["resolution_counts"].get("duplicate_repository", 0)
    calls_per_url = total_calls / len(sample)
    seconds_per_url = elapsed / len(sample)

    def hours(tokens_n: int) -> float:
        by_rate = TOTAL_URLS * calls_per_url / (RATE_PER_TOKEN * tokens_n)
        by_speed = TOTAL_URLS * seconds_per_url / 3600   # one sequential process
        return round(max(by_rate, by_speed), 1)

    result = {
        "sample": {"pkl": pkl_path.name, "urls": len(sample), "seed": RANDOM_SEED,
                   "max_issues": max_issues, "max_contributors": max_contributors},
        "resolution_counts": summary["resolution_counts"],
        "records": summary["totals"],
        "repositories_collected": collected,
        "api_calls": {"total": total_calls, "by_endpoint": dict(client.calls.most_common())},
        "http_statuses": {str(k): v for k, v in client.statuses.items()},
        "rate_limit_remaining": {"before": remaining_before, "after": remaining_after},
        "elapsed_seconds": round(elapsed, 1),
        "per_url": {"api_calls": round(calls_per_url, 1), "seconds": round(seconds_per_url, 2)},
        "projection_for_200k_urls_hours": {"1_token": hours(1), "3_tokens": hours(3)},
        "note": "Projection = max(rate-limit bound, sequential-speed bound). Profile cache savings grow with "
                "run size, so a 20-URL sample overestimates profile calls per URL.",
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "measurement.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()