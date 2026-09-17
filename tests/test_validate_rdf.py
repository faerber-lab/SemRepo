"""Tests for src/semrepo/validate_rdf.py -- confirms it correctly passes
valid pipeline output and correctly fails intentionally broken output,
against the real ontology and shapes files."""

from pathlib import Path

import pytest

from semrepo.generate_rdf import generate_rdf
from semrepo.validate_rdf import validate_generated_rdf

ONTOLOGY_PATH = Path("ontologies/semrepo-v2.ttl")
SHAPES_PATH = Path("ontologies/semrepo-v2-shapes.ttl")

pytestmark = pytest.mark.skipif(
    not ONTOLOGY_PATH.exists() or not SHAPES_PATH.exists(),
    reason="requires ontologies/ to be present (run from repo root)",
)


def _write_jsonl(path: Path, records: list) -> None:
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _valid_pilot_input(input_dir: Path) -> None:
    _write_jsonl(input_dir / "repositories.jsonl", [
        {"github_repository_id": 1, "canonical_url": "https://github.com/a/one", "created_at": "2020-01-01T00:00:00+00:00"},
    ])
    _write_jsonl(input_dir / "snapshots.jsonl", [
        {"repository_github_id": 1, "collected_at": "2026-09-08T00:00:00+00:00",
         "stars_count": 1, "forks_count": 0, "open_issues_count": 0,
         "description": "test", "archived": False},
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
    ])
    _write_jsonl(input_dir / "contributions.jsonl", [
        {"repository_github_id": 1, "snapshot_collected_at": "2026-09-08T00:00:00+00:00",
         "contributor_github_user_id": 42, "contributor_github_login": "someone", "commit_count": 5},
    ])
    _write_jsonl(input_dir / "language-usage.jsonl", [
        {"repository_github_id": 1, "snapshot_collected_at": "2026-09-08T00:00:00+00:00",
         "language_name": "Python", "language_bytes": 1000},
    ])


def test_valid_pipeline_output_conforms(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    _valid_pilot_input(input_dir)
    generate_rdf(input_dir, output_dir)

    conforms, report = validate_generated_rdf(
        sorted(output_dir.glob("*.ttl")), ONTOLOGY_PATH, SHAPES_PATH
    )
    assert conforms, report


def test_missing_mandatory_field_is_caught(tmp_path):
    """Regression guard for the exact real bug this module caught during
    development: a Contribution missing contributor_github_login must
    fail SHACL, not silently pass."""
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    _valid_pilot_input(input_dir)
    generate_rdf(input_dir, output_dir)

    # Corrupt the generated contributions file: drop the githubLogin triple.
    contrib_path = output_dir / "semrepo-contributions.ttl"
    from rdflib import Graph, Namespace
    SR = Namespace("https://semrepo.org/ontology/v2#")
    g = Graph().parse(contrib_path)
    for triple in list(g.triples((None, SR.githubLogin, None))):
        g.remove(triple)
    g.serialize(destination=contrib_path, format="turtle")

    conforms, report = validate_generated_rdf(
        sorted(output_dir.glob("*.ttl")), ONTOLOGY_PATH, SHAPES_PATH
    )
    assert not conforms
    assert "githubLogin" in report