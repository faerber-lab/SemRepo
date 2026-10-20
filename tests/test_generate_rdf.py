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

# ---------------------------------------------------------------------------
# Ontology v2.1 fields
# ---------------------------------------------------------------------------

def _make_v21_input(tmp_path: Path) -> Path:
    input_dir = _make_pilot_input(tmp_path)
    _write_jsonl(input_dir / "snapshots.jsonl", [
        {"repository_github_id": 1, "collected_at": "2026-09-08T00:00:00+00:00",
         "stars_count": 103257, "forks_count": 2, "open_issues_count": 1,
         "description": "test repo", "archived": False,
         "repository_name": "one", "full_name": "a/one", "default_branch": "main",
         "homepage_url": "https://example.org", "is_fork": False,
         "pushed_at": "2026-09-01T12:00:00+00:00", "updated_at": "2026-09-02T12:00:00+00:00",
         "last_commit_at": "2026-08-30T08:00:00+00:00",
         "watchers_count": 9, "size_kb": 108,
         "license_spdx_id": "MIT", "license_name": "MIT License",
         "topics": ["machine-learning", "demo"], "primary_language": "Python",
         "owner_github_id": 7, "owner_login": "a", "owner_type": "Organization"},
    ])
    _write_jsonl(input_dir / "issues.jsonl", [
        {"github_issue_id": 100, "issue_number": 1, "issue_state": "open",
         "issue_created_at": "2026-01-01T00:00:00+00:00", "belongs_to_repository_github_id": 1,
         "is_pull_request": False, "issue_closed_at": None,
         "issue_title": "Bug", "issue_url": "https://github.com/a/one/issues/1",
         "issue_updated_at": "2026-01-05T00:00:00+00:00", "issue_comment_count": 3,
         "issue_labels": ["bug", "help wanted"],
         "issue_author_github_id": 42, "issue_author_login": "test-contributor", "issue_author_type": "User"},
        {"github_issue_id": 101, "issue_number": 2, "issue_state": "closed",
         "issue_created_at": "2026-01-02T00:00:00+00:00", "belongs_to_repository_github_id": 1,
         "is_pull_request": True, "issue_closed_at": "2026-01-03T00:00:00+00:00",
         "pull_request_merged_at": "2026-01-03T00:00:00+00:00",
         "issue_author_github_id": 99, "issue_author_login": "dependabot[bot]", "issue_author_type": "Bot"},
    ])
    _write_jsonl(input_dir / "contributions.jsonl", [
        {"repository_github_id": 1, "snapshot_collected_at": "2026-09-08T00:00:00+00:00",
         "contributor_github_user_id": 42, "contributor_github_login": "test-contributor",
         "commit_count": 5, "contributor_account_type": "User"},
        {"repository_github_id": 1, "snapshot_collected_at": "2026-09-08T00:00:00+00:00",
         "contributor_github_user_id": 99, "contributor_github_login": "dependabot[bot]",
         "commit_count": 2, "contributor_account_type": "Bot"},
    ])
    return input_dir


def _snapshot_node():
    from datetime import datetime
    from rdflib import URIRef
    return URIRef(repository_snapshot_uri(1, datetime.fromisoformat("2026-09-08T00:00:00+00:00")))


def test_counts_are_plain_integers(tmp_path):
    """Reviewer request: 103257, not "103257"^^xsd:nonNegativeInteger."""
    from rdflib import XSD
    input_dir = _make_v21_input(tmp_path)
    output_dir = tmp_path / "output"
    generate_rdf(input_dir, output_dir)

    graph = Graph().parse(output_dir / "semrepo-snapshots.ttl")
    stars = graph.value(_snapshot_node(), SR.starsCount)
    assert stars.datatype == XSD.integer and stars.toPython() == 103257
    text = (output_dir / "semrepo-snapshots.ttl").read_text()
    assert "nonNegativeInteger" not in text
    assert "103257" in text and '"103257"' not in text   # bare Turtle integer


def test_snapshot_v21_fields(tmp_path):
    from rdflib import URIRef
    from semrepo.identifiers import github_account_uri
    input_dir = _make_v21_input(tmp_path)
    output_dir = tmp_path / "output"
    generate_rdf(input_dir, output_dir)

    g = Graph().parse(output_dir / "semrepo-snapshots.ttl")
    snap = _snapshot_node()
    for prop in (SR.pushedAt, SR.updatedAt, SR.lastCommitAt, SR.repositoryName, SR.fullName,
                 SR.defaultBranch, SR.homepageUrl, SR.isFork, SR.watchersCount, SR.sizeKb):
        assert g.value(snap, prop) is not None, prop

    mit = URIRef("https://spdx.org/licenses/MIT")
    assert (snap, SR.hasLicense, mit) in g
    assert (mit, SR.spdxId, Literal("MIT")) in g
    assert len(list(g.objects(snap, SR.hasTopic))) == 2
    assert (snap, SR.primaryLanguage, URIRef(programming_language_uri("Python"))) in g

    owner = URIRef(github_account_uri(7))
    assert (snap, SR.ownerAccount, owner) in g
    assert (owner, RDF.type, SR.GitHubOrganisation) in g


def test_noassertion_license_does_not_get_fake_spdx_iri(tmp_path):
    input_dir = _make_pilot_input(tmp_path)
    _write_jsonl(input_dir / "snapshots.jsonl", [
        {"repository_github_id": 1, "collected_at": "2026-09-08T00:00:00+00:00",
         "license_spdx_id": "NOASSERTION", "license_name": "Other"},
    ])
    output_dir = tmp_path / "output"
    generate_rdf(input_dir, output_dir)
    g = Graph().parse(output_dir / "semrepo-snapshots.ttl")
    lic = g.value(_snapshot_node(), SR.hasLicense)
    assert not str(lic).startswith("https://spdx.org/")


def test_issue_v21_fields_and_account_types(tmp_path):
    from rdflib import URIRef
    from semrepo.identifiers import github_account_uri, issue_uri
    input_dir = _make_v21_input(tmp_path)
    output_dir = tmp_path / "output"
    generate_rdf(input_dir, output_dir)

    g = Graph().parse(output_dir / "semrepo-issues.ttl")
    issue, pr = URIRef(issue_uri(100)), URIRef(issue_uri(101))
    assert (issue, SR.issueTitle, Literal("Bug")) in g
    assert set(g.objects(issue, SR.issueLabel)) == {Literal("bug"), Literal("help wanted")}
    assert g.value(issue, SR.issueCommentCount).toPython() == 3
    assert (issue, SR.issueAuthor, URIRef(github_account_uri(42))) in g
    assert g.value(pr, SR.pullRequestMergedAt) is not None
    assert (URIRef(github_account_uri(99)), RDF.type, SR.GitHubBot) in g

    c = Graph().parse(output_dir / "semrepo-contributions.ttl")
    assert (URIRef(github_account_uri(99)), RDF.type, SR.GitHubBot) in c
    assert (URIRef(github_account_uri(99)), RDF.type, SR.GitHubUser) not in c


def test_v21_output_conforms_to_shapes(tmp_path):
    from semrepo.validate_rdf import validate_generated_rdf
    root = Path(__file__).resolve().parents[1]
    input_dir = _make_v21_input(tmp_path)
    output_dir = tmp_path / "output"
    generate_rdf(input_dir, output_dir)

    conforms, report = validate_generated_rdf(
        sorted(output_dir.glob("*.ttl")),
        root / "ontologies" / "semrepo-v2.ttl",
        root / "ontologies" / "semrepo-v2-shapes.ttl",
    )
    assert conforms, report
