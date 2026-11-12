"""Tests for src/semrepo/github/collect_contributors.py -- fully offline,
covers pagination, anonymous-contributor skipping, the 202 quirk, account
profile collection, and the per-account profile cache."""

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
    """Serves the queued responses to /contributors calls in order, and a
    canned profile to every /users/{login} call."""

    def __init__(self, responses=None, exception=None, profile_status=200):
        self._responses = list(responses or [])
        self._exception = exception
        self._profile_status = profile_status
        self.requested_paths = []

    def get(self, path):
        self.requested_paths.append(path)
        if self._exception:
            raise self._exception
        if path.startswith("/users/"):
            login = path.split("/")[2]
            return FakeResponse(self._profile_status, {
                "login": login, "type": "User", "name": f"Name of {login}",
                "location": "Berlin", "followers": 3, "created_at": "2015-01-01T00:00:00Z",
            })
        return self._responses.pop(0)

    def contributor_list_calls(self):
        return [p for p in self.requested_paths if "/contributors" in p]

    def profile_calls(self):
        return [p for p in self.requested_paths if p.startswith("/users/")]


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

    contributions, contributors, activity = collect_contributors("octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler")

    assert len(contributions) == 2
    by_id = {c.contributor_github_user_id: c.commit_count for c in contributions}
    assert by_id == {1: 42, 2: 7}
    assert all(c.repository_github_id == 123 for c in contributions)
    assert activity.collection_status == CollectionStatus.SUCCESS


def test_paginates_across_multiple_pages():
    page1 = FakeResponse(200, [_contributor(i, f"user{i}", 1) for i in range(100)])
    page2 = FakeResponse(200, [_contributor(100, "user100", 1)])
    client = FakeClient(responses=[page1, page2])

    contributions, contributors, activity = collect_contributors("octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler")

    assert len(contributions) == 101
    assert len(client.contributor_list_calls()) == 2


def test_skips_anonymous_contributors():
    client = FakeClient(responses=[FakeResponse(200, [
        _contributor(1, "octocat", 42),
        _contributor(None, None, 5, anonymous=True),
    ])])

    contributions, contributors, activity = collect_contributors("octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler")

    assert len(contributions) == 1
    assert contributions[0].contributor_github_user_id == 1
    assert activity.collection_status == CollectionStatus.SUCCESS


def test_max_contributors_limit_marks_partial():
    page1 = FakeResponse(200, [_contributor(i, f"user{i}", 1) for i in range(100)])
    client = FakeClient(responses=[page1])

    contributions, contributors, activity = collect_contributors(
        "octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler", max_contributors=3
    )

    assert len(contributions) == 3
    assert len(client.contributor_list_calls()) == 1
    assert len(client.profile_calls()) == 3  # profiles only for the kept contributors
    assert activity.collection_status == CollectionStatus.PARTIAL_SUCCESS


def test_202_stats_computing_is_not_treated_as_success():
    client = FakeClient(responses=[FakeResponse(202, {})])

    contributions, contributors, activity = collect_contributors("octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler")

    assert contributions == []
    assert activity.collection_status == CollectionStatus.FAILED


def test_not_found():
    client = FakeClient(responses=[FakeResponse(404)])

    contributions, contributors, activity = collect_contributors("octocat", "gone", 1, SNAPSHOT_TIME, client, "test-crawler")

    assert contributions == []
    assert activity.collection_status == CollectionStatus.NOT_FOUND


def test_failed_on_client_exception():
    client = FakeClient(exception=ConnectionError("network unreachable"))

    contributions, contributors, activity = collect_contributors("octocat", "repo", 1, SNAPSHOT_TIME, client, "test-crawler")

    assert contributions == []
    assert activity.collection_status == CollectionStatus.FAILED

# ---------------------------------------------------------------------------
# Account profiles (GET /users/{login})
# ---------------------------------------------------------------------------

def test_collects_one_profile_per_contributor():
    client = FakeClient(responses=[FakeResponse(200, [
        _contributor(1, "octocat", 42),
        _contributor(2, "hubot", 7),
    ])])

    contributions, contributors, activity = collect_contributors(
        "octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler"
    )

    assert [c.contributor_github_login for c in contributors] == ["octocat", "hubot"]
    assert contributors[0].name == "Name of octocat"
    assert contributors[0].github_created_at == datetime(2015, 1, 1, tzinfo=timezone.utc)
    assert client.profile_calls() == ["/users/octocat", "/users/hubot"]


def test_known_profiles_are_not_fetched_again():
    """Accounts contributing to several repositories must cost one
    profile call in total, not one per repository."""
    known = {1}
    client = FakeClient(responses=[FakeResponse(200, [
        _contributor(1, "octocat", 42),   # already known
        _contributor(2, "hubot", 7),      # new
    ])])

    contributions, contributors, activity = collect_contributors(
        "octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler", known_profile_ids=known
    )

    assert len(contributions) == 2                    # contributions are still recorded
    assert [c.contributor_github_user_id for c in contributors] == [2]
    assert client.profile_calls() == ["/users/hubot"]
    assert known == {1, 2}                            # the shared set is updated in place


def test_fetch_profiles_false_makes_no_profile_calls():
    client = FakeClient(responses=[FakeResponse(200, [_contributor(1, "octocat", 42)])])

    contributions, contributors, activity = collect_contributors(
        "octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler", fetch_profiles=False
    )

    assert len(contributions) == 1
    assert contributors == []
    assert client.profile_calls() == []


def test_failed_profile_lookup_keeps_the_contribution():
    client = FakeClient(responses=[FakeResponse(200, [_contributor(1, "octocat", 42)])], profile_status=404)

    contributions, contributors, activity = collect_contributors(
        "octocat", "repo", 123, SNAPSHOT_TIME, client, "test-crawler"
    )

    assert len(contributions) == 1
    assert contributors == []
    assert activity.collection_status == CollectionStatus.SUCCESS


def test_error_paths_return_three_values():
    """Every failure path must return (contributions, contributors, activity):
    the pipeline unpacks three values, and a 2-tuple there crashes the run
    (e.g. GitHub's 403 for repositories with too many contributors)."""
    for response in (FakeResponse(403), FakeResponse(404), FakeResponse(202, {})):
        result = collect_contributors("o", "r", 1, SNAPSHOT_TIME, FakeClient(responses=[response]), "t")
        assert len(result) == 3
    result = collect_contributors("o", "r", 1, SNAPSHOT_TIME, FakeClient(exception=ConnectionError("x")), "t")
    assert len(result) == 3