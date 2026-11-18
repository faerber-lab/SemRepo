"""
Linking for the full run: GitHub repositories -> LPWC papers, MLSea
software and SemOpenAlex authors.

Replaces the per-repository SPARQL calls of linking.py with:
- a local LPWC index (lpwc_index.py, built from the Zenodo dump) for
  repository and paper lookups;
- lookups with the current AND the original repository URLs
  (source-repository-links.jsonl), so renamed/transferred repos are found;
- correct paper resolution: LPWC "repositoryreferences" nodes are mapped to
  their paper, and dataloaders are not treated as papers;
- batched SemOpenAlex author queries (names, ORCID, h-index) and batched
  MLSea queries against the live LPWC endpoint, both cached on disk and
  shared across collections;
- retries, and a checkpoint: every repository is appended to
  external-links.jsonl as soon as it is linked, so a re-run continues where
  it stopped.

The contributor <-> author name matching itself is unchanged: it reuses
linking.add_repository_contributor_matches(). The output has the format
generate_rdf_with_linking.py expects (plus extra evidence fields that the
RDF step ignores for now).

Only collections with a _COMPLETE marker (finished harvest) are linked.

Usage (from the repository root):
    python3 src/link_repositories.py \\
        --index /data/semrepo/lpwc/lpwc-index.sqlite \\
        --cache /data/semrepo/linking-cache.sqlite \\
        /data/semrepo/full-run/10001_15000            # one or more collection folders
    python3 src/link_repositories.py --index ... --cache ... --all /data/semrepo/full-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

from lpwc_index import LpwcIndex, normalize_repo_url

LPWC_ENDPOINT = "https://linkedpaperswithcode.com/sparql"
SOA_ENDPOINT = "https://semopenalex.org/sparql"
BATCH_SIZE = 100         # IRIs per batched SPARQL query
CHUNK_SIZE = 200         # repositories per chunk (queries are batched per chunk, results written per repository)
ATTEMPTS = 4
FUZZY_THRESHOLD = 0.60   # same as linking.py

SOA_QUERY = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX dbo:  <https://dbpedia.org/ontology/>
PREFIX bido: <http://purl.org/spar/bido/>
SELECT ?author ?name ?label ?orcidId ?hindex WHERE {
  VALUES ?author { %s }
  OPTIONAL { ?author foaf:name ?name . }
  OPTIONAL { ?author rdfs:label ?label . }
  OPTIONAL { ?author dbo:orcidId ?orcidId . }
  OPTIONAL { ?author bido:h-index ?hindex . }
}"""

MLSEA_QUERY = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?repo ?mlsea WHERE {
  VALUES ?repo { %s }
  ?repo owl:sameAs ?mlsea .
  FILTER(STRSTARTS(STR(?mlsea), "http://w3id.org/mlsea/") || STRSTARTS(STR(?mlsea), "https://w3id.org/mlsea/"))
}"""


# ---------------------------------------------------------------------------
# SPARQL with retries
# ---------------------------------------------------------------------------

def sparql_select(endpoint: str, query: str) -> list[dict]:
    from SPARQLWrapper import JSON, SPARQLWrapper
    client = SPARQLWrapper(endpoint)
    client.setQuery(query)
    client.setReturnFormat(JSON)
    client.setMethod("POST")      # VALUES blocks make long queries
    client.setTimeout(120)
    return client.query().convert()["results"]["bindings"]


def with_retries(fn: Callable, *args, attempts: int = ATTEMPTS, sleep=time.sleep, stats: Optional[Counter] = None):
    for attempt in range(attempts):
        try:
            if stats is not None:
                stats["sparql_queries"] += 1
            return fn(*args)
        except Exception:
            if stats is not None:
                stats["sparql_retries"] += 1
            if attempt == attempts - 1:
                raise
            sleep(10 * (attempt + 1))


def _value(row: dict, key: str) -> Optional[str]:
    v = row.get(key)
    return v["value"] if v else None


def _batches(items: list, size: int) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


# ---------------------------------------------------------------------------
# Disk cache for SemOpenAlex authors and MLSea links (shared across collections)
# ---------------------------------------------------------------------------

class LinkingCache:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path)
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS soa_author (author_uri TEXT PRIMARY KEY, data TEXT, fetched_at TEXT);
            CREATE TABLE IF NOT EXISTS mlsea (repo_iri TEXT PRIMARY KEY, uris TEXT, fetched_at TEXT);
        """)

    def _get(self, table: str, key_col: str, value_col: str, keys: list[str]) -> dict:
        found = {}
        for batch in _batches(keys, 500):
            q = f"SELECT {key_col}, {value_col} FROM {table} WHERE {key_col} IN ({','.join('?' * len(batch))})"
            found.update({k: json.loads(v) for k, v in self.con.execute(q, batch)})
        return found

    def get_authors(self, uris: list[str]) -> dict:
        return self._get("soa_author", "author_uri", "data", uris)

    def put_authors(self, data: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.con.executemany("INSERT OR REPLACE INTO soa_author VALUES (?,?,?)",
                             ((k, json.dumps(v), now) for k, v in data.items()))
        self.con.commit()

    def get_mlsea(self, repo_iris: list[str]) -> dict:
        return self._get("mlsea", "repo_iri", "uris", repo_iris)

    def put_mlsea(self, data: dict) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self.con.executemany("INSERT OR REPLACE INTO mlsea VALUES (?,?,?)",
                             ((k, json.dumps(v), now) for k, v in data.items()))
        self.con.commit()


def fetch_soa_authors(uris: list[str], cache: LinkingCache, select=sparql_select, stats=None, sleep=time.sleep) -> dict:
    """author_uri -> {author_uri, author_names, orcid_ids, h_index_values}; cached."""
    known = cache.get_authors(uris)
    missing = [u for u in uris if u not in known]
    for batch in _batches(missing, BATCH_SIZE):
        values = " ".join(f"<{u}>" for u in batch)
        rows = with_retries(select, SOA_ENDPOINT, SOA_QUERY % values, stats=stats, sleep=sleep)
        data = {u: {"author_uri": u, "author_names": [], "orcid_ids": [], "h_index_values": []} for u in batch}
        for row in rows:
            d = data.get(_value(row, "author"))
            if d is None:
                continue
            for name in (_value(row, "name"), _value(row, "label")):
                if name and name not in d["author_names"]:
                    d["author_names"].append(name)
            orcid, hindex = _value(row, "orcidId"), _value(row, "hindex")
            if orcid and orcid not in d["orcid_ids"]:
                d["orcid_ids"].append(orcid)
            if hindex and hindex not in d["h_index_values"]:
                d["h_index_values"].append(hindex)
        cache.put_authors(data)
        known.update(data)
    return known


def fetch_mlsea(repo_iris: list[str], cache: LinkingCache, select=sparql_select, stats=None, sleep=time.sleep) -> dict:
    """lpwc repo IRI -> [MLSea IRIs]; cached (empty lists too)."""
    known = cache.get_mlsea(repo_iris)
    missing = [r for r in repo_iris if r not in known]
    for batch in _batches(missing, BATCH_SIZE):
        values = " ".join(f"<{r}>" for r in batch)
        rows = with_retries(select, LPWC_ENDPOINT, MLSEA_QUERY % values, stats=stats, sleep=sleep)
        data = {r: [] for r in batch}
        for row in rows:
            repo, mlsea = _value(row, "repo"), _value(row, "mlsea")
            if repo in data and mlsea and mlsea not in data[repo]:
                data[repo].append(mlsea)
        for r in data:
            data[r].sort()
        cache.put_mlsea(data)
        known.update(data)
    return known


# ---------------------------------------------------------------------------
# One collection folder
# ---------------------------------------------------------------------------

def _read_jsonl(path: Path) -> Iterable[dict]:
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def _paper_record(p: dict) -> dict:
    """Paper in the format generate_rdf_with_linking.py / linking.py use, plus evidence fields."""
    relations = []
    if p["official"]:
        relations.append("hasOfficialRepository")
    if p["via_reference_node"] or p["direct_reference"]:
        relations.append("hasRepository")
    return {
        "lpwc_paper_uri": p["paper_iri"],
        "title": p.get("title"),
        "paper_url": p.get("url"),
        "creator_names": p.get("creator_names") or [],
        "authors": [{"lpwc_author_uri": a, "rdf_type": None} for a in p.get("soa_authors") or []],
        "repository_relations": relations,
        # evidence, not used by the RDF step yet
        "arxiv_id": p.get("arxiv_id"),
        "date": p.get("date"),
        "soa_work_uri": p.get("soa_work"),
        "paper_mentions_repo": p.get("paper_mentions_repo"),
        "repo_mentions_paper": p.get("repo_mentions_paper"),
    }


def link_collection(folder: Path, index: LpwcIndex, cache: LinkingCache, select=sparql_select,
                    sleep=time.sleep, match_contributors=None, log=print) -> dict:
    if match_contributors is None:
        from linking import add_repository_contributor_matches as match_contributors

    started = time.monotonic()
    out_path = folder / "external-links.jsonl"
    review_path = folder / "github-soa-match-review.jsonl"
    done = {rec["github_repository_id"] for rec in _read_jsonl(out_path)}

    repositories = [r for r in _read_jsonl(folder / "repositories.jsonl") if r["github_repository_id"] not in done]
    contributions = list(_read_jsonl(folder / "contributions.jsonl"))
    contributors = list(_read_jsonl(folder / "contributors.jsonl"))
    urls_by_repo: dict[int, set[str]] = {}
    for link in _read_jsonl(folder / "source-repository-links.jsonl"):
        rid = link.get("resolved_repository_github_id")
        if rid is not None:
            urls_by_repo.setdefault(rid, set()).add(link["original_repository_url"])

    c: Counter = Counter(skipped_already_linked=len(done))
    stats: Counter = Counter()
    match_types: Counter = Counter()

    for chunk in _batches(repositories, CHUNK_SIZE):
        # 1. local LPWC lookups (current + original URLs)
        prepared = []
        for repo in chunk:
            rid, canonical = repo["github_repository_id"], repo["canonical_url"]
            found, via = {}, {}
            for url in [canonical] + sorted(urls_by_repo.get(rid, set())):
                for lpwc_repo in index.find_repositories(url):
                    if lpwc_repo["repo_iri"] not in found:
                        found[lpwc_repo["repo_iri"]] = lpwc_repo
                        same = normalize_repo_url(url) == normalize_repo_url(canonical)
                        via[lpwc_repo["repo_iri"]] = "current_url" if same else "original_url"
            papers = {iri: [_paper_record(p) for p in index.papers_for_repository(iri)] for iri in found}
            prepared.append((repo, found, via, papers))

        # 2. batched remote lookups for the whole chunk (cached)
        author_uris = sorted({a["lpwc_author_uri"] for _, _, _, papers in prepared
                              for plist in papers.values() for p in plist for a in p["authors"]})
        repo_iris = sorted({iri for _, found, _, _ in prepared for iri in found})
        authors = fetch_soa_authors(author_uris, cache, select, stats, sleep)
        mlsea = fetch_mlsea(repo_iris, cache, select, stats, sleep)

        # 3. assemble, match contributors, write each repository immediately
        with out_path.open("a", encoding="utf-8") as out, review_path.open("a", encoding="utf-8") as rev:
            for repo, found, via, papers in prepared:
                rid = repo["github_repository_id"]
                result = {
                    "github_repository_id": rid,
                    "github_repository_url": repo["canonical_url"],
                    "lpwc_repository_matches": [],
                    "status": "RepositoryMatched" if found else "NoExactRepositoryMatch",
                }
                for iri, lpwc_repo in found.items():
                    plist = papers[iri]
                    for p in plist:
                        p["authors"] = [{**a, **authors.get(a["lpwc_author_uri"], {})} for a in p["authors"]]
                    result["lpwc_repository_matches"].append({
                        "lpwc_repository_uri": iri,
                        "github_url": lpwc_repo["url"],
                        "matched_via": via[iri],
                        "papers": plist,
                        "mlsea_software_uris": mlsea.get(iri, []),
                    })
                matches, reviews = match_contributors(result, contributions, contributors, fuzzy_threshold=FUZZY_THRESHOLD)
                result["github_contributor_soa_matches"] = matches
                out.write(json.dumps(result, ensure_ascii=False) + "\n")
                for r in reviews:
                    rev.write(json.dumps(r, ensure_ascii=False) + "\n")

                c["repositories_linked"] += 1
                if found:
                    c["lpwc_matched"] += 1
                    if all(v == "original_url" for v in via.values()):
                        c["matched_only_via_original_url"] += 1
                    c["papers"] += sum(len(p) for p in papers.values())
                    c["official_papers"] += sum(1 for p in papers.values() for x in p if "hasOfficialRepository" in x["repository_relations"])
                    c["papers_with_soa_work"] += sum(1 for p in papers.values() for x in p if x["soa_work_uri"])
                    c["mlsea_links"] += sum(len(mlsea.get(i, [])) for i in found)
                c["contributor_matches"] += len(matches)
                c["review_records"] += len(reviews)
                match_types.update(m["match_type"] for m in matches)
        log(f"{folder.name}: {c['repositories_linked']}/{len(repositories)} repositories linked "
            f"({stats['sparql_queries']} SPARQL queries, {time.monotonic() - started:.0f} s)")

    summary = {
        "collection": folder.name,
        "linked_at": datetime.now(timezone.utc).isoformat(),
        "index": index.meta().get("source_file"),
        "counts": dict(c),
        "contributor_match_types": dict(match_types),
        "sparql": dict(stats),
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    (folder / "linking-summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Link harvested repositories to LPWC, MLSea and SemOpenAlex.")
    ap.add_argument("folders", nargs="*", type=Path)
    ap.add_argument("--all", type=Path, help="link every complete collection under this folder")
    ap.add_argument("--index", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    args = ap.parse_args(argv)

    folders = list(args.folders)
    if args.all:
        folders += sorted(p for p in args.all.iterdir() if p.is_dir() and (p / "repositories.jsonl").exists())
    if not folders:
        sys.exit("No collection folders given.")

    index, cache = LpwcIndex(args.index), LinkingCache(args.cache)
    for folder in folders:
        if not (folder / "_COMPLETE").exists():
            print(f"{folder.name}: harvest not complete yet -- skipped")
            continue
        summary = link_collection(folder, index, cache)
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()