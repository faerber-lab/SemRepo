"""Tests for src/semrepo/generate_rdf.py."""

import json
from pathlib import Path

from rdflib import RDF, Graph, Literal

from semrepo.generate_rdf import SR, generate_rdf
from semrepo.identifiers import (
    programming_language_uri, repository_snapshot_uri, repository_uri,
)


def _write_jsonl(path: Path, records: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _make_pilot_input(tmp_path: Path) -> Path:
    input_dir = tmp_path / "input"

    _write_jsonl(input_dir / "repositories.jsonl", [
        {"github_repository_id": 1, "canonical_url": "https://github.com/a/one", "created_at": "2020-01-01T00:00:00+00:00"},
    ])
    _write_jsonl(input_dir / "snapshots.jsonl", [
        {"repository_github_id": 1, "collected_at": "2026-09-08T00:00:00+00:00",
         "stars_count": 10, "forks_count": 2, "open_issues_count": 1,
         "description": "test repo", "archived": False},
    ])
    _write_jsonl(input_dir / "source-repository-links.jsonl", [
        {"original_repository_url": "https://github.com/a/one", "resolution_status": "Resolved",
         "final_resolved_url": "https://github.com/a/one", "resolved_repository_github_id": 1},
    ])
    _write_jsonl(input_dir / "collection-activities.jsonl", [
        {"collection_timestamp": "2026-09-08T00:00:00+00:00", "attempted_url": "https://github.com/a/one",
         "collection_source": "test", "collection_status": "Success", "resulted_in_repository_github_id": 1},
    ])
    _write_jsonl(input_dir / "issues.jsonl", [
        {"github_issue_id": 100, "issue_number": 1, "issue_state": "open",
         "issue_created_at": "2026-01-01T00:00:00+00:00", "belongs_to_repository_github_id": 1,
         "is_pull_request": False, "issue_closed_at": None},
        {"github_issue_id": 101, "issue_number": 2, "issue_state": "closed",
         "issue_created_at": "2026-01-02T00:00:00+00:00", "belongs_to_repository_github_id": 1,
         "is_pull_request": True, "issue_closed_at": "2026-01-03T00:00:00+00:00"},
    ])
    _write_jsonl(input_dir / "contributions.jsonl", [
        {"repository_github_id": 1, "snapshot_collected_at": "2026-09-08T00:00:00+00:00",
         "contributor_github_user_id": 42, "contributor_github_login": "test-contributor", "commit_count": 5},
    ])
    _write_jsonl(input_dir / "language-usage.jsonl", [
        {"repository_github_id": 1, "snapshot_collected_at": "2026-09-08T00:00:00+00:00",
         "language_name": "Python", "language_bytes": 1000},
    ])
    return input_dir


def test_generate_rdf_produces_five_files_with_correct_counts(tmp_path):
    input_dir = _make_pilot_input(tmp_path)
    output_dir = tmp_path / "output"

    counts = generate_rdf(input_dir, output_dir)

    assert counts["repositories"] == 1
    assert counts["snapshots"] == 1
    assert counts["issues"] == 2
    assert counts["contributions"] == 1
    assert counts["language_usage"] == 1

    for filename in ["semrepo-core.ttl", "semrepo-snapshots.ttl", "semrepo-issues.ttl",
                      "semrepo-contributions.ttl", "semrepo-languages.ttl"]:
        assert (output_dir / filename).exists()


def test_snapshot_links_to_repository_both_directions(tmp_path):
    input_dir = _make_pilot_input(tmp_path)
    output_dir = tmp_path / "output"
    generate_rdf(input_dir, output_dir)

    core = Graph().parse(output_dir / "semrepo-core.ttl")
    snapshots = Graph().parse(output_dir / "semrepo-snapshots.ttl")
    combined = core + snapshots

    from datetime import datetime
    from rdflib import URIRef
    repo = URIRef(repository_uri(1))
    snap = URIRef(repository_snapshot_uri(1, datetime.fromisoformat("2026-09-08T00:00:00+00:00")))

    assert (repo, SR.hasSnapshot, snap) in combined
    assert (snap, SR.snapshotOf, repo) in combined


def test_issue_vs_pull_request_typing(tmp_path):
    input_dir = _make_pilot_input(tmp_path)
    output_dir = tmp_path / "output"
    generate_rdf(input_dir, output_dir)

    from rdflib import URIRef
    from semrepo.identifiers import issue_uri
    graph = Graph().parse(output_dir / "semrepo-issues.ttl")

    assert (URIRef(issue_uri(100)), RDF.type, SR.Issue) in graph
    assert (URIRef(issue_uri(101)), RDF.type, SR.PullRequest) in graph
    assert (URIRef(issue_uri(101)), RDF.type, SR.Issue) not in graph  # not double-typed


def test_resolution_status_maps_to_correct_individual(tmp_path):
    input_dir = _make_pilot_input(tmp_path)
    output_dir = tmp_path / "output"
    generate_rdf(input_dir, output_dir)

    from rdflib import URIRef
    from semrepo.identifiers import source_repository_link_uri
    graph = Graph().parse(output_dir / "semrepo-core.ttl")

    link_uri = URIRef(source_repository_link_uri("https://github.com/a/one"))
    assert (link_uri, SR.resolutionStatus, SR.Resolved) in graph


def test_same_language_name_reuses_one_programming_language_node(tmp_path):
    """Two different repositories both using Python must point at the
    SAME ProgrammingLanguage URI, not two separate nodes."""
    input_dir = tmp_path / "input"
    _write_jsonl(input_dir / "language-usage.jsonl", [
        {"repository_github_id": 1, "snapshot_collected_at": "2026-09-08T00:00:00+00:00",
         "language_name": "Python", "language_bytes": 1000},
        {"repository_github_id": 2, "snapshot_collected_at": "2026-09-08T00:00:00+00:00",
         "language_name": "python", "language_bytes": 500},  # different casing, same language
    ])
    for name in ["repositories", "snapshots", "source-repository-links", "collection-activities", "issues", "contributions"]:
        _write_jsonl(input_dir / f"{name}.jsonl", [])

    output_dir = tmp_path / "output"
    generate_rdf(input_dir, output_dir)

    graph = Graph().parse(output_dir / "semrepo-languages.ttl")
    lang_nodes = set(graph.subjects(RDF.type, SR.ProgrammingLanguage))
    assert len(lang_nodes) == 1  # deduplicated despite casing difference


def test_contribution_types_contributor_as_githubuser_and_documents_it(tmp_path):
    input_dir = _make_pilot_input(tmp_path)
    output_dir = tmp_path / "output"
    generate_rdf(input_dir, output_dir)

    from rdflib import URIRef
    from semrepo.identifiers import github_account_uri
    graph = Graph().parse(output_dir / "semrepo-contributions.ttl")

    account = URIRef(github_account_uri(42))
    assert (account, RDF.type, SR.GitHubUser) in graph
    assert (account, SR.githubUserId, None) in graph
    assert (account, SR.githubLogin, Literal("test-contributor")) in graph


def test_missing_input_files_produce_empty_but_valid_output(tmp_path):
    """No repositories.jsonl etc. at all -- should not crash, just
    produce empty (but valid, parseable) graphs."""
    input_dir = tmp_path / "empty-input"
    input_dir.mkdir()
    output_dir = tmp_path / "output"

    counts = generate_rdf(input_dir, output_dir)

    assert all(v == 0 for v in counts.values())
    for filename in ["semrepo-core.ttl", "semrepo-snapshots.ttl"]:
        Graph().parse(output_dir / filename)  # must not raise