"""
WP4.7 -- Core pipeline orchestration: normalize -> resolve -> collect ->
write, for a list of repository URLs, with two things the project
proposal explicitly requires and earlier stages didn't yet provide:

1. Deduplication by GitHub's stable numeric repository ID (WP4.4's
   requirement, and the direct fix for the WP1 finding that v1
   deduplicated by URL string/filename instead -- see
   docs/wp4-pipeline-audit-findings.md). Two different URLs can resolve to
   the same repository (a rename, a redirect, two LPWC entries for the
   same project) -- this is only knowable *after* resolution, never from
   the URL text itself, which is exactly why dedup has to happen here and
   not in normalize_url.py.

2. Checkpoint/resume: this reads whatever output already exists in
   output_dir and skips URLs already processed and repository IDs already
   collected, so an interrupted run can simply be re-started with the same
   URL list rather than needing separate resume bookkeeping.

Both are testable fully offline (see tests/test_pipeline.py) using a fake
client, per WP4.7's "don't make every test depend on the live API"
guidance -- scripts/run_small_example.py is now a thin wrapper around
run_pipeline() for actually hitting the live API.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Set, Tuple

from semrepo.github.collect_contributors import collect_contributors
from semrepo.github.collect_issues import collect_issues
from semrepo.github.collect_languages import collect_languages
from semrepo.github.collect_repository import build_repository_snapshot
from semrepo.github.github_client import GitHubClient
from semrepo.github.normalize_url import ParseStatus, normalize_github_url
from semrepo.github.resolve_repository import resolve_repository
from semrepo.normalization.normalize_metadata import OUTPUT_FILES, write_repository_records

logger = logging.getLogger(__name__)


def _load_checkpoint_state(output_dir: Path) -> Tuple[Set[str], Set[int]]:
    """Rebuilds resume state from whatever output files already exist.
    Returns (already_processed_urls, already_seen_repository_ids); both
    empty on a fresh run (no prior output).

    URLs whose only prior attempt ended in API_ERROR are deliberately NOT
    included in already_processed_urls: that status means the attempt
    failed for a transient reason (rate limit, network blip, a temporary
    5xx), not that the URL is permanently unresolvable. Skipping it
    forever on every future resume would silently and permanently drop a
    repository that a retry might resolve just fine -- exactly the kind
    of silent data loss this project's audit keeps finding in v1 and is
    trying not to repeat. Every other outcome (RESOLVED, RENAMED,
    TRANSFERRED, DELETED, PRIVATE, INVALID) is a real, meaningful result
    and is correctly skipped on resume."""
    processed_urls: Set[str] = set()
    links_path = output_dir / OUTPUT_FILES["source_repository_link"]
    if links_path.exists():
        with open(links_path, encoding="utf-8") as f:
            for line in f:
                record = json.loads(line)
                if record["resolution_status"] != "ApiError":
                    processed_urls.add(record["original_repository_url"])

    seen_ids: Set[int] = set()
    repos_path = output_dir / OUTPUT_FILES["repository"]
    if repos_path.exists():
        with open(repos_path, encoding="utf-8") as f:
            for line in f:
                seen_ids.add(json.loads(line)["github_repository_id"])

    return processed_urls, seen_ids


def run_pipeline(
    urls: List[str],
    output_dir: Path,
    client: GitHubClient,
    collection_source: str,
    max_issues: int = None,
    max_contributors: int = None,
) -> Dict[str, dict]:
    """Runs the full normalize -> resolve -> collect -> write pipeline for
    each URL. Safe to call again with the same (or a superset of the) URL
    list after an interruption -- already-processed URLs and
    already-collected repository IDs are skipped, not redone."""
    processed_urls, seen_repository_ids = _load_checkpoint_state(output_dir)
    resolution_counts: Counter = Counter()
    totals: Counter = Counter()

    for raw_url in urls:
        if raw_url in processed_urls:
            logger.info("Skipping %s -- already processed in a previous run", raw_url)
            resolution_counts["skipped_checkpoint"] += 1
            continue

        normalized = normalize_github_url(raw_url)
        if normalized.parse_status != ParseStatus.OK:
            logger.warning("Skipping %s -- normalization failed: %s", raw_url, normalized.error_reason)
            resolution_counts["normalize_failed"] += 1
            continue

        link, canonical, raw_data = resolve_repository(normalized, client)
        resolution_counts[link.resolution_status.value] += 1

        is_duplicate = canonical is not None and canonical.github_repository_id in seen_repository_ids
        collection_activities: list = []
        issues, contributions, languages, snapshot = [], [], [], None
        canonical_to_write = None

        if is_duplicate:
            logger.info(
                "%s resolves to repository %d, already collected via another URL -- skipping duplicate collection",
                raw_url, canonical.github_repository_id,
            )
            resolution_counts["duplicate_repository"] += 1

        elif canonical is not None and raw_data is not None:
            canonical_to_write = canonical
            seen_repository_ids.add(canonical.github_repository_id)
            owner, repo = raw_data["owner"]["login"], raw_data["name"]
            collected_at = datetime.now(timezone.utc)

            snapshot = build_repository_snapshot(raw_data, collected_at)

            languages, lang_activity = collect_languages(
                owner, repo, canonical.github_repository_id, collected_at, client, collection_source
            )
            collection_activities.append(lang_activity)

            issues, issues_activity = collect_issues(
                owner, repo, canonical.github_repository_id, client, collection_source, max_issues=max_issues
            )
            collection_activities.append(issues_activity)

            contributions, contrib_activity = collect_contributors(
                owner, repo, canonical.github_repository_id, collected_at, client, collection_source,
                max_contributors=max_contributors,
            )
            collection_activities.append(contrib_activity)

            totals["issues"] += len(issues)
            totals["contributions"] += len(contributions)
            totals["languages"] += len(languages)

        write_repository_records(
            output_dir,
            canonical_repository=canonical_to_write,
            snapshot=snapshot,
            source_repository_link=link,
            issues=issues,
            contributions=contributions,
            language_usages=languages,
            collection_activities=collection_activities,
        )
        processed_urls.add(raw_url)

    return {"resolution_counts": dict(resolution_counts), "totals": dict(totals)}