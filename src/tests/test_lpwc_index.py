"""Tests for src/lpwc_index.py on a tiny synthetic dump that follows the
structure of the real 2024-09-05 LPWC dump."""

from lpwc_index import LpwcIndex, build_index, normalize_repo_url

L = "https://linkedpaperswithcode.com/"
NT = f"""
<{L}repository/github.com/Owner/Repo> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <{L}class/repository> .
<{L}repository/github.com/Owner/Repo> <http://purl.org/spar/fabio/hasURL> "https://github.com/Owner/Repo"^^<http://www.w3.org/2001/XMLSchema#anyURI> .
<{L}repository/github.com/Owner/Repo> <{L}property/hasFramework> "pytorch" .
<{L}paper/p1> <{L}property/hasOfficialRepository> <{L}repository/github.com/Owner/Repo> .
<{L}paper/p1> <{L}property/hasRepositoryReferences> <{L}repositoryreferences/p1/github.com/Owner/Repo> .
<{L}repositoryreferences/p1/github.com/Owner/Repo> <{L}property/hasRepository> <{L}repository/github.com/Owner/Repo> .
<{L}repositoryreferences/p1/github.com/Owner/Repo> <{L}property/paperMentionsRepository> "true"^^<http://www.w3.org/2001/XMLSchema#boolean> .
<{L}repositoryreferences/p1/github.com/Owner/Repo> <{L}property/repositoryMentionsPaper> "false"^^<http://www.w3.org/2001/XMLSchema#boolean> .
<{L}paper/p1> <http://purl.org/dc/terms/title> "A \\"quoted\\" title \\u00e9" .
<{L}paper/p1> <http://purl.org/spar/fabio/hasURL> "https://arxiv.org/pdf/1.pdf"^^<http://www.w3.org/2001/XMLSchema#anyURI> .
<{L}paper/p1> <http://purl.org/dc/terms/creator> <https://semopenalex.org/author/A1> .
<{L}paper/p1> <http://www.w3.org/2002/07/owl#sameAs> <https://semopenalex.org/work/W1> .
<{L}paper/p2> <{L}property/hasRepositoryReferences> <{L}repositoryreferences/p2/github.com/Owner/Repo> .
<{L}repositoryreferences/p2/github.com/Owner/Repo> <{L}property/hasRepository> <{L}repository/github.com/Owner/Repo> .
<{L}paper/p2> <{L}property/creatorName> "Jane Doe" .
<{L}dataloader/x> <{L}property/hasRepository> <{L}repository/github.com/Owner/Repo> .
<{L}paper/p1> <http://purl.org/dc/terms/abstract> "ignored" .
"""


def _index(tmp_path):
    nt = tmp_path / "lpwc.nt"
    nt.write_text(NT.strip() + "\n", encoding="utf-8")
    counts = build_index(nt, tmp_path / "idx.sqlite", log_every=0)
    return counts, LpwcIndex(tmp_path / "idx.sqlite")


def test_normalize_repo_url():
    for url in ["https://github.com/Owner/Repo", "http://www.github.com/owner/repo/", "github.com/OWNER/repo.git",
                "https://github.com/owner/repo?tab=readme#x"]:
        assert normalize_repo_url(url) == "github.com/owner/repo"


def test_lookup_finds_repo_case_insensitively(tmp_path):
    _, index = _index(tmp_path)
    found = index.find_repositories("https://github.com/owner/repo.git")
    assert [r["repo_iri"] for r in found] == [f"{L}repository/github.com/Owner/Repo"]
    assert found[0]["framework"] == "pytorch"


def test_reference_nodes_resolve_to_papers_and_dataloaders_are_not_papers(tmp_path):
    counts, index = _index(tmp_path)
    papers = {p["paper_iri"]: p for p in index.papers_for_repository(f"{L}repository/github.com/Owner/Repo")}

    assert set(papers) == {f"{L}paper/p1", f"{L}paper/p2"}          # no dataloader, no reference-node IRIs
    p1, p2 = papers[f"{L}paper/p1"], papers[f"{L}paper/p2"]
    assert p1["official"] and p1["via_reference_node"]
    assert p1["paper_mentions_repo"] is True and p1["repo_mentions_paper"] is False
    assert not p2["official"] and p2["via_reference_node"]
    assert counts["dataloader_links"] == 1 and counts["reference_nodes_without_paper"] == 0


def test_paper_metadata_and_semopenalex_links(tmp_path):
    _, index = _index(tmp_path)
    p1 = next(p for p in index.papers_for_repository(f"{L}repository/github.com/Owner/Repo")
              if p["paper_iri"].endswith("/p1"))
    assert p1["title"] == 'A "quoted" title é'
    assert p1["url"] == "https://arxiv.org/pdf/1.pdf"
    assert p1["soa_work"] == "https://semopenalex.org/work/W1"
    assert p1["soa_authors"] == ["https://semopenalex.org/author/A1"]


def test_unknown_url_returns_nothing(tmp_path):
    _, index = _index(tmp_path)
    assert index.lookup("https://github.com/nobody/nothing") == []