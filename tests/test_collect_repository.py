"""Tests for src/semrepo/github/collect_repository.py -- pure
transformation, no network involved (fetch_last_commit_at uses a fake
client)."""

from datetime import datetime, timezone

from semrepo.github.collect_repository import build_repository_snapshot, fetch_last_commit_at


def test_builds_snapshot_from_full_api_response():
    data = {
        "id": 123,
        "name": "Hello-World",
        "full_name": "octocat/Hello-World",
        "stargazers_count": 42,
        "watchers_count": 42,          # == stars on GitHub; must NOT be used
        "subscribers_count": 9,        # the real watcher count
        "forks_count": 7,
        "open_issues_count": 3,
        "description": "My first repository",
        "archived": False,
        "fork": False,
        "default_branch": "main",
        "homepage": "https://example.org",
        "size": 108,
        "pushed_at": "2026-09-01T12:00:00Z",
        "updated_at": "2026-09-02T12:00:00Z",
        "license": {"key": "mit", "name": "MIT License", "spdx_id": "MIT"},
        "topics": ["machine-learning", "demo"],
        "language": "Python",
        "owner": {"id": 583231, "login": "octocat", "type": "User"},
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
    # v2.1 fields
    assert snapshot.repository_name == "Hello-World"
    assert snapshot.full_name == "octocat/Hello-World"
    assert snapshot.watchers_count == 9
    assert snapshot.is_fork is False
    assert snapshot.default_branch == "main"
    assert snapshot.homepage_url == "https://example.org"
    assert snapshot.size_kb == 108
    assert snapshot.pushed_at == datetime(2026, 9, 1, 12, tzinfo=timezone.utc)
    assert snapshot.updated_at == datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
    assert snapshot.license_spdx_id == "MIT"
    assert snapshot.license_name == "MIT License"
    assert snapshot.topics == ["machine-learning", "demo"]
    assert snapshot.primary_language == "Python"
    assert (snapshot.owner_github_id, snapshot.owner_login, snapshot.owner_type) == (583231, "octocat", "User")
    assert snapshot.last_commit_at is None  # needs the separate call


def test_missing_optional_fields_become_none():
    # A minimal response missing optional fields shouldn't crash --
    # SHACL treats these as optional (see semrepo-v2-shapes.ttl).
    data = {"id": 123, "license": None, "homepage": ""}
    collected_at = datetime(2026, 8, 26, tzinfo=timezone.utc)

    snapshot = build_repository_snapshot(data, collected_at)

    assert snapshot.repository_github_id == 123
    assert snapshot.stars_count is None
    assert snapshot.forks_count is None
    assert snapshot.open_issues_count is None
    assert snapshot.description is None
    assert snapshot.archived is None
    assert snapshot.pushed_at is None
    assert snapshot.license_spdx_id is None
    assert snapshot.homepage_url is None   # empty string from GitHub -> None
    assert snapshot.topics == []
    assert snapshot.owner_github_id is None


class _FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, response=None, exc=None):
        self.response, self.exc, self.calls = response, exc, []

    def get(self, path):
        self.calls.append(path)
        if self.exc:
            raise self.exc
        return self.response


def test_fetch_last_commit_at_reads_committer_date():
    client = _FakeClient(_FakeResponse(200, [
        {"commit": {"committer": {"date": "2026-08-30T08:00:00Z"}, "author": {"date": "2026-08-29T08:00:00Z"}}}
    ]))
    assert fetch_last_commit_at("a", "b", client) == datetime(2026, 8, 30, 8, tzinfo=timezone.utc)
    assert client.calls == ["/repos/a/b/commits?per_page=1"]


def test_fetch_last_commit_at_returns_none_for_empty_repo_or_error():
    assert fetch_last_commit_at("a", "b", _FakeClient(_FakeResponse(409, {"message": "Git Repository is empty."}))) is None
    assert fetch_last_commit_at("a", "b", _FakeClient(_FakeResponse(200, []))) is None
    assert fetch_last_commit_at("a", "b", _FakeClient(exc=RuntimeError("boom"))) is None
