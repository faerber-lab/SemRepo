"""Tests for src/semrepo/pipeline.py -- deduplication by GitHub numeric ID
and checkpoint/resume, fully offline via a routing fake client."""

import json

from semrepo.pipeline import run_pipeline


class FakeResponse:
    def __init__(self, status_code, json_data=None, history=None):
        self.status_code = status_code
        self._json_data = json_data if json_data is not None else {}
        self.history = history or []

    def json(self):
        return self._json_data


def _repo_payload(id_, owner, name):
    return {
        "id": id_, "name": name, "owner": {"login": owner},
        "html_url": f"https://github.com/{owner}/{name}",
        "created_at": "2020-01-01T00:00:00Z",
        "stargazers_count": 1, "forks_count": 1, "open_issues_count": 0,
        "description": None, "archived": False,
    }


class RoutingFakeClient:
    """Routes GET calls to canned responses by endpoint type (repo lookup,
    languages, issues, contributors), keyed off the owner/repo in the path.
    repo_payloads maps 'owner/repo' -> repo dict; an unknown key means the
    repository lookup itself returns 404."""

    def __init__(self, repo_payloads: dict):
        self.repo_payloads = repo_payloads
        self.requested_paths = []

    def get(self, path):
        self.requested_paths.append(path)
        parts = path.lstrip("/").split("/")
        owner, repo = parts[1], parts[2].split("?")[0]
        key = f"{owner}/{repo}"

        if "/languages" in path:
            return FakeResponse(200, {})
        if "/issues" in path:
            return FakeResponse(200, [])
        if "/contributors" in path:
            return FakeResponse(200, [])

        if key not in self.repo_payloads:
            return FakeResponse(404)
        return FakeResponse(200, self.repo_payloads[key])


def test_two_distinct_repositories_are_both_collected(tmp_path):
    client = RoutingFakeClient({
        "a/one": _repo_payload(1, "a", "one"),
        "b/two": _repo_payload(2, "b", "two"),
    })

    summary = run_pipeline(
        ["https://github.com/a/one", "https://github.com/b/two"],
        tmp_path, client, "test-source",
    )

    assert summary["resolution_counts"] == {"Resolved": 2}
    repos = (tmp_path / "repositories.jsonl").read_text().strip().split("\n")
    assert len(repos) == 2


def test_two_urls_resolving_to_same_id_are_deduplicated(tmp_path):
    # Both URLs resolve to the SAME repository (id=42) -- simulating two
    # LPWC entries, or a URL recorded before and after a rename.
    same_repo = _repo_payload(42, "same", "repo")
    client = RoutingFakeClient({
        "old-name/repo": same_repo,
        "same/repo": same_repo,
    })

    summary = run_pipeline(
        ["https://github.com/old-name/repo", "https://github.com/same/repo"],
        tmp_path, client, "test-source",
    )

    repos = (tmp_path / "repositories.jsonl").read_text().strip().split("\n")
    assert len(repos) == 1
    assert json.loads(repos[0])["github_repository_id"] == 42

    # Both URLs' resolutions are still recorded -- neither is silently dropped.
    links = (tmp_path / "source-repository-links.jsonl").read_text().strip().split("\n")
    assert len(links) == 2

    assert summary["resolution_counts"]["duplicate_repository"] == 1

    # The duplicate must not trigger a second round of follow-up calls.
    followup_calls = [
        p for p in client.requested_paths
        if "/languages" in p or "/issues" in p or "/contributors" in p
    ]
    assert len(followup_calls) == 3  # exactly one repo's worth


def test_checkpoint_resume_skips_already_processed_urls(tmp_path):
    client = RoutingFakeClient({"a/one": _repo_payload(1, "a", "one")})
    run_pipeline(["https://github.com/a/one"], tmp_path, client, "test-source")

    client2 = RoutingFakeClient({"a/one": _repo_payload(1, "a", "one")})
    summary = run_pipeline(["https://github.com/a/one"], tmp_path, client2, "test-source")

    assert summary["resolution_counts"] == {"skipped_checkpoint": 1}
    assert client2.requested_paths == []  # no API calls at all for the already-processed URL

    repos = (tmp_path / "repositories.jsonl").read_text().strip().split("\n")
    assert len(repos) == 1  # not duplicated by the second run


def test_checkpoint_resume_still_processes_new_urls(tmp_path):
    client = RoutingFakeClient({"a/one": _repo_payload(1, "a", "one")})
    run_pipeline(["https://github.com/a/one"], tmp_path, client, "test-source")

    client2 = RoutingFakeClient({
        "a/one": _repo_payload(1, "a", "one"),
        "b/two": _repo_payload(2, "b", "two"),
    })
    summary = run_pipeline(
        ["https://github.com/a/one", "https://github.com/b/two"],
        tmp_path, client2, "test-source",
    )

    assert summary["resolution_counts"] == {"skipped_checkpoint": 1, "Resolved": 1}
    repos = (tmp_path / "repositories.jsonl").read_text().strip().split("\n")
    assert len(repos) == 2  # the earlier one plus the newly processed one


def test_checkpoint_resume_retries_api_errors_instead_of_skipping_forever(tmp_path):
    """A transient API_ERROR must NOT be permanently skipped on resume --
    only genuinely meaningful outcomes (resolved, invalid, etc.) should be."""

    class AlwaysErrorsClient:
        def get(self, path):
            raise ConnectionError("simulated transient failure")

    first_client = AlwaysErrorsClient()
    summary1 = run_pipeline(["https://github.com/a/one"], tmp_path, first_client, "test-source")
    assert summary1["resolution_counts"] == {"ApiError": 1}

    # Second run, this time the API works -- the URL must be retried, not
    # silently skipped just because it failed once before.
    second_client = RoutingFakeClient({"a/one": _repo_payload(1, "a", "one")})
    summary2 = run_pipeline(["https://github.com/a/one"], tmp_path, second_client, "test-source")

    assert summary2["resolution_counts"] == {"Resolved": 1}
    assert len(second_client.requested_paths) > 0  # a real retry happened, not a checkpoint skip


def test_normalize_and_resolution_failures_do_not_crash(tmp_path):
    client = RoutingFakeClient({})  # nothing resolves

    summary = run_pipeline(
        ["not a github url at all", "https://github.com/does/not-exist"],
        tmp_path, client, "test-source",
    )

    assert summary["resolution_counts"]["normalize_failed"] == 1
    assert summary["resolution_counts"]["Invalid"] == 1
    links = (tmp_path / "source-repository-links.jsonl").read_text().strip().split("\n")
    assert len(links) == 1  # only the resolvable-but-invalid one leaves a trace