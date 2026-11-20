"""Tests for src/link_repositories.py -- offline: real LpwcIndex on a tiny
dump, fake SPARQL endpoint, fake contributor matcher."""

import json

import pytest

from link_repositories import LinkingCache, link_collection
from lpwc_index import LpwcIndex, build_index

L = "https://linkedpaperswithcode.com/"
NT = f"""
<{L}repository/github.com/old/name> <http://purl.org/spar/fabio/hasURL> "https://github.com/old/name"^^<http://www.w3.org/2001/XMLSchema#anyURI> .
<{L}paper/p1> <{L}property/hasOfficialRepository> <{L}repository/github.com/old/name> .
<{L}paper/p1> <{L}property/hasRepositoryReferences> <{L}repositoryreferences/p1/github.com/old/name> .
<{L}repositoryreferences/p1/github.com/old/name> <{L}property/hasRepository> <{L}repository/github.com/old/name> .
<{L}paper/p1> <http://purl.org/dc/terms/creator> <https://semopenalex.org/author/A1> .
<{L}paper/p1> <http://www.w3.org/2002/07/owl#sameAs> <https://semopenalex.org/work/W1> .
<{L}repository/github.com/a/plain> <http://purl.org/spar/fabio/hasURL> "https://github.com/a/plain"^^<http://www.w3.org/2001/XMLSchema#anyURI> .
<{L}paper/p2> <{L}property/hasRepositoryReferences> <{L}repositoryreferences/p2/github.com/a/plain> .
<{L}repositoryreferences/p2/github.com/a/plain> <{L}property/hasRepository> <{L}repository/github.com/a/plain> .
<{L}paper/p2> <http://purl.org/dc/terms/creator> <https://semopenalex.org/author/A1> .
"""


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


class FakeEndpoint:
    def __init__(self, fail_first=0):
        self.queries = []
        self.fail_first = fail_first

    def __call__(self, endpoint, query):
        self.queries.append((endpoint, query))
        if self.fail_first:
            self.fail_first -= 1
            raise TimeoutError("simulated")
        if "semopenalex" in endpoint:
            return [{"author": {"value": "https://semopenalex.org/author/A1"}, "name": {"value": "Jane Doe"}}]
        if f"<{L}repository/github.com/old/name>" in query:
            return [{"repo": {"value": f"{L}repository/github.com/old/name"}, "mlsea": {"value": "http://w3id.org/mlsea/x"}}]
        return []


@pytest.fixture
def setup(tmp_path):
    nt = tmp_path / "lpwc.nt"
    nt.write_text(NT.strip() + "\n")
    build_index(nt, tmp_path / "idx.sqlite", log_every=0)
    folder = tmp_path / "1_5"
    folder.mkdir()
    _write(folder / "repositories.jsonl", [
        {"github_repository_id": 1, "canonical_url": "https://github.com/new/name"},     # renamed
        {"github_repository_id": 2, "canonical_url": "https://github.com/A/Plain"},
        {"github_repository_id": 3, "canonical_url": "https://github.com/not/inlpwc"},
    ])
    _write(folder / "source-repository-links.jsonl", [
        {"original_repository_url": "https://github.com/old/name", "resolved_repository_github_id": 1},
        {"original_repository_url": "https://github.com/a/plain", "resolved_repository_github_id": 2},
        {"original_repository_url": "https://github.com/not/inlpwc", "resolved_repository_github_id": 3},
    ])
    (folder / "_COMPLETE").write_text("x")
    return folder, LpwcIndex(tmp_path / "idx.sqlite"), LinkingCache(tmp_path / "cache.sqlite")


def _no_matches(result, contributions, contributors, fuzzy_threshold):
    return [], []


def _records(folder):
    return {r["github_repository_id"]: r for r in map(json.loads, (folder / "external-links.jsonl").read_text().splitlines())}


def test_links_renamed_repo_via_original_url_with_correct_relations(setup):
    folder, index, cache = setup
    summary = link_collection(folder, index, cache, select=FakeEndpoint(), sleep=lambda s: None,
                              match_contributors=_no_matches, log=lambda m: None)
    recs = _records(folder)

    assert recs[1]["status"] == "RepositoryMatched"
    m = recs[1]["lpwc_repository_matches"][0]
    assert m["matched_via"] == "original_url"
    assert [p["lpwc_paper_uri"] for p in m["papers"]] == [f"{L}paper/p1"]          # no reference-node IRIs
    assert m["papers"][0]["repository_relations"] == ["hasOfficialRepository", "hasRepository"]
    assert m["papers"][0]["authors"][0]["author_names"] == ["Jane Doe"]
    assert m["papers"][0]["soa_work_uri"] == "https://semopenalex.org/work/W1"
    assert m["mlsea_software_uris"] == ["http://w3id.org/mlsea/x"]

    assert recs[2]["lpwc_repository_matches"][0]["papers"][0]["repository_relations"] == ["hasRepository"]
    assert recs[3]["status"] == "NoExactRepositoryMatch"
    assert summary["counts"]["matched_only_via_original_url"] == 1


def test_remote_queries_are_batched_and_cached(setup):
    folder, index, cache = setup
    endpoint = FakeEndpoint()
    link_collection(folder, index, cache, select=endpoint, sleep=lambda s: None,
                    match_contributors=_no_matches, log=lambda m: None)
    assert len(endpoint.queries) == 2            # 1 SemOpenAlex batch (A1 once) + 1 MLSea batch, for 3 repos

    (folder / "external-links.jsonl").unlink()
    endpoint2 = FakeEndpoint()
    link_collection(folder, index, cache, select=endpoint2, sleep=lambda s: None,
                    match_contributors=_no_matches, log=lambda m: None)
    assert endpoint2.queries == []               # everything came from the cache


def test_retries_and_resume(setup):
    folder, index, cache = setup
    link_collection(folder, index, cache, select=FakeEndpoint(fail_first=2), sleep=lambda s: None,
                    match_contributors=_no_matches, log=lambda m: None)
    assert len(_records(folder)) == 3

    summary = link_collection(folder, index, cache, select=FakeEndpoint(), sleep=lambda s: None,
                              match_contributors=_no_matches, log=lambda m: None)
    assert summary["counts"]["skipped_already_linked"] == 3
    assert len((folder / "external-links.jsonl").read_text().splitlines()) == 3   # nothing written twice


def test_output_works_with_generate_rdf_external_links(setup, tmp_path):
    from rdflib import Graph
    from generate_rdf_with_linking import add_external_links, add_lpwc_authorship
    folder, index, cache = setup
    link_collection(folder, index, cache, select=FakeEndpoint(), sleep=lambda s: None,
                    match_contributors=_no_matches, log=lambda m: None)
    g = Graph()
    n_links = add_external_links(g, folder / "external-links.jsonl")
    n_auth = add_lpwc_authorship(g, folder / "external-links.jsonl")
    # repo1: same-repository + official + referenced + MLSea = 4, plus 2 SemOpenAlex-work links
    # (p1 is owl:sameAs W1, once per relation); repo2: same-repository + referenced = 2
    assert n_links == 8
    assert n_auth == 2