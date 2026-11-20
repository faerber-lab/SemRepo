"""Tests for prepare_publication.py and the publication-related parts of
generate_rdf_with_linking.py (PR split, e-mail masking)."""

import json

from rdflib import RDF, XSD, Graph, Literal, URIRef

XSD_STRING = XSD.string

from generate_rdf_with_linking import SR, generate_rdf, mask_emails
from prepare_publication import prepare

TS = "2026-11-18T00:00:00+00:00"


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def _collection(root, name, repo_ids, url_prefix, complete=True):
    d = root / name
    _write(d / "repositories.jsonl", [{"github_repository_id": i, "canonical_url": f"https://github.com/o/r{i}"} for i in repo_ids])
    _write(d / "snapshots.jsonl", [{"repository_github_id": i, "collected_at": TS} for i in repo_ids])
    _write(d / "issues.jsonl", [{"github_issue_id": i * 10, "issue_number": 1, "issue_state": "open",
                                 "issue_created_at": TS, "belongs_to_repository_github_id": i} for i in repo_ids])
    _write(d / "contributions.jsonl", [{"repository_github_id": i, "snapshot_collected_at": TS,
                                        "contributor_github_user_id": 7, "contributor_github_login": "alice",
                                        "commit_count": 1} for i in repo_ids])
    _write(d / "contributors.jsonl", [{"contributor_github_user_id": 7, "contributor_github_login": "alice",
                                       "email": "alice@example.org"}])
    _write(d / "language-usage.jsonl", [])
    _write(d / "source-repository-links.jsonl", [{"original_repository_url": f"{url_prefix}{i}",
                                                  "resolution_status": "Resolved", "resolved_repository_github_id": i}
                                                 for i in repo_ids])
    _write(d / "collection-activities.jsonl", [{"attempted_url": f"https://api.github.com/repos/o/r{i}/issues",
                                                "collection_timestamp": TS, "collection_source": name,
                                                "collection_status": "PartialSuccess",
                                                "resulted_in_repository_github_id": i} for i in repo_ids])
    _write(d / "external-links.jsonl", [{"github_repository_id": i, "lpwc_repository_matches": []} for i in repo_ids])
    if complete:
        (d / "_COMPLETE").write_text("x")


def _lines(path):
    return [json.loads(l) for l in path.read_text().splitlines()]


def test_duplicates_are_kept_once_and_provenance_is_preserved(tmp_path):
    harvest, publish = tmp_path / "h", tmp_path / "p"
    _collection(harvest, "a", [1, 2], "https://github.com/x/r")
    _collection(harvest, "b", [2, 3], "https://github.com/y/r")      # repo 2 again, via another URL
    _collection(harvest, "c", [4], "https://github.com/z/r", complete=False)

    summary = prepare(harvest, publish)

    assert summary["unique_repositories"] == 3 and summary["collections_skipped_incomplete"] == ["c"]
    assert [r["github_repository_id"] for r in _lines(publish / "b" / "repositories.jsonl")] == [3]
    assert [r["github_issue_id"] for r in _lines(publish / "b" / "issues.jsonl")] == [30]
    assert len(_lines(publish / "b" / "source-repository-links.jsonl")) == 2   # both URLs of b kept
    assert len(_lines(publish / "b" / "contributors.jsonl")) == 0             # alice already written in a
    assert summary["totals"]["repositories_dropped"] == 1
    assert summary["capped_repositories_partial_success"] == {"issues": 3}


def test_mask_emails():
    assert mask_emails("Contact: jane.doe@uni-x.de or @jane") == "Contact: [email removed] or @jane"
    assert mask_emails("no email here") == "no email here"


def test_rdf_splits_pull_requests_and_masks_bio_emails(tmp_path):
    d = tmp_path / "in"
    _write(d / "issues.jsonl", [
        {"github_issue_id": 1, "issue_number": 1, "issue_state": "open", "issue_created_at": TS,
         "belongs_to_repository_github_id": 9},
        {"github_issue_id": 2, "issue_number": 2, "issue_state": "closed", "issue_created_at": TS,
         "belongs_to_repository_github_id": 9, "is_pull_request": True},
    ])
    _write(d / "contributors.jsonl", [{"contributor_github_user_id": 7, "contributor_github_login": "alice",
                                       "contributor_account_type": "User", "email": "alice@example.org",
                                       "bio": "PhD student, mail me: alice@example.org", "blog": "alice@example.org"}])
    out = tmp_path / "out"
    counts = generate_rdf(d, out)

    issues, prs = Graph().parse(out / "semrepo-issues.ttl"), Graph().parse(out / "semrepo-pullrequests.ttl")
    assert len(set(issues.subjects(RDF.type, SR.Issue))) == 1 and len(set(issues.subjects(RDF.type, SR.PullRequest))) == 0
    assert len(set(prs.subjects(RDF.type, SR.PullRequest))) == 1
    assert counts["pull_requests"] == 1

    text = (out / "semrepo-contributions.ttl").read_text()
    assert "alice@example.org" not in text
    assert "[email removed]" in text

def test_rdf_adds_semopenalex_work_links_evidence_and_paper_metadata(tmp_path):
    from pathlib import Path
    from semrepo.validate_rdf import validate_generated_rdf
    L = "https://linkedpaperswithcode.com/"
    d = tmp_path / "in"
    _write(d / "repositories.jsonl", [{"github_repository_id": 1, "canonical_url": "https://github.com/o/r1"}])
    _write(d / "external-links.jsonl", [{
        "github_repository_id": 1,
        "lpwc_repository_matches": [{
            "lpwc_repository_uri": f"{L}repository/github.com/o/r1",
            "papers": [{
                "lpwc_paper_uri": f"{L}paper/p1", "title": "A paper", "date": "2020-06-11",
                "repository_relations": ["hasOfficialRepository"],
                "soa_work_uri": "https://semopenalex.org/work/W1",
                "paper_mentions_repo": True, "repo_mentions_paper": False,
                "tasks": [f"{L}task/object-detection"], "research_areas": [f"{L}area/computer-vision"],
                "authors": [],
            }],
            "mlsea_software_uris": [],
        }],
    }])
    out = tmp_path / "out"
    counts = generate_rdf(d, out)
    g = Graph().parse(out / "semrepo-external-links.ttl")

    soa_links = [l for l in g.subjects(SR.targetKnowledgeGraph, Literal("SemOpenAlex", datatype=XSD_STRING))]
    assert len(soa_links) == 1
    assert (soa_links[0], SR.linkingMethod, Literal("lpwc-paper-owl-sameAs", datatype=XSD_STRING)) in g

    paper_link = next(l for l in g.subjects(SR.linkRelationType, Literal("official implementation of", datatype=XSD_STRING))
                      if str(g.value(l, SR.linkTarget)).endswith("/paper/p1"))
    assert g.value(paper_link, SR.paperMentionsRepository).toPython() is True
    assert g.value(paper_link, SR.repositoryMentionsPaper).toPython() is False

    paper = URIRef(f"{L}paper/p1")
    assert str(g.value(paper, URIRef("http://purl.org/dc/terms/date"))) == "2020-06-11"
    assert (paper, URIRef("http://dbpedia.org/property/area"), URIRef(f"{L}area/computer-vision")) in g
    assert counts["lpwc_paper_metadata"] == 1

    root = Path(__file__).resolve().parents[2]
    ok, report = validate_generated_rdf(sorted(out.glob("*.ttl")), root / "ontologies/semrepo-v2.ttl",
                                        root / "ontologies/semrepo-v2-shapes.ttl")
    assert ok, report


def test_language_spellings_are_unified_across_collections(tmp_path):
    harvest, publish = tmp_path / "h", tmp_path / "p"
    _collection(harvest, "a", [1, 2], "https://github.com/x/r")
    _collection(harvest, "b", [3], "https://github.com/y/r")
    _write(harvest / "a" / "snapshots.jsonl", [{"repository_github_id": 1, "collected_at": TS, "primary_language": "MATLAB"},
                                               {"repository_github_id": 2, "collected_at": TS, "primary_language": "MATLAB"}])
    _write(harvest / "b" / "language-usage.jsonl", [{"repository_github_id": 3, "snapshot_collected_at": TS,
                                                     "language_name": "Matlab", "language_bytes": 10}])

    summary = prepare(harvest, publish)

    assert _lines(publish / "b" / "language-usage.jsonl")[0]["language_name"] == "MATLAB"
    assert summary["language_names_unified"] == {"matlab": {"canonical": "MATLAB", "variants": {"MATLAB": 2, "Matlab": 1}}}


def test_evidence_flags_from_two_lpwc_repositories_are_merged(tmp_path):
    from pathlib import Path
    from semrepo.validate_rdf import validate_generated_rdf
    L = "https://linkedpaperswithcode.com/"

    def match(repo, paper_mentions, repo_mentions):
        return {"lpwc_repository_uri": f"{L}repository/github.com/o/{repo}", "mlsea_software_uris": [],
                "papers": [{"lpwc_paper_uri": f"{L}paper/p1", "repository_relations": ["hasOfficialRepository"],
                            "paper_mentions_repo": paper_mentions, "repo_mentions_paper": repo_mentions,
                            "authors": []}]}

    d = tmp_path / "in"
    _write(d / "repositories.jsonl", [{"github_repository_id": 1, "canonical_url": "https://github.com/o/new"}])
    # renamed repository: current and original URL are two LPWC repository nodes with different flags
    _write(d / "external-links.jsonl", [{"github_repository_id": 1,
                                         "lpwc_repository_matches": [match("new", False, False), match("old", True, False)]}])
    out = tmp_path / "out"
    generate_rdf(d, out)
    g = Graph().parse(out / "semrepo-external-links.ttl")

    link = next(l for l in g.subjects(SR.linkRelationType, Literal("official implementation of", datatype=XSD_STRING)))
    assert [o.toPython() for o in g.objects(link, SR.paperMentionsRepository)] == [True]
    assert [o.toPython() for o in g.objects(link, SR.repositoryMentionsPaper)] == [False]

    root = Path(__file__).resolve().parents[2]
    ok, report = validate_generated_rdf(sorted(out.glob("*.ttl")), root / "ontologies/semrepo-v2.ttl",
                                        root / "ontologies/semrepo-v2-shapes.ttl")
    assert ok, report