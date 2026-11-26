"""
Final dataset statistics of a SemRepo v2 release (evaluation step 9.5),
computed directly from the publication copy and the generated RDF -- not
from the per-step summary files, which count links per repository before
cross-collection dedup.

Usage:
    python3 src/compute_statistics.py <publish root> <rdf root> <output dir> \\
        [--precision score-result.json] [--triples] [--workers 3]

Writes <output dir>/statistics.json and <output dir>/statistics.md.
--triples parses every Turtle file and sums the triples per file (slow: the whole RDF
is read once). This also checks that every file parses. The sum counts a triple
once per file it appears in; triples about resources shared by several
collections are repeated, so the number of distinct triples (what a triple
store holds) is lower -- count it with src/export_ntriples.py and `sort -u`.
--precision uses the per-stratum precision of the manual sample to estimate
the precision of the published contributor -> author links on the full data.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Iterator, Optional

from generate_rdf_with_linking import RDF_FUZZY_THRESHOLD
from sample_contributor_matches import stratum

# SemRepo v1 (Zenodo RDF dump of 2025-05-11, as published in the v1 paper);
# source: src/docs/current-statistics-comparison.csv
V1 = {
    "triples": 82_078_636,      # compare with the distinct count of the v2 release (export_ntriples.py)
    "repositories": 197_566,
    "mlsea_links": 148_186,
    "github_soa_author_links": 11_867,      # persons linked to a SemOpenAlex author
    "issues (hasIssue usages)": 2_609_510,
}


def _read(path: Path) -> Iterator[dict]:
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def _collections(root: Path) -> list[Path]:
    return sorted(p for p in root.iterdir() if p.is_dir())


def _top(counter: Counter, n: int = 10) -> list[list]:
    return [[k, v] for k, v in counter.most_common(n)]


def repository_statistics(cols: list[Path]) -> dict:
    repos = sum(1 for c in cols for _ in _read(c / "repositories.jsonl"))
    primary = Counter(r["primary_language"] for c in cols for r in _read(c / "snapshots.jsonl") if r.get("primary_language"))
    used = Counter(r["language_name"] for c in cols for r in _read(c / "language-usage.jsonl") if r.get("language_name"))
    return {"repositories": repos, "distinct_languages": len(used),
            "top_primary_languages": _top(primary), "top_languages_by_repositories_using_them": _top(used)}


def issue_statistics(cols: list[Path]) -> dict:
    n = prs = 0
    author_types: Counter = Counter()
    repos_with_issues, repos_with_prs, authors = set(), set(), set()
    for c in cols:
        for r in _read(c / "issues.jsonl"):
            n += 1
            rid = r.get("belongs_to_repository_github_id")
            if r.get("is_pull_request"):
                prs += 1
                repos_with_prs.add(rid)
            else:
                repos_with_issues.add(rid)
            author_types[r.get("issue_author_type") or "unknown"] += 1
            if r.get("issue_author_github_id") is not None:
                authors.add(r["issue_author_github_id"])
    return {"issues_and_pull_requests": n, "pull_requests": prs, "issues": n - prs,
            "repositories_with_issues": len(repos_with_issues), "repositories_with_pull_requests": len(repos_with_prs),
            "distinct_issue_authors": len(authors), "issue_authors_by_account_type": dict(author_types)}


def contributor_statistics(cols: list[Path]) -> dict:
    contributors, repos = set(), set()
    n = 0
    for c in cols:
        for r in _read(c / "contributions.jsonl"):
            n += 1
            contributors.add(r["contributor_github_user_id"])
            repos.add(r["repository_github_id"])
    types = Counter(r.get("contributor_account_type") or "unknown" for c in cols for r in _read(c / "contributors.jsonl"))
    return {"contributions": n, "distinct_contributors": len(contributors),
            "repositories_with_contributions": len(repos), "contributor_profiles_by_account_type": dict(types)}


def linking_statistics(cols: list[Path], precision: Optional[dict] = None) -> dict:
    papers, official, works, mlsea, tasks = set(), set(), set(), set(), set()
    paper_areas: dict[str, set] = {}
    repos_lpwc = repos_paper = repos_work = repos_mlsea = 0
    pairs: dict[tuple, dict] = {}
    for c in cols:
        for rec in _read(c / "external-links.jsonl"):
            matches = rec.get("lpwc_repository_matches") or []
            has_paper = has_work = has_mlsea = False
            for m in matches:
                if m.get("mlsea_software_uris"):
                    has_mlsea = True
                    mlsea.update(m["mlsea_software_uris"])
                for p in m.get("papers") or []:
                    has_paper = True
                    uri = p["lpwc_paper_uri"]
                    papers.add(uri)
                    if "hasOfficialRepository" in (p.get("repository_relations") or []):
                        official.add(uri)
                    if p.get("soa_work_uri"):
                        has_work = True
                        works.add(p["soa_work_uri"])
                    tasks.update(p.get("tasks") or [])
                    paper_areas.setdefault(uri, set()).update(p.get("research_areas") or [])
            repos_lpwc += bool(matches)
            repos_paper += has_paper
            repos_work += has_work
            repos_mlsea += has_mlsea
            for m in rec.get("github_contributor_soa_matches") or []:
                if m.get("match_status") == "AmbiguousNameMatch":
                    continue
                pairs.setdefault((m["contributor_github_user_id"], m["soa_author_uri"]), m)

    areas = Counter(a for s in paper_areas.values() for a in s)
    strata = Counter(stratum(m) for m in pairs.values())
    published = {k: m for k, m in pairs.items()
                 if m.get("match_type") != "FuzzyNameMatch" or float(m.get("similarity") or 0) >= RDF_FUZZY_THRESHOLD}
    result = {
        "repositories_with_lpwc_match": repos_lpwc, "repositories_with_paper": repos_paper,
        "repositories_with_semopenalex_work": repos_work, "repositories_with_mlsea_link": repos_mlsea,
        "distinct_papers": len(papers), "distinct_papers_with_official_link": len(official),
        "distinct_semopenalex_works": len(works), "distinct_mlsea_software": len(mlsea),
        "distinct_tasks": len(tasks),
        "distinct_papers_with_research_area": sum(1 for s in paper_areas.values() if s),
        "top_research_areas_by_distinct_papers": _top(areas),
        "contributor_author_pairs_by_stratum": dict(sorted(strata.items())),
        "rdf_fuzzy_threshold": RDF_FUZZY_THRESHOLD,
        "published_contributor_author_pairs": len(published),
        "published_distinct_github_accounts": len({k[0] for k in published}),
        "published_distinct_semopenalex_authors": len({k[1] for k in published}),
    }
    if precision:
        # population-weighted estimate on the full data, using the sample's per-stratum precision
        p = {name: s["precision"] for name, s in precision["strata"].items() if s.get("precision") is not None}
        pub_strata = Counter(stratum(m) for m in published.values())
        weight = sum(n for name, n in pub_strata.items() if name in p)
        all_weight = sum(n for name, n in strata.items() if name in p)
        result["estimated_precision_published"] = round(sum(p[k] * n for k, n in pub_strata.items() if k in p) / weight, 3) if weight else None
        result["estimated_precision_all_from_0.60"] = round(sum(p[k] * n for k, n in strata.items() if k in p) / all_weight, 3) if all_weight else None
    return result


def _count_triples(collection_dir: str) -> dict:
    from rdflib import Graph
    counts = {}
    for ttl in sorted(Path(collection_dir).glob("*.ttl")):
        g = Graph()
        g.parse(ttl, format="turtle")
        counts[ttl.name] = len(g)
    return counts


def triple_statistics(rdf_root: Path, workers: int) -> dict:
    by_file: Counter = Counter()
    with ProcessPoolExecutor(max_workers=workers) as pool:
        for counts in pool.map(_count_triples, [str(c) for c in _collections(rdf_root)]):
            by_file.update(counts)
    return {"triples_summed_over_files": sum(by_file.values()), "triples_by_file": dict(sorted(by_file.items()))}


def to_markdown(s: dict) -> str:
    lines = ["# SemRepo v2 — dataset statistics", ""]
    for section, values in s.items():
        if not isinstance(values, dict):
            continue
        lines += [f"## {section}", "", "| Statistic | Value |", "|---|---|"]
        for k, v in values.items():
            if isinstance(v, int):
                v = f"{v:,}"
            elif isinstance(v, (list, dict)):
                v = "; ".join(f"{a.rsplit('/', 1)[-1]}: {b:,}" for a, b in (v.items() if isinstance(v, dict) else v))
            lines.append(f"| {k} | {v} |")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str]) -> None:
    if len(argv) < 3:
        print(__doc__)
        sys.exit(1)
    publish_root, rdf_root, out_dir = Path(argv[0]), Path(argv[1]), Path(argv[2])
    precision = json.loads(Path(argv[argv.index("--precision") + 1]).read_text()) if "--precision" in argv else None
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 1
    cols = _collections(publish_root)

    stats = {
        "repositories": repository_statistics(cols),
        "issues_and_pull_requests": issue_statistics(cols),
        "contributors": contributor_statistics(cols),
        "linking": linking_statistics(cols, precision),
    }
    if "--triples" in argv:
        stats["rdf"] = triple_statistics(rdf_root, workers)
    summary = rdf_root / "rdf-summary.json"
    if summary.exists():
        totals = json.loads(summary.read_text())["totals"]
        stats["v1_vs_v2"] = {
            f"{k} (v1 / v2)": f"{V1[k]:,} / {v:,}" for k, v in {
                "repositories": stats["repositories"]["repositories"],
                # v1 counts persons linked to SemOpenAlex (one link per person); v2 counts one
                # link per repository, contributor and author, so persons are compared
                "github_soa_author_links": stats["linking"]["published_distinct_github_accounts"],
                "issues (hasIssue usages)": stats["issues_and_pull_requests"]["issues_and_pull_requests"],
            }.items() if v is not None}
        # v1 has one hasMlseaUrl link per repository, so it is compared with repositories that have an MLSea link
        stats["v1_vs_v2"]["repositories with an MLSea link (v1 / v2)"] = \
            f"{V1['mlsea_links']:,} / {stats['linking']['repositories_with_mlsea_link']:,}"

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "statistics.json").write_text(json.dumps(stats, indent=2))
    (out_dir / "statistics.md").write_text(to_markdown(stats))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])