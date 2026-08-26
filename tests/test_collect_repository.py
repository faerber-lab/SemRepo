"""Tests for src/semrepo/github/collect_repository.py -- pure
transformation, no network involved."""

from datetime import datetime, timezone

from semrepo.github.collect_repository import build_repository_snapshot


def test_builds_snapshot_from_full_api_response():
    data = {
        "id": 123,
        "name": "Hello-World",
        "stargazers_count": 42,
        "forks_count": 7,
        "open_issues_count": 3,
        "description": "My first repository",
        "archived": False,
    }
    collected_at = datetime(2026, 8, 26, tzinfo=timezone.utc)

    snapshot = build_repository_snapshot(data, collected_at)

    assert snapshot.repository_github_id == 123
    assert snapshot.collected_at == collected_at
    assert snapshot.stars_count == 42
    assert snapshot.forks_count == 7
    assert snapshot.open_issues_count == 3
    assert snapshot.description == "My first repository"
    assert snapshot.archived is False


def test_missing_optional_fields_become_none():
    # A minimal response missing some optional fields shouldn't crash --
    # SHACL already treats these as optional (see semrepo-v2-shapes.ttl).
    data = {"id": 123}
    collected_at = datetime(2026, 8, 26, tzinfo=timezone.utc)

    snapshot = build_repository_snapshot(data, collected_at)

    assert snapshot.repository_github_id == 123
    assert snapshot.stars_count is None
    assert snapshot.forks_count is None
    assert snapshot.open_issues_count is None
    assert snapshot.description is None
    assert snapshot.archived is None