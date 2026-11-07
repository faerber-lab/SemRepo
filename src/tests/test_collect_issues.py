"""Tests for src/semrepo/github/collect_issues.py -- fully offline, covers
pagination across multiple pages and the max_issues limit."""

from semrepo.github.collect_issues import collect_issues
from semrepo.models import CollectionStatus


class FakeResponse:
    def __init__(self, status_code, json_data=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else []

    def json(self):
        return self._json_data


class FakeClient:
    """Returns one response per call, in order -- lets tests simulate
    multi-page pagination by queuing several FakeResponses."""
    def __init__(self, responses=None, exception=None):
        self._responses = list(responses or [])
        self._exception = exception
        self.requested_paths = []

    def get(self, path):
        self.requested_paths.append(path)
        if self._exception:
            raise self._exception
        return self._responses.pop(0)


def _issue_item(number, id_=None, closed=False, is_pr=False):
    item = {
        "id": id_ or (1000 + number),
        "number": number,
        "state": "closed" if closed else "open",
        "created_at": "2026-01-01T00:00:00Z",
        "closed_at": "2026-02-01T00:00:00Z" if closed else None,
    }
    if is_pr:
        item["pull_request"] = {"url": "https://api.github.com/..."}
    return item


def test_single_page_short_of_per_page_stops_immediately():
    client = FakeClient(responses=[FakeResponse(200, [_issue_item(1), _issue_item(2)])])

    issues, activity = collect_issues("octocat", "repo", 123, client, "test-crawler")

    assert len(issues) == 2
    assert client.requested_paths == ["/repos/octocat/repo/issues?state=all&per_page=100&page=1"]
    assert activity.collection_status == CollectionStatus.SUCCESS


def test_paginates_across_multiple_full_pages():
    page1 = FakeResponse(200, [_issue_item(i) for i in range(100)])  # full page -> keep going
    page2 = FakeResponse(200, [_issue_item(100), _issue_item(101)])  # short page -> stop
    client = FakeClient(responses=[page1, page2])

    issues, activity = collect_issues("octocat", "repo", 123, client, "test-crawler")

    assert len(issues) == 102
    assert len(client.requested_paths) == 2
    assert "page=1" in client.requested_paths[0]
    assert "page=2" in client.requested_paths[1]
    assert activity.collection_status == CollectionStatus.SUCCESS


def test_state_all_is_always_requested():
    client = FakeClient(responses=[FakeResponse(200, [])])

    collect_issues("octocat", "repo", 123, client, "test-crawler")

    assert "state=all" in client.requested_paths[0]


def test_distinguishes_pull_requests_from_issues():
    client = FakeClient(responses=[FakeResponse(200, [
        _issue_item(1, is_pr=False),
        _issue_item(2, is_pr=True),
    ])])

    issues, _ = collect_issues("octocat", "repo", 123, client, "test-crawler")

    by_number = {i.issue_number: i.is_pull_request for i in issues}
    assert by_number == {1: False, 2: True}


def test_closed_issue_has_closed_at_set():
    client = FakeClient(responses=[FakeResponse(200, [_issue_item(1, closed=True)])])

    issues, _ = collect_issues("octocat", "repo", 123, client, "test-crawler")

    assert issues[0].issue_state == "closed"
    assert issues[0].issue_closed_at is not None
    assert issues[0].issue_closed_at.year == 2026


def test_open_issue_has_no_closed_at():
    client = FakeClient(responses=[FakeResponse(200, [_issue_item(1, closed=False)])])

    issues, _ = collect_issues("octocat", "repo", 123, client, "test-crawler")

    assert issues[0].issue_closed_at is None


def test_max_issues_limit_stops_early_and_marks_partial():
    page1 = FakeResponse(200, [_issue_item(i) for i in range(100)])
    client = FakeClient(responses=[page1])  # a second page exists but should never be requested

    issues, activity = collect_issues("octocat", "repo", 123, client, "test-crawler", max_issues=5)

    assert len(issues) == 5
    assert len(client.requested_paths) == 1  # stopped before requesting page 2
    assert activity.collection_status == CollectionStatus.PARTIAL_SUCCESS


def test_not_found():
    client = FakeClient(responses=[FakeResponse(404)])

    issues, activity = collect_issues("octocat", "gone", 1, client, "test-crawler")

    assert issues == []
    assert activity.collection_status == CollectionStatus.NOT_FOUND


def test_failed_on_client_exception():
    client = FakeClient(exception=ConnectionError("network unreachable"))

    issues, activity = collect_issues("octocat", "repo", 1, client, "test-crawler")

    assert issues == []
    assert activity.collection_status == CollectionStatus.FAILED