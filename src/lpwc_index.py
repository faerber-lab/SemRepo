"""
Local index of Linked Papers With Code (LPWC), built once from the Zenodo
N-Triples dump, so the linking step can look repositories and papers up
locally instead of sending several SPARQL queries per repository to the
public LPWC endpoint.

Source: https://zenodo.org/records/13881433 (linkedpaperswithcode_2024-09-05.nt,
MD5 3512477cd716ef8c1cf71b184b3a16ca, 10.6 M triples).

What the dump looks like (checked on the 2024-09-05 file):

    repo     rdf:type                     lpwc:class/repository
    repo     fabio:hasURL                 "https://github.com/owner/name"^^xsd:anyURI
    repo     lpwc:hasFramework            "pytorch"
    paper    lpwc:hasOfficialRepository   repo                         (159,100)
    paper    lpwc:hasRepository           repo                         ( 95,389)
    paper    lpwc:hasRepositoryReferences refnode
    refnode  lpwc:hasRepository           repo                         (254,470)
    refnode  lpwc:paperMentionsRepository "true|false"^^xsd:boolean
    refnode  lpwc:repositoryMentionsPaper "true|false"^^xsd:boolean
    dataloader lpwc:hasRepository         repo                         (  4,359)  -- not a paper
    paper    dcterms:title / dcterms:date / fabio:hasURL / fabio:hasArXivId
    paper    dcterms:creator              <https://semopenalex.org/author/...>
    paper    lpwc:creatorName             "Name"
    paper    owl:sameAs                   <https://semopenalex.org/work/...>

Note: the dump contains no MLSea (w3id.org/mlsea) links; those are only on
the live endpoint.

The index is a SQLite file (one pass over the dump, a few minutes):

    python3 src/lpwc_index.py build /data/semrepo/lpwc/linkedpaperswithcode_2024-09-05.nt /data/semrepo/lpwc/lpwc-index.sqlite
    python3 src/lpwc_index.py lookup /data/semrepo/lpwc/lpwc-index.sqlite https://github.com/ddshan/hand_object_detector
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

LPWC = "https://linkedpaperswithcode.com/"
P_HAS_URL = "http://purl.org/spar/fabio/hasURL"
P_ARXIV = "http://purl.org/spar/fabio/hasArXivId"
P_TITLE = "http://purl.org/dc/terms/title"
P_DATE = "http://purl.org/dc/terms/date"
P_CREATOR = "http://purl.org/dc/terms/creator"
P_SAME_AS = "http://www.w3.org/2002/07/owl#sameAs"
P_OFFICIAL = LPWC + "property/hasOfficialRepository"
P_HAS_REPO = LPWC + "property/hasRepository"
P_HAS_REFS = LPWC + "property/hasRepositoryReferences"
P_PAPER_MENTIONS = LPWC + "property/paperMentionsRepository"
P_REPO_MENTIONS = LPWC + "property/repositoryMentionsPaper"
P_FRAMEWORK = LPWC + "property/hasFramework"
P_CREATOR_NAME = LPWC + "property/creatorName"

REPO_PREFIX = LPWC + "repository/"
PAPER_PREFIX = LPWC + "paper/"
REFS_PREFIX = LPWC + "repositoryreferences/"
DATALOADER_PREFIX = LPWC + "dataloader/"
SOA_WORK_PREFIX = "https://semopenalex.org/work/"

PREDICATES = {P_HAS_URL, P_ARXIV, P_TITLE, P_DATE, P_CREATOR, P_SAME_AS, P_OFFICIAL, P_HAS_REPO,
              P_HAS_REFS, P_PAPER_MENTIONS, P_REPO_MENTIONS, P_FRAMEWORK, P_CREATOR_NAME}
_PREDICATE_MARKERS = tuple(f"<{p}>" for p in PREDICATES)

_LINE = re.compile(
    r'^<([^>]*)>\s+<([^>]*)>\s+(?:<([^>]*)>|"((?:[^"\\]|\\.)*)"(?:\^\^<[^>]*>|@[A-Za-z0-9-]+)?)\s*\.\s*$'
)
_ESCAPE = re.compile(r'\\(?:u([0-9A-Fa-f]{4})|U([0-9A-Fa-f]{8})|(.))')
_SIMPLE_ESCAPES = {"t": "\t", "n": "\n", "r": "\r", "b": "\b", "f": "\f", '"': '"', "'": "'", "\\": "\\"}


def _unescape(literal: str) -> str:
    def repl(m):
        if m.group(1) or m.group(2):
            return chr(int(m.group(1) or m.group(2), 16))
        return _SIMPLE_ESCAPES.get(m.group(3), m.group(3))
    return _ESCAPE.sub(repl, literal) if "\\" in literal else literal


def normalize_repo_url(url: str) -> str:
    """Comparable form of a GitHub URL: lower case, no scheme, no www,
    no trailing slash or .git. GitHub owner/repo names are case-insensitive."""
    u = (url or "").strip().lower()
    u = re.sub(r"^[a-z]+://", "", u)
    u = u[4:] if u.startswith("www.") else u
    u = u.split("#")[0].split("?")[0].rstrip("/")
    return u[:-4] if u.endswith(".git") else u


def _triples(path: Path) -> Iterator[tuple[str, str, Optional[str], Optional[str]]]:
    """(subject, predicate, object_iri, object_literal) for the predicates we need."""
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not any(marker in line for marker in _PREDICATE_MARKERS):
                continue
            m = _LINE.match(line)
            if m:
                s, p, o_iri, o_lit = m.groups()
                yield s, p, o_iri, (_unescape(o_lit) if o_lit is not None else None)


SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE repo (repo_iri TEXT PRIMARY KEY, url TEXT, url_norm TEXT, framework TEXT);
CREATE INDEX repo_url_norm ON repo(url_norm);
CREATE TABLE paper (paper_iri TEXT PRIMARY KEY, title TEXT, url TEXT, arxiv_id TEXT, date TEXT, soa_work TEXT);
CREATE TABLE paper_repo (
    paper_iri TEXT, repo_iri TEXT,
    official INTEGER, direct_reference INTEGER, via_reference_node INTEGER,
    paper_mentions_repo INTEGER, repo_mentions_paper INTEGER,
    PRIMARY KEY (paper_iri, repo_iri));
CREATE INDEX paper_repo_repo ON paper_repo(repo_iri);
CREATE TABLE paper_author (paper_iri TEXT, author_iri TEXT, PRIMARY KEY (paper_iri, author_iri));
CREATE TABLE paper_creator_name (paper_iri TEXT, name TEXT, PRIMARY KEY (paper_iri, name));
CREATE TABLE dataloader_repo (dataloader_iri TEXT, repo_iri TEXT, PRIMARY KEY (dataloader_iri, repo_iri));
"""


def _bool(value: Optional[str]) -> Optional[int]:
    return None if value is None else int(value.strip().lower() == "true")


def build_index(nt_path: Path, db_path: Path, log_every: int = 1_000_000) -> dict:
    """One pass over the dump; writes a fresh SQLite index. Returns counts."""
    started = time.monotonic()
    repos: dict[str, dict] = defaultdict(dict)
    papers: dict[str, dict] = defaultdict(dict)
    links: dict[tuple[str, str], dict] = defaultdict(dict)
    ref_paper: dict[str, str] = {}
    ref_repo: dict[str, str] = {}
    ref_flags: dict[str, dict] = defaultdict(dict)
    authors: set[tuple[str, str]] = set()
    creator_names: set[tuple[str, str]] = set()
    dataloaders: set[tuple[str, str]] = set()
    other_has_repo = 0
    seen = 0

    for s, p, o_iri, o_lit in _triples(nt_path):
        seen += 1
        if log_every and seen % log_every == 0:
            print(f"  {seen:,} relevant triples read ({time.monotonic() - started:.0f} s)", flush=True)

        if p == P_HAS_URL and o_lit is not None and s.startswith(REPO_PREFIX):
            repos[s]["url"] = o_lit
        elif p == P_FRAMEWORK and s.startswith(REPO_PREFIX):
            repos[s]["framework"] = o_lit
        elif p == P_OFFICIAL and o_iri:
            links[(s, o_iri)]["official"] = 1
        elif p == P_HAS_REPO and o_iri:
            if s.startswith(PAPER_PREFIX):
                links[(s, o_iri)]["direct_reference"] = 1
            elif s.startswith(REFS_PREFIX):
                ref_repo[s] = o_iri
            elif s.startswith(DATALOADER_PREFIX):
                dataloaders.add((s, o_iri))
            else:
                other_has_repo += 1
        elif p == P_HAS_REFS and o_iri:
            ref_paper[o_iri] = s
        elif p == P_PAPER_MENTIONS:
            ref_flags[s]["paper_mentions_repo"] = _bool(o_lit)
        elif p == P_REPO_MENTIONS:
            ref_flags[s]["repo_mentions_paper"] = _bool(o_lit)
        elif s.startswith(PAPER_PREFIX):
            if p == P_TITLE:
                papers[s]["title"] = o_lit
            elif p == P_HAS_URL:
                papers[s]["url"] = o_lit
            elif p == P_ARXIV:
                papers[s]["arxiv_id"] = o_lit
            elif p == P_DATE:
                papers[s]["date"] = o_lit
            elif p == P_SAME_AS and o_iri and o_iri.startswith(SOA_WORK_PREFIX):
                papers[s]["soa_work"] = o_iri
            elif p == P_CREATOR and o_iri:
                authors.add((s, o_iri))
            elif p == P_CREATOR_NAME and o_lit:
                creator_names.add((s, o_lit))

    unresolved_refs = 0
    for ref, repo in ref_repo.items():
        paper = ref_paper.get(ref)
        if paper is None:
            unresolved_refs += 1
            continue
        link = links[(paper, repo)]
        link["via_reference_node"] = 1
        for key, value in ref_flags.get(ref, {}).items():
            if value is not None:
                link[key] = max(link.get(key) or 0, value)

    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO repo VALUES (?,?,?,?)",
                    ((iri, r.get("url"), normalize_repo_url(r["url"]) if r.get("url") else None, r.get("framework"))
                     for iri, r in repos.items()))
    con.executemany("INSERT INTO paper VALUES (?,?,?,?,?,?)",
                    ((iri, d.get("title"), d.get("url"), d.get("arxiv_id"), d.get("date"), d.get("soa_work"))
                     for iri, d in papers.items()))
    con.executemany("INSERT INTO paper_repo VALUES (?,?,?,?,?,?,?)",
                    ((paper, repo, l.get("official", 0), l.get("direct_reference", 0), l.get("via_reference_node", 0),
                      l.get("paper_mentions_repo"), l.get("repo_mentions_paper"))
                     for (paper, repo), l in links.items()))
    con.executemany("INSERT INTO paper_author VALUES (?,?)", authors)
    con.executemany("INSERT INTO paper_creator_name VALUES (?,?)", creator_names)
    con.executemany("INSERT INTO dataloader_repo VALUES (?,?)", dataloaders)

    counts = {
        "relevant_triples": seen,
        "repositories": len(repos),
        "repositories_with_url": sum(1 for r in repos.values() if r.get("url")),
        "papers_with_metadata": len(papers),
        "paper_repository_links": len(links),
        "official_links": sum(1 for l in links.values() if l.get("official")),
        "reference_nodes": len(ref_repo),
        "reference_nodes_without_paper": unresolved_refs,
        "dataloader_links": len(dataloaders),
        "other_hasRepository_subjects": other_has_repo,
        "paper_author_links": len(authors),
        "creator_names": len(creator_names),
        "papers_with_semopenalex_work": sum(1 for d in papers.values() if d.get("soa_work")),
        "build_seconds": round(time.monotonic() - started, 1),
    }
    meta = {"source_file": nt_path.name, "built_at": datetime.now(timezone.utc).isoformat(),
            "counts": json.dumps(counts)}
    con.executemany("INSERT INTO meta VALUES (?,?)", meta.items())
    con.commit()
    con.close()
    return counts


class LpwcIndex:
    """Read-only lookups on a built index."""

    def __init__(self, db_path: Path):
        self.con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.con.row_factory = sqlite3.Row

    def find_repositories(self, github_url: str) -> list[dict]:
        rows = self.con.execute("SELECT * FROM repo WHERE url_norm = ?", (normalize_repo_url(github_url),))
        return [dict(r) for r in rows]

    def papers_for_repository(self, repo_iri: str) -> list[dict]:
        papers = []
        for link in self.con.execute("SELECT * FROM paper_repo WHERE repo_iri = ? ORDER BY paper_iri", (repo_iri,)):
            paper_iri = link["paper_iri"]
            row = self.con.execute("SELECT * FROM paper WHERE paper_iri = ?", (paper_iri,)).fetchone()
            papers.append({
                **(dict(row) if row else {"paper_iri": paper_iri}),
                "official": bool(link["official"]),
                "direct_reference": bool(link["direct_reference"]),
                "via_reference_node": bool(link["via_reference_node"]),
                "paper_mentions_repo": None if link["paper_mentions_repo"] is None else bool(link["paper_mentions_repo"]),
                "repo_mentions_paper": None if link["repo_mentions_paper"] is None else bool(link["repo_mentions_paper"]),
                "soa_authors": [r[0] for r in self.con.execute(
                    "SELECT author_iri FROM paper_author WHERE paper_iri = ? ORDER BY author_iri", (paper_iri,))],
                "creator_names": [r[0] for r in self.con.execute(
                    "SELECT name FROM paper_creator_name WHERE paper_iri = ? ORDER BY name", (paper_iri,))],
            })
        return papers

    def lookup(self, github_url: str) -> list[dict]:
        return [{**repo, "papers": self.papers_for_repository(repo["repo_iri"])}
                for repo in self.find_repositories(github_url)]

    def meta(self) -> dict:
        return {k: v for k, v in self.con.execute("SELECT key, value FROM meta")}


def _md5(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(argv: list[str]) -> None:
    if len(argv) >= 3 and argv[0] == "build":
        nt, db = Path(argv[1]), Path(argv[2])
        print(f"Building {db} from {nt} ...", flush=True)
        counts = build_index(nt, db)
        print(json.dumps(counts, indent=2))
    elif len(argv) >= 3 and argv[0] == "lookup":
        index = LpwcIndex(Path(argv[1]))
        print(json.dumps(index.lookup(argv[2]), indent=2, ensure_ascii=False))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])