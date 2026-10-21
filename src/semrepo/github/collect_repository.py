"""
WP4.5 -- Build a RepositorySnapshot from the raw GitHub repository API
response.

Deliberately NOT a network call: resolve_repository.py (WP4.4) already
fetches GET /repos/{owner}/{repo} to resolve identity, and that same
response already contains every field a RepositorySnapshot needs
(counts, description, archived, and -- since ontology v2.1 -- pushed_at,
updated_at, license, topics, language, default_branch, owner, subscribers).
Making a second API call here to re-fetch the same data would waste
rate-limit budget for nothing -- so build_repository_snapshot() is a pure
transformation of the dict resolve_repository() already returns.

The one value the repository response does NOT contain is the time of the
last commit. fetch_last_commit_at() gets it with a single extra call
(GET /repos/{owner}/{repo}/commits?per_page=1) and is kept separate so the
pipeline can make that cost explicit and optional.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from semrepo.github.utils import parse_github_datetime
from semrepo.models import RepositorySnapshot

logger = logging.getLogger(__name__)


def _opt_dt(value: Optional[str]) -> Optional[datetime]:
    return parse_github_datetime(value) if value else None


def build_repository_snapshot(data: dict, collected_at: datetime) -> RepositorySnapshot:
    """data is the raw GitHub API response dict for GET /repos/{owner}/{repo}
    (the third element returned by resolve_repository()). collected_at is
    passed in explicitly rather than read from the response, so all
    snapshots produced in one pipeline run share one consistent timestamp
    (collectedAt marks pipeline observation time, not any GitHub-side
    timestamp)."""
    license_info = data.get("license") or {}
    owner = data.get("owner") or {}
    return RepositorySnapshot(
        repository_github_id=data["id"],
        collected_at=collected_at,
        stars_count=data.get("stargazers_count"),
        forks_count=data.get("forks_count"),
        open_issues_count=data.get("open_issues_count"),
        description=data.get("description"),
        archived=data.get("archived"),
        repository_name=data.get("name"),
        full_name=data.get("full_name"),
        default_branch=data.get("default_branch"),
        homepage_url=data.get("homepage") or None,
        is_fork=data.get("fork"),
        pushed_at=_opt_dt(data.get("pushed_at")),
        updated_at=_opt_dt(data.get("updated_at")),
        # NOTE: 'watchers_count' in the API equals the star count; the real
        # watcher number is 'subscribers_count'.
        watchers_count=data.get("subscribers_count"),
        size_kb=data.get("size"),
        license_spdx_id=license_info.get("spdx_id"),
        license_name=license_info.get("name"),
        topics=list(data.get("topics") or []),
        primary_language=data.get("language"),
        owner_github_id=owner.get("id"),
        owner_login=owner.get("login"),
        owner_type=owner.get("type"),
    )


def fetch_last_commit_at(owner: str, repo: str, client) -> Optional[datetime]:
    """One extra API call per repository: timestamp of the newest commit on
    the default branch. Returns None (never raises) if the repository is
    empty (409), not found, or the call fails -- the snapshot simply has no
    lastCommitAt in that case."""
    try:
        response = client.get(f"/repos/{owner}/{repo}/commits?per_page=1")
    except Exception as e:
        logger.warning("Could not fetch last commit for %s/%s: %s", owner, repo, e)
        return None
    if response.status_code != 200:
        return None
    try:
        items = response.json()
    except Exception:
        return None
    if not isinstance(items, list) or not items or not isinstance(items[0], dict):
        return None
    commit = items[0].get("commit") or {}
    date = (commit.get("committer") or {}).get("date") or (commit.get("author") or {}).get("date")
    return _opt_dt(date)
