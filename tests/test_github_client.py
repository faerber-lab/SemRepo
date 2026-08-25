"""Tests for src/semrepo/github/github_client.py -- token rotation on
rate-limit responses. Mocks requests.Session.get directly rather than
hitting the live GitHub API, per WP4.7's "don't make every test depend on
the live API" guidance."""

from unittest.mock import MagicMock, patch

import pytest

from semrepo.github.github_client import AllTokensExhaustedError, GitHubClient


def _fake_response(status_code, headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    return resp


def test_returns_successful_response_without_rotating():
    client = GitHubClient(tokens=["token-a"])
    with patch.object(client._session, "get", return_value=_fake_response(200)) as mock_get:
        response = client.get("/repos/octocat/Hello-World")

    assert response.status_code == 200
    assert mock_get.call_count == 1


def test_rotates_to_next_token_on_rate_limit():
    client = GitHubClient(tokens=["token-a", "token-b"])
    rate_limited = _fake_response(403, headers={"X-RateLimit-Remaining": "0"})
    success = _fake_response(200)

    with patch.object(client._session, "get", side_effect=[rate_limited, success]) as mock_get:
        response = client.get("/repos/octocat/Hello-World")

    assert response.status_code == 200
    assert mock_get.call_count == 2
    # second call should have used token-b's Authorization header
    second_call_headers = mock_get.call_args_list[1].kwargs["headers"]
    assert "token-b" in second_call_headers["Authorization"]


def test_raises_when_all_tokens_exhausted():
    client = GitHubClient(tokens=["token-a", "token-b"])
    rate_limited = _fake_response(429)

    with patch.object(client._session, "get", return_value=rate_limited):
        with pytest.raises(AllTokensExhaustedError):
            client.get("/repos/octocat/Hello-World")


def test_requires_at_least_one_token():
    with pytest.raises(ValueError):
        GitHubClient(tokens=[])


def test_from_env_reads_comma_separated_tokens(monkeypatch):
    monkeypatch.setenv("SEMREPO_GITHUB_TOKENS", "tok1, tok2 ,tok3")
    client = GitHubClient.from_env()
    assert client.tokens == ["tok1", "tok2", "tok3"]


def test_from_env_raises_when_unset(monkeypatch):
    monkeypatch.delenv("SEMREPO_GITHUB_TOKENS", raising=False)
    with pytest.raises(ValueError):
        GitHubClient.from_env()