"""Tests for src/semrepo/normalization/normalize_metadata.py."""

import json
from datetime import datetime, timezone

import pytest

from semrepo.models import (
    CanonicalRepository, CollectionActivity, CollectionStatus,
    Contribution, Issue, LanguageUsage, ResolutionStatus,
    RepositorySnapshot, SourceRepositoryLink,
)
from semrepo.normalization.normalize_metadata import (
    to_json_dict, write_jsonl, write_repository_records,
)

TS = datetime(2026, 8, 27, 10, 0, 0, tzinfo=timezone.utc)


def test_to_json_dict_serializes_datetime_as_isoformat():
    repo = CanonicalRepository(github_repository_id=1, canonical_url="https://github.com/a/b", created_at=TS)

    result = to_json_dict(repo)

    assert result["created_at"] == TS.isoformat()
    assert isinstance(result["created_at"], str)


def test_to_json_dict_serializes_enum_as_its_value():
    activity = CollectionActivity(
        collection_timestamp=TS, attempted_url="https://x", collection_source="test",
        collection_status=CollectionStatus.SUCCESS,
    )

    result = to_json_dict(activity)

    assert result["collection_status"] == "Success"
    assert isinstance(result["collection_status"], str)


def test_to_json_dict_keeps_none_fields_visible():
    """A missing value must stay as null, not disappear from the record."""
    snapshot = RepositorySnapshot(repository_github_id=1, collected_at=TS)  # all optional fields left unset

    result = to_json_dict(snapshot)

    assert "stars_count" in result
    assert result["stars_count"] is None
    assert "description" in result
    assert result["description"] is None


def test_to_json_dict_rejects_non_dataclass():
    with pytest.raises(TypeError):
        to_json_dict({"not": "a dataclass"})


def test_write_jsonl_appends_across_multiple_calls(tmp_path):
    output_path = tmp_path / "out.jsonl"
    repo1 = CanonicalRepository(github_repository_id=1, canonical_url="https://github.com/a/b")
    repo2 = CanonicalRepository(github_repository_id=2, canonical_url="https://github.com/c/d")

    count1 = write_jsonl([repo1], output_path)
    count2 = write_jsonl([repo2], output_path)

    assert count1 == 1
    assert count2 == 1
    lines = output_path.read_text().strip().split("\n")
    assert len(lines) == 2
    ids = [json.loads(line)["github_repository_id"] for line in lines]
    assert ids == [1, 2]


def test_write_repository_records_full_success_case(tmp_path):
    repo = CanonicalRepository(github_repository_id=1, canonical_url="https://github.com/a/b")
    snapshot = RepositorySnapshot(repository_github_id=1, collected_at=TS, stars_count=10)
    link = SourceRepositoryLink(original_repository_url="https://github.com/a/b", resolution_status=ResolutionStatus.RESOLVED)
    issues = [Issue(github_issue_id=1, issue_number=1, issue_state="open", issue_created_at=TS, belongs_to_repository_github_id=1)]
    contributions = [Contribution(repository_github_id=1, snapshot_collected_at=TS, contributor_github_user_id=99, commit_count=5)]
    languages = [LanguageUsage(repository_github_id=1, snapshot_collected_at=TS, language_name="Python", language_bytes=100)]

    written = write_repository_records(
        tmp_path,
        canonical_repository=repo,
        snapshot=snapshot,
        source_repository_link=link,
        issues=issues,
        contributions=contributions,
        language_usages=languages,
    )

    assert written == {
        "repository": 1, "snapshot": 1, "source_repository_link": 1,
        "issue": 1, "contribution": 1, "language_usage": 1, "collection_activity": 0,
    }
    assert (tmp_path / "repositories.jsonl").exists()
    assert (tmp_path / "snapshots.jsonl").exists()
    assert (tmp_path / "collection-activities.jsonl").exists() is False  # nothing written -> file never created


def test_write_repository_records_failed_resolution_still_leaves_a_trace(tmp_path):
    """A repository that failed to resolve has no snapshot/issues/etc, but
    its SourceRepositoryLink and CollectionActivity must still be written
    -- this is the whole point of the provenance design (WP1's MLSea
    finding: don't let a failure vanish without a trace)."""
    link = SourceRepositoryLink(original_repository_url="https://github.com/gone/repo", resolution_status=ResolutionStatus.INVALID)
    activity = CollectionActivity(
        collection_timestamp=TS, attempted_url="https://github.com/gone/repo",
        collection_source="test-crawler", collection_status=CollectionStatus.FAILED,
    )

    written = write_repository_records(
        tmp_path,
        source_repository_link=link,
        collection_activities=[activity],
    )

    assert written["source_repository_link"] == 1
    assert written["collection_activity"] == 1
    assert written["repository"] == 0
    assert written["snapshot"] == 0
    assert (tmp_path / "source-repository-links.jsonl").exists()
    assert (tmp_path / "repositories.jsonl").exists() is False