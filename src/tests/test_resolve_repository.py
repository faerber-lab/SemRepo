"""Tests for src/semrepo/github/resolve_repository.py -- exercises every
ResolutionStatus branch using a fake GitHubClient stub, fully offline."""

import pytest

from semrepo.github.normalize_url import NormalizedUrl, ParseStatus
from semrepo.github.resolve_repository import resolve_repository
from semrepo.models import ResolutionStatus


class FakeResponse:
    def __init__(self, status_code, json_data=None, history=None):
        self.status_code = status_code
        self._json_data = json_data or {}
        self.history = history or []

    def json(self):
        return self._json_data


class FakeClient:
    def __init__(self, response=None, exception=None):
        self._response = response
        self._exception = exception
        self.requested_paths = []

    def get(self, path):
        self.requested_paths.append(path)
        if self._exception:
            raise self._exception
        return self._response


def _ok_normalized(url="https://github.com/octocat/Hello-World"):
    return NormalizedUrl(
        original_url="https://github.com/octocat/Hello-World/",
        normalized_candidate_url=url,
        parse_status=ParseStatus.OK,
    )


def test_resolved_when_no_redirect():
    response = FakeResponse(200, json_data={
        "id": 123, "owner": {"login": "octocat"}, "name": "Hello-World",
        "html_url": "https://github.com/octocat/Hello-World",
        "created_at": "2011-01-26T19:01:12Z",
    })
    client = FakeClient(response=response)

    link, canonical, raw_data = resolve_repository(_ok_normalized(), client)

    assert link.resolution_status == ResolutionStatus.RESOLVED
    assert link.resolved_repository_github_id == 123
    assert canonical is not None
    assert canonical.github_repository_id == 123
    assert canonical.created_at.year == 2011
    assert raw_data is not None
    assert raw_data["name"] == "Hello-World"
    assert client.requested_paths == ["/repos/octocat/Hello-World"]


def test_renamed_when_same_owner_different_repo_name():
    response = FakeResponse(200, json_data={
        "id": 123, "owner": {"login": "octocat"}, "name": "Hello-World-Renamed",
        "html_url": "https://github.com/octocat/Hello-World-Renamed",
        "created_at": "2011-01-26T19:01:12Z",
    }, history=["redirect"])
    client = FakeClient(response=response)

    link, canonical, raw_data = resolve_repository(_ok_normalized(), client)

    assert link.resolution_status == ResolutionStatus.RENAMED
    assert canonical is not None


def test_transferred_when_owner_changed():
    response = FakeResponse(200, json_data={
        "id": 123, "owner": {"login": "new-owner"}, "name": "Hello-World",
        "html_url": "https://github.com/new-owner/Hello-World",
        "created_at": "2011-01-26T19:01:12Z",
    }, history=["redirect"])
    client = FakeClient(response=response)

    link, canonical, raw_data = resolve_repository(_ok_normalized(), client)

    assert link.resolution_status == ResolutionStatus.TRANSFERRED
    assert canonical is not None


def test_invalid_on_404():
    client = FakeClient(response=FakeResponse(404))

    link, canonical, raw_data = resolve_repository(_ok_normalized(), client)

    assert link.resolution_status == ResolutionStatus.INVALID
    assert canonical is None
    assert raw_data is None
    assert link.resolved_repository_github_id is None


def test_api_error_on_unexpected_status():
    client = FakeClient(response=FakeResponse(500))

    link, canonical, raw_data = resolve_repository(_ok_normalized(), client)

    assert link.resolution_status == ResolutionStatus.API_ERROR
    assert canonical is None


def test_api_error_on_client_exception():
    client = FakeClient(exception=ConnectionError("network unreachable"))

    link, canonical, raw_data = resolve_repository(_ok_normalized(), client)

    assert link.resolution_status == ResolutionStatus.API_ERROR
    assert canonical is None


def test_rejects_non_ok_normalized_url():
    bad = NormalizedUrl(
        original_url="https://gitlab.com/x/y",
        normalized_candidate_url=None,
        parse_status=ParseStatus.NOT_GITHUB,
        error_reason="not github",
    )
    client = FakeClient(response=FakeResponse(200))

    with pytest.raises(ValueError):
        resolve_repository(bad, client)

    assert client.requested_paths == []  # never even attempted an API call