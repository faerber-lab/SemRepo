"""
WP4.7 -- Small-scale pipeline pilot: normalize -> resolve -> collect ->
write, run end to end against a handful of real repositories.

Matches the project proposal's WP4 output checklist item "successful
execution on 10 repositories" and its general instruction not to attempt
the full ~200k-repository crawl before the pilot pipeline passes its
tests (Section 6, "Required Order").

Runs unauthenticated by default (GitHubClient with an empty token list --
see github_client.py), so this can be run by anyone without a personal
access token, at the cost of GitHub's public 60-requests/hour limit.
max_issues/max_contributors are capped at 20 for this pilot specifically
to keep total API usage predictable and well within that budget,
regardless of how large any individual repository is; this also
exercises the configurable-limit / PARTIAL_SUCCESS path for real, since a
few of the repositories below genuinely have far more than 20 issues or
contributors.
"""

from __future__ import annotations

import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from semrepo.github.collect_contributors import collect_contributors
from semrepo.github.collect_issues import collect_issues
from semrepo.github.collect_languages import collect_languages
from semrepo.github.collect_repository import build_repository_snapshot
from semrepo.github.github_client import GitHubClient
from semrepo.github.normalize_url import normalize_github_url
from semrepo.github.resolve_repository import resolve_repository
from semrepo.normalization.normalize_metadata import write_repository_records

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

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


def run_pilot(urls: list[str], output_dir: Path, client: GitHubClient) -> dict:
    resolution_counts: Counter = Counter()
    totals = Counter()

    for raw_url in urls:
        normalized = normalize_github_url(raw_url)
        if normalized.parse_status.value != "ok":
            logger.warning("Skipping %s -- normalization failed: %s", raw_url, normalized.error_reason)
            resolution_counts["normalize_failed"] += 1
            continue

        link, canonical, raw_data = resolve_repository(normalized, client)
        resolution_counts[link.resolution_status.value] += 1

        collection_activities = []
        issues, contributions, languages, snapshot = [], [], [], None

        if canonical is not None and raw_data is not None:
            owner, repo = raw_data["owner"]["login"], raw_data["name"]
            collected_at = datetime.now(timezone.utc)

            snapshot = build_repository_snapshot(raw_data, collected_at)

            languages, lang_activity = collect_languages(
                owner, repo, canonical.github_repository_id, collected_at, client, COLLECTION_SOURCE
            )
            collection_activities.append(lang_activity)

            issues, issues_activity = collect_issues(
                owner, repo, canonical.github_repository_id, client, COLLECTION_SOURCE, max_issues=PILOT_LIMIT
            )
            collection_activities.append(issues_activity)

            contributions, contrib_activity = collect_contributors(
                owner, repo, canonical.github_repository_id, collected_at, client, COLLECTION_SOURCE,
                max_contributors=PILOT_LIMIT,
            )
            collection_activities.append(contrib_activity)

            totals["issues"] += len(issues)
            totals["contributions"] += len(contributions)
            totals["languages"] += len(languages)

        write_repository_records(
            output_dir,
            canonical_repository=canonical,
            snapshot=snapshot,
            source_repository_link=link,
            issues=issues,
            contributions=contributions,
            language_usages=languages,
            collection_activities=collection_activities,
        )

        logger.info(
            "%s -> %s (%d issues, %d contributions, %d languages)",
            raw_url, link.resolution_status.value, len(issues), len(contributions), len(languages),
        )
        time.sleep(0.5)  # polite pacing, not required by our own rate-limit handling

    return {"resolution_counts": dict(resolution_counts), "totals": dict(totals)}


if __name__ == "__main__":
    output_dir = Path("data/pilot")
    client = GitHubClient(tokens=[])  # unauthenticated -- see module docstring

    summary = run_pilot(PILOT_REPOSITORY_URLS, output_dir, client)

    print("\n--- Pilot summary ---")
    print("Resolution outcomes:", summary["resolution_counts"])
    print("Records collected:", summary["totals"])
    print(f"Output written to: {output_dir.resolve()}")