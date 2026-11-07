"""Tests for src/semrepo/github/collect_languages.py -- fully offline via a
fake GitHubClient, same pattern as test_resolve_repository.py."""

from datetime import datetime, timezone

from semrepo.github.collect_languages import collect_languages
from semrepo.models import CollectionStatus


class FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

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


SNAPSHOT_TIME = datetime(2026, 8, 26, tzinfo=timezone.utc)


def test_success_with_multiple_languages():
    client = FakeClient(response=FakeResponse(200, {"Python": 12345, "JavaScript": 6789}))

    usages, activity = collect_languages("octocat", "Hello-World", 123, SNAPSHOT_TIME, client, "test-crawler")

    assert len(usages) == 2
    by_name = {u.language_name: u.language_bytes for u in usages}
    assert by_name == {"Python": 12345, "JavaScript": 6789}
    assert all(u.repository_github_id == 123 for u in usages)
    assert activity.collection_status == CollectionStatus.SUCCESS
    assert activity.collection_source == "test-crawler"
    assert activity.resulted_in_repository_github_id == 123


def test_success_with_empty_repository():
    """A repo with no detectable source code returns {} -- that's a
    legitimate SUCCESS, not an error."""
    client = FakeClient(response=FakeResponse(200, {}))

    usages, activity = collect_languages("octocat", "empty-repo", 999, SNAPSHOT_TIME, client, "test-crawler")

    assert usages == []
    assert activity.collection_status == CollectionStatus.SUCCESS


def test_not_found():
    client = FakeClient(response=FakeResponse(404))

    usages, activity = collect_languages("octocat", "gone", 1, SNAPSHOT_TIME, client, "test-crawler")

    assert usages == []
    assert activity.collection_status == CollectionStatus.NOT_FOUND


def test_failed_on_unexpected_status():
    client = FakeClient(response=FakeResponse(500))

    usages, activity = collect_languages("octocat", "repo", 1, SNAPSHOT_TIME, client, "test-crawler")

    assert usages == []
    assert activity.collection_status == CollectionStatus.FAILED


def test_failed_on_client_exception():
    client = FakeClient(exception=ConnectionError("network unreachable"))

    usages, activity = collect_languages("octocat", "repo", 1, SNAPSHOT_TIME, client, "test-crawler")

    assert usages == []
    assert activity.collection_status == CollectionStatus.FAILED


def test_collection_source_is_never_empty():
    """Mirrors the WP3 SHACL decision: collectionSource is mandatory.
    Enforced by the function signature (required parameter), verified here
    that it always ends up on the resulting CollectionActivity."""
    client = FakeClient(response=FakeResponse(200, {"Python": 100}))

    _, activity = collect_languages("octocat", "repo", 1, SNAPSHOT_TIME, client, "my-source-tag")

    assert activity.collection_source == "my-source-tag"