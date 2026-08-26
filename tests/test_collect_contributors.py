"""Tests for src/semrepo/github/collect_contributors.py -- fully offline,
covers pagination, anonymous-contributor skipping, and the 202 quirk."""

from datetime import datetime, timezone

from semrepo.github.collect_contributors import collect_contributors
from semrepo.models import CollectionStatus

SNAPSHOT_TIME = datetime(2026, 8, 26, tzinfo=timezone.utc)


class FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else []

    def json(self):
        return self._json_data


class FakeClient:
    def __init__(self, responses=None, exception=None):
        self._responses = list(responses or [])
        self._exception = exception
        self.requested_paths = []

    def get(self, path):
        self.requested_paths.append(path)
        if self._exception:
            raise self._exception
        return self._responses.pop(0)


def _contributor(id_, login, contributions, anonymous=False):
    item = {"login": login, "contributions": contributions}
    if anonymous:
        item["type"] = "Anonymous"
        item["id"] = None
    else:
        item["id"] = id_
    return item


def test_single_page():
    client = FakeClient(responses=[FakeResponse(200, [
        _contributor(1, "octocat", 42),
        _contributor(2, "hubot", 7),
    ])])

    contributions, activity = collect_contributors("octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler")

    assert len(contributions) == 2
    by_id = {c.contributor_github_user_id: c.commit_count for c in contributions}
    assert by_id == {1: 42, 2: 7}
    assert all(c.repository_github_id == 123 for c in contributions)
    assert activity.collection_status == CollectionStatus.SUCCESS


def test_paginates_across_multiple_pages():
    page1 = FakeResponse(200, [_contributor(i, f"user{i}", 1) for i in range(100)])
    page2 = FakeResponse(200, [_contributor(100, "user100", 1)])
    client = FakeClient(responses=[page1, page2])

    contributions, activity = collect_contributors("octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler")

    assert len(contributions) == 101
    assert len(client.requested_paths) == 2


def test_skips_anonymous_contributors():
    client = FakeClient(responses=[FakeResponse(200, [
        _contributor(1, "octocat", 42),
        _contributor(None, None, 5, anonymous=True),
    ])])

    contributions, activity = collect_contributors("octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler")

    assert len(contributions) == 1
    assert contributions[0].contributor_github_user_id == 1
    assert activity.collection_status == CollectionStatus.SUCCESS


def test_max_contributors_limit_marks_partial():
    page1 = FakeResponse(200, [_contributor(i, f"user{i}", 1) for i in range(100)])
    client = FakeClient(responses=[page1])

    contributions, activity = collect_contributors(
        "octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler", max_contributors=3
    )

    assert len(contributions) == 3
    assert len(client.requested_paths) == 1
    assert activity.collection_status == CollectionStatus.PARTIAL_SUCCESS


def test_202_stats_computing_is_not_treated_as_success():
    client = FakeClient(responses=[FakeResponse(202, {})])

    contributions, activity = collect_contributors("octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler")

    assert contributions == []
    assert activity.collection_status == CollectionStatus.FAILED


def test_not_found():
    client = FakeClient(responses=[FakeResponse(404)])

    contributions, activity = collect_contributors("octocat", "gone", 1, SNAPSHOT_TIME, client, "test-crawler")

    assert contributions == []
    assert activity.collection_status == CollectionStatus.NOT_FOUND


def test_failed_on_client_exception():
    client = FakeClient(exception=ConnectionError("network unreachable"))

    contributions, activity = collect_contributors("octocat", "repo", 1, SNAPSHOT_TIME, client, "test-crawler")

    assert contributions == []
    assert activity.collection_status == CollectionStatus.FAILED