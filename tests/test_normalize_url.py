"""Tests for src/semrepo/github/normalize_url.py -- covers every case the
project proposal's WP4.3 explicitly lists, plus the reserved-path check
added based on the pipeline audit."""

import pytest

from semrepo.github.normalize_url import ParseStatus, normalize_github_url

EXPECTED = "https://github.com/octocat/Hello-World"


@pytest.mark.parametrize("raw_url", [
    "https://github.com/octocat/Hello-World",
    "http://github.com/octocat/Hello-World",                      # http -> https
    "https://www.github.com/octocat/Hello-World",                 # www stripped
    "https://github.com/octocat/Hello-World/",                    # trailing slash
    "https://github.com/octocat/Hello-World.git",                 # trailing .git
    "https://github.com/octocat/Hello-World?tab=readme-ov-file",  # query string
    "https://github.com/octocat/Hello-World#readme",              # fragment
    "github.com/octocat/Hello-World",                             # missing scheme
    "https://github.com/octocat/Hello-World/issues/42",           # issue subpath
    "https://github.com/octocat/Hello-World/tree/main",           # branch subpath
    "https://github.com/octocat/Hello-World/blob/main/README.md", # file subpath
    "https://github.com/octocat/Hello-World/releases/tag/v1.0",   # release subpath
])
def test_normalizes_to_canonical_form(raw_url):
    result = normalize_github_url(raw_url)
    assert result.parse_status == ParseStatus.OK
    assert result.normalized_candidate_url == EXPECTED
    assert result.error_reason is None
    assert result.original_url == raw_url  # original preserved verbatim


def test_rejects_non_github_host():
    result = normalize_github_url("https://gitlab.com/octocat/Hello-World")
    assert result.parse_status == ParseStatus.NOT_GITHUB
    assert result.normalized_candidate_url is None
    assert result.error_reason is not None


@pytest.mark.parametrize("raw_url,expected_reason_substring", [
    ("", "empty"),
    ("https://github.com/", "no path"),
    ("https://github.com/onlyowner", "fewer than 2 segments"),
    ("https://github.com/inv@lid/repo", "invalid characters"),  # valid host, bad owner chars
])
def test_rejects_malformed_urls(raw_url, expected_reason_substring):
    result = normalize_github_url(raw_url)
    assert result.parse_status == ParseStatus.MALFORMED
    assert result.normalized_candidate_url is None
    assert expected_reason_substring in result.error_reason


@pytest.mark.parametrize("reserved_url", [
    "https://github.com/marketplace/actions/some-action",
    "https://github.com/settings/profile",
    "https://github.com/orgs/some-org/people",
])
def test_rejects_reserved_github_paths(reserved_url):
    result = normalize_github_url(reserved_url)
    assert result.parse_status == ParseStatus.NOT_GITHUB
    assert result.normalized_candidate_url is None
    assert "reserved" in result.error_reason


def test_garbage_input_does_not_crash():
    """Not one of the specific cases above -- just confirms nonsense input
    is rejected gracefully (some non-OK status) rather than raising."""
    result = normalize_github_url("not a url at all $$$")
    assert result.parse_status in (ParseStatus.NOT_GITHUB, ParseStatus.MALFORMED)
    assert result.normalized_candidate_url is None