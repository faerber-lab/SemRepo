"""Tests for src/run_full_harvest.py -- rate-limit waiting, retry, chunked
resume. Fully offline."""

import json
import pickle

import pytest

from run_full_harvest import GuardedClient, RateLimitGuard, harvest_collection


class Clock:
    def __init__(self):
        self.t = 1_000.0
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        self.slept.append(seconds)
        self.t += seconds


def test_guard_does_not_wait_while_one_token_has_budget():
    clock = Clock()
    budgets = {"a": (0, 2_000.0), "b": (4_000, 2_000.0)}
    guard = RateLimitGuard(["a", "b"], fetch=budgets.__getitem__, sleep=clock.sleep, now=clock.now)
    assert guard.wait_if_exhausted() is False
    assert clock.slept == []


def test_guard_sleeps_until_earliest_reset_when_all_tokens_are_low():
    clock = Clock()
    budgets = {"a": (10, 1_600.0), "b": (50, 1_300.0)}
    guard = RateLimitGuard(["a", "b"], fetch=budgets.__getitem__, sleep=clock.sleep, now=clock.now)
    assert guard.wait_if_exhausted() is True
    assert clock.slept == [pytest.approx(305.0)]   # earliest reset (1300) + 5 s - now (1000)


class Response:
    def __init__(self, status=200, remaining="4000"):
        self.status_code = status
        self.headers = {"X-RateLimit-Remaining": remaining}


class FlakyClient:
    """Raises once (like 'all tokens exhausted'), then works."""

    def __init__(self):
        self.calls = 0

    def get(self, path):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("All tokens exhausted")
        return Response()


def test_guarded_client_waits_and_retries_when_tokens_are_exhausted():
    clock = Clock()
    state = {"remaining": 0}
    guard = RateLimitGuard(["a"], fetch=lambda t: (state["remaining"], 1_060.0), sleep=clock.sleep, now=clock.now)
    client = GuardedClient(FlakyClient(), guard, check_every=10_000)

    response = client.get("/repos/a/b")

    assert response.status_code == 200
    assert len(clock.slept) == 1


def test_guarded_client_reraises_errors_that_are_not_about_the_rate_limit():
    clock = Clock()
    guard = RateLimitGuard(["a"], fetch=lambda t: (4_000, 0.0), sleep=clock.sleep, now=clock.now)
    client = GuardedClient(FlakyClient(), guard, check_every=10_000)
    with pytest.raises(RuntimeError):
        client.get("/repos/a/b")
    assert clock.slept == []


def test_harvest_collection_runs_in_chunks_writes_progress_and_marks_complete(tmp_path, monkeypatch):
    import run_full_harvest
    monkeypatch.setattr(run_full_harvest, "CHUNK_SIZE", 2)
    monkeypatch.setattr(run_full_harvest.RateLimitGuard, "status", lambda self: [(5_000, 0.0)])

    pkl = tmp_path / "1_5.pkl"
    pkl.write_bytes(pickle.dumps([f"https://github.com/a/r{i}" for i in range(5)]))
    calls = []

    def fake_pipeline(urls, out_dir, client, source, **kwargs):
        calls.append((list(urls), kwargs))
        return {"resolution_counts": {"Resolved": len(urls)}, "totals": {"issues": 1}}

    progress = harvest_collection(pkl, tmp_path / "out", ["tok"], max_issues=1000, max_contributors=100,
                                  fetch_last_commit=True, fetch_profiles=True,
                                  client_factory=lambda: object(), pipeline=fake_pipeline)

    assert [len(urls) for urls, _ in calls] == [2, 2, 1]
    assert calls[0][1]["max_issues"] == 1000 and calls[0][1]["max_contributors"] == 100
    assert progress["urls_done"] == 5 and progress["resolution_counts"] == {"Resolved": 5}
    assert (tmp_path / "out" / "1_5" / "_COMPLETE").exists()
    assert json.loads((tmp_path / "out" / "1_5" / "progress.json").read_text())["urls_total"] == 5

    # second call: collection already complete -> pipeline not called again
    calls.clear()
    harvest_collection(pkl, tmp_path / "out", ["tok"], 1000, 100, True, True,
                       client_factory=lambda: object(), pipeline=fake_pipeline)
    assert calls == []