"""
WP4.4 -- Resolve a normalized candidate URL to a canonical GitHub
repository, classifying the outcome using the same ResolutionStatus
vocabulary defined in the v2 ontology (ontologies/semrepo-v2.ttl) and
enforced by its SHACL shapes (sh:in on :resolutionStatus, 7 closed values).

Known limitation, documented rather than silently assumed: GitHub's API
returns a plain 404 for a repository that is deleted, one that never
existed, and one that exists but is private and inaccessible to the
current token -- these three cases are NOT distinguishable from the API
response alone. A 404 is conservatively classified as INVALID here rather
than guessed at as DELETED or PRIVATE. v1 had no resolution tracking at
all (docs/wp4-pipeline-audit-findings.md), so even this conservative
classification is new information, not a regression.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import urlparse

from semrepo.github.github_client import GitHubClient
from semrepo.github.normalize_url import NormalizedUrl, ParseStatus
from semrepo.models import CanonicalRepository, ResolutionStatus, SourceRepositoryLink

logger = logging.getLogger(__name__)


def _extract_owner_repo(normalized_url: str) -> Tuple[str, str]:
    """normalized_url is guaranteed to be https://github.com/{owner}/{repo}
    -- normalize_url.py only ever produces that exact shape for OK results."""
    path = urlparse(normalized_url).path.strip("/")
    owner, repo = path.split("/")[:2]
    return owner, repo


def _parse_github_datetime(value: str) -> datetime:
    """GitHub timestamps look like '2011-01-26T19:01:12Z'. Python's
    datetime.fromisoformat() only accepts the 'Z' suffix from 3.11+; this
    project targets >=3.10 (pyproject.toml), so we normalize it by hand."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def resolve_repository(
    normalized: NormalizedUrl,
    client: GitHubClient,
) -> Tuple[SourceRepositoryLink, Optional[CanonicalRepository]]:
    """Resolves one normalized candidate URL against the live GitHub API.

    Always returns a SourceRepositoryLink. Returns a CanonicalRepository
    too, but only when resolution_status is RESOLVED, RENAMED, or
    TRANSFERRED (i.e. the repository is currently reachable)."""

    if normalized.parse_status != ParseStatus.OK or normalized.normalized_candidate_url is None:
        raise ValueError(
            f"resolve_repository requires a successfully normalized URL, got "
            f"parse_status={normalized.parse_status!r} for {normalized.original_url!r}"
        )

    requested_owner, requested_repo = _extract_owner_repo(normalized.normalized_candidate_url)

    try:
        response = client.get(f"/repos/{requested_owner}/{requested_repo}")
    except Exception as e:
        logger.warning("API error resolving %s: %s", normalized.normalized_candidate_url, e)
        return (
            SourceRepositoryLink(
                original_repository_url=normalized.original_url,
                resolution_status=ResolutionStatus.API_ERROR,
            ),
            None,
        )

    if response.status_code == 404:
        # See module docstring -- deleted / never-existed / private are
        # indistinguishable here and conservatively bucketed as INVALID.
        return (
            SourceRepositoryLink(
                original_repository_url=normalized.original_url,
                resolution_status=ResolutionStatus.INVALID,
            ),
            None,
        )

    if response.status_code != 200:
        logger.warning(
            "Unexpected status %d resolving %s", response.status_code, normalized.normalized_candidate_url
        )
        return (
            SourceRepositoryLink(
                original_repository_url=normalized.original_url,
                resolution_status=ResolutionStatus.API_ERROR,
            ),
            None,
        )

    data = response.json()
    final_owner = data["owner"]["login"]
    final_url = data["html_url"]
    was_redirected = len(response.history) > 0

    if not was_redirected:
        status = ResolutionStatus.RESOLVED
    elif final_owner.lower() != requested_owner.lower():
        status = ResolutionStatus.TRANSFERRED
    else:
        status = ResolutionStatus.RENAMED

    link = SourceRepositoryLink(
        original_repository_url=normalized.original_url,
        resolution_status=status,
        final_resolved_url=final_url,
        resolved_repository_github_id=data["id"],
    )
    canonical = CanonicalRepository(
        github_repository_id=data["id"],
        canonical_url=final_url,
        created_at=_parse_github_datetime(data["created_at"]) if data.get("created_at") else None,
    )
    return link, canonical