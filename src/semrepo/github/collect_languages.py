"""
WP4.5 -- Collect per-language byte counts for a repository via the GitHub
API's dedicated /languages endpoint.

v1 scraped percentage values from repository HTML pages instead (see
docs/wp4-pipeline-audit-findings.md, Finding 5) -- fragile to GitHub UI
changes and only ever gave lossy percentages. This uses the stable,
API-based byte-count endpoint instead, matching the v2 ontology's
languageBytes design (raw byte count, not a precomputed percentage).

Every call produces a CollectionActivity record documenting what happened,
per the proposal's WP4.5 completeness-tracking requirement and the WP1
finding that v1 had no way to trace which pipeline run produced which data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Tuple

from semrepo.github.github_client import GitHubClient
from semrepo.models import CollectionActivity, CollectionStatus, LanguageUsage

logger = logging.getLogger(__name__)


def collect_languages(
    owner: str,
    repo: str,
    repository_github_id: int,
    snapshot_collected_at: datetime,
    client: GitHubClient,
    collection_source: str,
) -> Tuple[List[LanguageUsage], CollectionActivity]:
    """Fetches GET /repos/{owner}/{repo}/languages and returns one
    LanguageUsage per language, plus a CollectionActivity describing the
    attempt. Always returns both -- the LanguageUsage list is empty (not
    None) on failure, and also legitimately empty for a real repository
    with no detectable source code (that's still SUCCESS, not an error;
    /languages doesn't paginate, so there's no partial-result case here)."""

    attempted_url = f"https://api.github.com/repos/{owner}/{repo}/languages"
    timestamp = datetime.now(timezone.utc)

    try:
        response = client.get(f"/repos/{owner}/{repo}/languages")
    except Exception as e:
        logger.warning("API error collecting languages for %s/%s: %s", owner, repo, e)
        activity = CollectionActivity(
            collection_timestamp=timestamp,
            attempted_url=attempted_url,
            collection_source=collection_source,
            collection_status=CollectionStatus.FAILED,
            resulted_in_repository_github_id=None,
        )
        return [], activity

    if response.status_code == 404:
        activity = CollectionActivity(
            collection_timestamp=timestamp,
            attempted_url=attempted_url,
            collection_source=collection_source,
            collection_status=CollectionStatus.NOT_FOUND,
            resulted_in_repository_github_id=None,
        )
        return [], activity

    if response.status_code != 200:
        logger.warning(
            "Unexpected status %d collecting languages for %s/%s", response.status_code, owner, repo
        )
        activity = CollectionActivity(
            collection_timestamp=timestamp,
            attempted_url=attempted_url,
            collection_source=collection_source,
            collection_status=CollectionStatus.FAILED,
            resulted_in_repository_github_id=repository_github_id,
        )
        return [], activity

    data = response.json()  # e.g. {"Python": 12345, "JavaScript": 6789}
    usages = [
        LanguageUsage(
            repository_github_id=repository_github_id,
            snapshot_collected_at=snapshot_collected_at,
            language_name=language_name,
            language_bytes=byte_count,
        )
        for language_name, byte_count in data.items()
    ]

    activity = CollectionActivity(
        collection_timestamp=timestamp,
        attempted_url=attempted_url,
        collection_source=collection_source,
        collection_status=CollectionStatus.SUCCESS,
        resulted_in_repository_github_id=repository_github_id,
    )
    return usages, activity