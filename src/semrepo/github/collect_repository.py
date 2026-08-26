"""
WP4.5 -- Build a RepositorySnapshot from the raw GitHub repository API
response.

Deliberately NOT a network call: resolve_repository.py (WP4.4) already
fetches GET /repos/{owner}/{repo} to resolve identity, and that same
response already contains every field a RepositorySnapshot needs
(stargazers_count, forks_count, open_issues_count, description, archived).
Making a second API call here to re-fetch the same data would waste
rate-limit budget for nothing -- so this module is a pure transformation of
the dict resolve_repository() already returns, not a new fetch.
"""

from __future__ import annotations

from datetime import datetime

from semrepo.models import RepositorySnapshot


def build_repository_snapshot(data: dict, collected_at: datetime) -> RepositorySnapshot:
    """data is the raw GitHub API response dict for GET /repos/{owner}/{repo}
    (the third element returned by resolve_repository()). collected_at is
    passed in explicitly rather than read from the response, so all
    snapshots produced in one pipeline run share one consistent timestamp
    (matches WP3's snapshot design -- collectedAt marks pipeline observation
    time, not any GitHub-side timestamp)."""
    return RepositorySnapshot(
        repository_github_id=data["id"],
        collected_at=collected_at,
        stars_count=data.get("stargazers_count"),
        forks_count=data.get("forks_count"),
        open_issues_count=data.get("open_issues_count"),
        description=data.get("description"),
        archived=data.get("archived"),
    )