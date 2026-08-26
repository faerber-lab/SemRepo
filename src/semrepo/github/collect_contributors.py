"""
WP4.5 -- Collect contributors (and their commit counts) for a repository
via GitHub's paginated /contributors endpoint.

Same reuse-the-pagination-idea, fix-the-rest approach as collect_issues.py.

Two things handled deliberately:
- Anonymous contributors (commits not attributed to any GitHub account --
  common on older repositories) are skipped, not force-fit into a
  Contribution record: our ontology's Contribution.contributor must be a
  real GitHubAccount (see semrepo-v2-shapes.ttl's sh:or constraint), and an
  anonymous entry has no stable account ID to attach one to. The skipped
  count is logged, not silently dropped without a trace.
- GitHub can return 202 Accepted (not 200) while it computes contributor
  statistics in the background for a repository that hasn't been requested
  before. This is not an error, but this collector does not retry/poll for
  it -- it is reported as FAILED with a clear log message explaining why,
  rather than being silently conflated with a real failure. A future
  revision could add a retry-after-delay path if this turns out to affect
  a meaningful share of repositories in practice.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from semrepo.github.github_client import GitHubClient
from semrepo.models import CollectionActivity, CollectionStatus, Contribution

logger = logging.getLogger(__name__)

PER_PAGE = 100


def collect_contributors(
    owner: str,
    repo: str,
    repository_github_id: int,
    snapshot_collected_at: datetime,
    client: GitHubClient,
    collection_source: str,
    max_contributors: Optional[int] = None,
) -> Tuple[List[Contribution], CollectionActivity]:
    """max_contributors=None means unlimited. A limit that actually cuts
    the result short is recorded as PARTIAL_SUCCESS, per Rule 7."""

    attempted_url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
    timestamp = datetime.now(timezone.utc)
    contributions: List[Contribution] = []
    page = 1
    limit_applied = False
    anonymous_skipped = 0

    while True:
        try:
            response = client.get(
                f"/repos/{owner}/{repo}/contributors?per_page={PER_PAGE}&page={page}"
            )
        except Exception as e:
            logger.warning("API error collecting contributors for %s/%s (page %d): %s", owner, repo, page, e)
            status = CollectionStatus.PARTIAL_SUCCESS if contributions else CollectionStatus.FAILED
            return contributions, CollectionActivity(
                collection_timestamp=timestamp,
                attempted_url=attempted_url,
                collection_source=collection_source,
                collection_status=status,
                resulted_in_repository_github_id=repository_github_id if contributions else None,
            )

        if response.status_code == 404:
            return [], CollectionActivity(
                collection_timestamp=timestamp,
                attempted_url=attempted_url,
                collection_source=collection_source,
                collection_status=CollectionStatus.NOT_FOUND,
                resulted_in_repository_github_id=None,
            )

        if response.status_code == 202:
            # GitHub is still computing contributor stats -- see module
            # docstring. Not retried here; reported plainly as FAILED.
            logger.warning(
                "GitHub is still computing contributor stats for %s/%s (202) -- not retried", owner, repo
            )
            return contributions, CollectionActivity(
                collection_timestamp=timestamp,
                attempted_url=attempted_url,
                collection_source=collection_source,
                collection_status=CollectionStatus.FAILED,
                resulted_in_repository_github_id=repository_github_id,
            )

        if response.status_code != 200:
            logger.warning(
                "Unexpected status %d collecting contributors for %s/%s (page %d)",
                response.status_code, owner, repo, page,
            )
            status = CollectionStatus.PARTIAL_SUCCESS if contributions else CollectionStatus.FAILED
            return contributions, CollectionActivity(
                collection_timestamp=timestamp,
                attempted_url=attempted_url,
                collection_source=collection_source,
                collection_status=status,
                resulted_in_repository_github_id=repository_github_id,
            )

        page_data = response.json()
        if not page_data:
            break

        for item in page_data:
            if item.get("type") == "Anonymous" or item.get("id") is None:
                anonymous_skipped += 1
                continue
            contributions.append(Contribution(
                repository_github_id=repository_github_id,
                snapshot_collected_at=snapshot_collected_at,
                contributor_github_user_id=item["id"],
                commit_count=item["contributions"],
            ))
            if max_contributors is not None and len(contributions) >= max_contributors:
                limit_applied = True
                break

        if limit_applied or len(page_data) < PER_PAGE:
            break
        page += 1

    if anonymous_skipped:
        logger.info(
            "Skipped %d anonymous contributor(s) for %s/%s (no attributable GitHub account)",
            anonymous_skipped, owner, repo,
        )

    return contributions, CollectionActivity(
        collection_timestamp=timestamp,
        attempted_url=attempted_url,
        collection_source=collection_source,
        collection_status=CollectionStatus.PARTIAL_SUCCESS if limit_applied else CollectionStatus.SUCCESS,
        resulted_in_repository_github_id=repository_github_id,
    )