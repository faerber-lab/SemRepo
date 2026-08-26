"""
WP4.5 -- Collect issues and pull requests for a repository via GitHub's
paginated /issues endpoint.

Reuses the *design* of v1's crawler.py get_issues() -- page-increment
pagination worked correctly there (see docs/wp4-pipeline-audit-findings.md)
-- but wires it to github_client.py's token-rotating client, replaces the
hard-coded max_issues default with a configurable one
(config/default.yaml's collection_limits.max_issues), and adds
CollectionActivity tracking that v1 had none of.

Two GitHub API quirks handled deliberately, not by accident:
- /issues returns both issues AND pull requests in the same list -- an
  item is a pull request if and only if it has a "pull_request" key. That
  maps directly onto our Issue.is_pull_request field.
- The endpoint defaults to state=open only. state=all is requested
  explicitly, or every closed issue would be silently under-collected.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from semrepo.github.github_client import GitHubClient
from semrepo.github.utils import parse_github_datetime
from semrepo.models import CollectionActivity, CollectionStatus, Issue

logger = logging.getLogger(__name__)

PER_PAGE = 100


def _to_issue(item: dict, repository_github_id: int) -> Issue:
    return Issue(
        github_issue_id=item["id"],
        issue_number=item["number"],
        issue_state=item["state"],
        issue_created_at=parse_github_datetime(item["created_at"]),
        belongs_to_repository_github_id=repository_github_id,
        is_pull_request="pull_request" in item,
        issue_closed_at=parse_github_datetime(item["closed_at"]) if item.get("closed_at") else None,
    )


def collect_issues(
    owner: str,
    repo: str,
    repository_github_id: int,
    client: GitHubClient,
    collection_source: str,
    max_issues: Optional[int] = None,
) -> Tuple[List[Issue], CollectionActivity]:
    """max_issues=None means unlimited (matches config/default.yaml's
    default of null). If a limit IS applied and actually cuts the result
    short, that's recorded as PARTIAL_SUCCESS on the returned
    CollectionActivity, never silently -- per Rule 7, any limit must be
    visible in output metadata."""

    attempted_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
    timestamp = datetime.now(timezone.utc)
    issues: List[Issue] = []
    page = 1
    limit_applied = False

    while True:
        try:
            response = client.get(
                f"/repos/{owner}/{repo}/issues?state=all&per_page={PER_PAGE}&page={page}"
            )
        except Exception as e:
            logger.warning("API error collecting issues for %s/%s (page %d): %s", owner, repo, page, e)
            status = CollectionStatus.PARTIAL_SUCCESS if issues else CollectionStatus.FAILED
            return issues, CollectionActivity(
                collection_timestamp=timestamp,
                attempted_url=attempted_url,
                collection_source=collection_source,
                collection_status=status,
                resulted_in_repository_github_id=repository_github_id if issues else None,
            )

        if response.status_code == 404:
            return [], CollectionActivity(
                collection_timestamp=timestamp,
                attempted_url=attempted_url,
                collection_source=collection_source,
                collection_status=CollectionStatus.NOT_FOUND,
                resulted_in_repository_github_id=None,
            )

        if response.status_code != 200:
            logger.warning(
                "Unexpected status %d collecting issues for %s/%s (page %d)",
                response.status_code, owner, repo, page,
            )
            status = CollectionStatus.PARTIAL_SUCCESS if issues else CollectionStatus.FAILED
            return issues, CollectionActivity(
                collection_timestamp=timestamp,
                attempted_url=attempted_url,
                collection_source=collection_source,
                collection_status=status,
                resulted_in_repository_github_id=repository_github_id,
            )

        page_data = response.json()
        if not page_data:
            break  # no more pages

        for item in page_data:
            issues.append(_to_issue(item, repository_github_id))
            if max_issues is not None and len(issues) >= max_issues:
                limit_applied = True
                break

        if limit_applied or len(page_data) < PER_PAGE:
            break  # limit hit, or this was the last (short) page
        page += 1

    return issues, CollectionActivity(
        collection_timestamp=timestamp,
        attempted_url=attempted_url,
        collection_source=collection_source,
        collection_status=CollectionStatus.PARTIAL_SUCCESS if limit_applied else CollectionStatus.SUCCESS,
        resulted_in_repository_github_id=repository_github_id,
    )