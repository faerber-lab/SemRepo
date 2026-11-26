"""Tests for compute_statistics.py and export_sample.py (evaluation step 9.5)."""

import json

import compute_statistics
from export_sample import export, scrub

TS = "2026-11-18T00:00:00+00:00"
L = "https://linkedpaperswithcode.com/"


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def _paper(n, official=True, area=True):
    return {"lpwc_paper_uri": f"{L}paper/p{n}", "repository_relations": ["hasOfficialRepository" if official else "hasRepository"],
            "soa_work_uri": f"https://semopenalex.org/work/W{n}", "authors": [], "tasks": [f"{L}task/t{n}"],
            "research_areas": [f"{L}area/computer-vision"] if area else []}


def _publish(root):
    """Two collections; repo 1 is renamed, has a bot PR, an author match and a fuzzy match below 0.70."""
    a, b = root / "a", root / "b"
    _write(a / "repositories.jsonl", [{"github_repository_id": 1, "canonical_url": "https://github.com/o/one"},
                                      {"github_repository_id": 2, "canonical_url": "https://github.com/o/two"}])
    _write(b / "repositories.jsonl", [{"github_repository_id": 3, "canonical_url": "https://github.com/o/three"}])
    _write(a / "snapshots.jsonl", [{"repository_github_id": 1, "collected_at": TS, "primary_language": "Python"},
                                   {"repository_github_id": 2, "collected_at": TS, "primary_language": "C++"}])
    _write(b / "snapshots.jsonl", [{"repository_github_id": 3, "collected_at": TS, "primary_language": "Python"}])
    _write(a / "issues.jsonl", [
        {"github_issue_id": 10, "issue_number": 1, "issue_state": "open", "issue_created_at": TS,
         "belongs_to_repository_github_id": 1, "issue_author_github_id": 5, "issue_author_login": "u", "issue_author_type": "User"},
        {"github_issue_id": 11, "issue_number": 2, "issue_state": "open", "issue_created_at": TS, "is_pull_request": True,
         "belongs_to_repository_github_id": 1, "issue_author_github_id": 6, "issue_author_login": "dependabot[bot]",
         "issue_author_type": "Bot"}])
    _write(a / "contributions.jsonl", [{"repository_github_id": 1, "snapshot_collected_at": TS,
                                        "contributor_github_user_id": 7, "contributor_github_login": "alice", "commit_count": 3}])
    # alice's profile was written once, in the other collection
    _write(b / "contributors.jsonl", [{"contributor_github_user_id": 7, "contributor_github_login": "alice",
                                       "contributor_account_type": "User", "email": "alice@example.org",
                                       "bio": "mail me: alice@example.org"}])
    _write(a / "source-repository-links.jsonl", [{"original_repository_url": "https://github.com/old/one",
                                                  "resolution_status": "Renamed", "resolved_repository_github_id": 1}])
    _write(a / "external-links.jsonl", [
        {"github_repository_id": 1, "github_repository_url": "https://github.com/o/one",
         "lpwc_repository_matches": [{"lpwc_repository_uri": f"{L}repository/one", "mlsea_software_uris": ["https://w3id.org/mlsea/s1"],
                                      "papers": [_paper(1), _paper(2, official=False)]}],
         "github_contributor_soa_matches": [
             {"contributor_github_user_id": 7, "soa_author_uri": "https://semopenalex.org/author/A1", "match_type": "ExactNameMatch", "similarity": 1.0},
             {"contributor_github_user_id": 8, "soa_author_uri": "https://semopenalex.org/author/A2", "match_type": "FuzzyNameMatch", "similarity": 0.65}]},
        {"github_repository_id": 2, "lpwc_repository_matches": []}])
    _write(b / "external-links.jsonl", [
        {"github_repository_id": 3, "lpwc_repository_matches": [{"lpwc_repository_uri": f"{L}repository/three",
                                                                 "mlsea_software_uris": [], "papers": [_paper(1)]}]}])
    return root


def test_statistics_count_distinct_entities(tmp_path):
    cols = sorted(p for p in _publish(tmp_path / "p").iterdir())
    link = compute_statistics.linking_statistics(cols)
    assert link["distinct_papers"] == 2                      # p1 is linked from two repositories
    assert link["distinct_papers_with_official_link"] == 1
    assert link["distinct_semopenalex_works"] == 2
    assert link["distinct_mlsea_software"] == 1
    assert link["repositories_with_lpwc_match"] == 2
    assert link["top_research_areas_by_distinct_papers"] == [[f"{L}area/computer-vision", 2]]
    assert link["published_contributor_author_pairs"] == 1  # the 0.65 fuzzy match is not published

    issues = compute_statistics.issue_statistics(cols)
    assert issues["pull_requests"] == 1 and issues["issue_authors_by_account_type"] == {"User": 1, "Bot": 1}
    assert compute_statistics.repository_statistics(cols)["top_primary_languages"][0] == ["Python", 2]


def test_estimated_precision_uses_sample_strata(tmp_path):
    cols = sorted(p for p in _publish(tmp_path / "p").iterdir())
    precision = {"strata": {"ExactNameMatch": {"precision": 1.0}, "Fuzzy 0.60-0.70": {"precision": 0.5}}}
    link = compute_statistics.linking_statistics(cols, precision)
    assert link["estimated_precision_published"] == 1.0
    assert link["estimated_precision_all_from_0.60"] == 0.75


def test_statistics_main_writes_json_and_markdown_with_triples(tmp_path):
    from generate_rdf_with_linking import generate_rdf
    publish = _publish(tmp_path / "p")
    for col in ("a", "b"):
        generate_rdf(publish / col, tmp_path / "rdf" / col)
    compute_statistics.main([str(publish), str(tmp_path / "rdf"), str(tmp_path / "out"), "--triples", "--workers", "2"])
    stats = json.loads((tmp_path / "out" / "statistics.json").read_text())
    assert stats["rdf"]["triples"] > 0
    assert "| distinct_papers | 2 |" in (tmp_path / "out" / "statistics.md").read_text()


def test_scrub_removes_email_fields_and_addresses():
    assert scrub({"email": "a@b.org", "bio": "x a@b.org", "n": [{"email": 1}]}) == {"bio": "x [email removed]", "n": [{}]}


def test_export_sample_is_complete_scrubbed_and_valid(tmp_path):
    report = export(_publish(tmp_path / "p"), tmp_path / "sample")
    by_folder = {r["folder"]: r for r in report}
    assert "o__one" in by_folder and all(r["shacl_conforms"] for r in report)

    one = tmp_path / "sample" / "o__one"
    profiles = [json.loads(l) for l in (one / "jsonl" / "contributors.jsonl").read_text().splitlines()]
    assert [p["contributor_github_login"] for p in profiles] == ["alice"]          # found in the other collection
    assert "email" not in profiles[0] and "@" not in profiles[0]["bio"]
    assert len((one / "jsonl" / "issues.jsonl").read_text().splitlines()) == 2
    assert (one / "rdf" / "semrepo-core.ttl").exists()
    assert "o__one" in (tmp_path / "sample" / "README.md").read_text()


def test_export_ntriples_shows_triples_shared_by_collections(tmp_path):
    """Summing triples per file counts shared triples (e.g. a paper's metadata) once per
    collection; the N-Triples export lets `sort -u` count the distinct triples."""
    from export_ntriples import main as export_nt
    from generate_rdf_with_linking import generate_rdf
    paper = {"lpwc_paper_uri": f"{L}paper/shared", "repository_relations": ["hasOfficialRepository"],
             "title": "A shared paper", "authors": []}
    for col, rid in (("a", 1), ("b", 2)):
        d = tmp_path / "publish" / col
        _write(d / "repositories.jsonl", [{"github_repository_id": rid, "canonical_url": f"https://github.com/o/r{rid}"}])
        _write(d / "external-links.jsonl", [{"github_repository_id": rid, "lpwc_repository_matches": [
            {"lpwc_repository_uri": f"{L}repository/r{rid}", "mlsea_software_uris": [], "papers": [paper]}]}])
        generate_rdf(d, tmp_path / "rdf" / col)

    export_nt([str(tmp_path / "rdf"), str(tmp_path / "nt")])

    lines = [l for f in sorted((tmp_path / "nt").glob("*.nt")) for l in f.read_text().splitlines() if l.strip()]
    summed = json.loads((tmp_path / "nt" / "export-summary.json").read_text())["triples_summed_over_files"]
    assert len(lines) == summed
    assert len(set(lines)) < summed                      # the shared paper's triples appear in both collections
    assert any("A shared paper" in l for l in lines)