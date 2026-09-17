"""Tests for src/semrepo/identifiers.py -- the core guarantee is
determinism: same input, same URI, every time, across separate calls."""

from datetime import datetime, timezone

from semrepo.identifiers import (
    collection_activity_uri, contribution_uri, external_link_uri,
    github_account_uri, issue_uri, language_usage_uri,
    programming_language_uri, repository_snapshot_uri, repository_uri,
    source_repository_link_uri,
)

TS = datetime(2026, 9, 8, 12, 0, 0, tzinfo=timezone.utc)
TS2 = datetime(2026, 9, 9, 12, 0, 0, tzinfo=timezone.utc)


def test_repository_uri_is_deterministic_and_id_based():
    assert repository_uri(123) == repository_uri(123)
    assert repository_uri(123) != repository_uri(456)
    assert "123" in repository_uri(123)


def test_github_account_uri_is_deterministic():
    assert github_account_uri(1) == github_account_uri(1)
    assert github_account_uri(1) != github_account_uri(2)


def test_issue_uri_uses_global_id_not_issue_number():
    # Two different issues in different repos could share the same
    # issue_number (per-repo only) but never the same github_issue_id
    # (global) -- the URI must be built from the latter.
    assert issue_uri(9001) != issue_uri(9002)
    assert issue_uri(9001) == issue_uri(9001)


def test_programming_language_uri_normalizes_case_and_whitespace():
    assert programming_language_uri("Python") == programming_language_uri("python")
    assert programming_language_uri("Python") == programming_language_uri(" Python ")
    assert programming_language_uri("Python") != programming_language_uri("JavaScript")


def test_repository_snapshot_uri_varies_with_timestamp():
    uri1 = repository_snapshot_uri(1, TS)
    uri2 = repository_snapshot_uri(1, TS2)
    assert uri1 != uri2
    assert repository_snapshot_uri(1, TS) == uri1  # stable on repeat


def test_contribution_uri_deterministic_and_sensitive_to_each_field():
    base = contribution_uri(1, TS, 100)
    assert contribution_uri(1, TS, 100) == base  # repeat -> identical
    assert contribution_uri(2, TS, 100) != base  # different repo
    assert contribution_uri(1, TS2, 100) != base  # different snapshot
    assert contribution_uri(1, TS, 200) != base  # different contributor


def test_language_usage_uri_deterministic_and_case_insensitive():
    assert language_usage_uri(1, TS, "Python") == language_usage_uri(1, TS, "python")
    assert language_usage_uri(1, TS, "Python") != language_usage_uri(1, TS, "Rust")


def test_source_repository_link_uri_keyed_on_original_url():
    url = "https://github.com/old-name/repo"
    assert source_repository_link_uri(url) == source_repository_link_uri(url)
    assert source_repository_link_uri(url) != source_repository_link_uri(url + "-different")


def test_external_link_uri_deterministic():
    args = ("https://semrepo.org/resource/repository/1", "SemOpenAlex", "https://semopenalex.org/work/1")
    assert external_link_uri(*args) == external_link_uri(*args)


def test_collection_activity_uri_deterministic():
    args = ("https://github.com/a/b", TS, "test-source")
    assert collection_activity_uri(*args) == collection_activity_uri(*args)
    assert collection_activity_uri("https://github.com/a/b", TS, "other-source") != collection_activity_uri(*args)


def test_different_entity_types_never_collide():
    """Sanity check: the path prefix alone guarantees no cross-type
    collisions even if the numeric/hash suffix happened to match."""
    assert repository_uri(1) != github_account_uri(1)
    assert repository_uri(1) != issue_uri(1)