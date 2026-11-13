"""
Pilot check for src/linking.py -- runs Yuni's linking functions unchanged
on a harvested pilot folder and measures what they find, without
overwriting external-links.jsonl.

Adds only what a long run needs, from the outside:
- every SPARQL call gets a 60 s timeout and up to 3 attempts;
- a failure on one repository is recorded and the run continues;
- if SemOpenAlex is unreachable, author enrichment is skipped (LPWC and
  MLSea links are still tested) and the summary says so;
- for renamed/transferred repositories it also tries the ORIGINAL URL
  from source-repository-links.jsonl, to measure how many LPWC links the
  canonical-URL lookup misses.

Usage (from the repository root):
    python3 src/linking_check.py data/measure/run1
Output: <folder>/linking-check/results.jsonl and summary.json
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from SPARQLWrapper import JSON, SPARQLWrapper

import linking  # src/linking.py (this script lives next to it)

TIMEOUT_SECONDS = 60
ATTEMPTS = 3
TOTAL_REPOSITORIES = 200_000


def _select(endpoint: str, query: str) -> list[dict]:
    client = SPARQLWrapper(endpoint)
    client.setQuery(query)
    client.setReturnFormat(JSON)
    client.setTimeout(TIMEOUT_SECONDS)
    return client.query().convert()["results"]["bindings"]


def _with_retries(fn, stats: Counter):
    def wrapper(endpoint, query):
        last_error = None
        for attempt in range(ATTEMPTS):
            try:
                stats["sparql_queries"] += 1
                return fn(endpoint, query)
            except Exception as error:  # timeout, connection reset, 5xx ...
                last_error = error
                stats["sparql_retries"] += 1
                time.sleep(5 * (attempt + 1))
        raise last_error
    return wrapper


def _reachable(endpoint: str) -> bool:
    try:
        client = SPARQLWrapper(endpoint)
        client.setQuery("ASK {}")
        client.setReturnFormat(JSON)
        client.setTimeout(15)
        client.query().convert()
        return True
    except Exception:
        return False


def _norm(url: str) -> str:
    u = (url or "").strip().lower().rstrip("/")
    u = u.replace("http://", "https://").replace("://www.", "://")
    return u[:-4] if u.endswith(".git") else u


def main() -> None:
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/measure/run1")
    out_dir = folder / "linking-check"
    out_dir.mkdir(parents=True, exist_ok=True)

    stats: Counter = Counter()
    linking.query_sparql = _with_retries(_select, stats)
    linking.run_select = _with_retries(_select, stats)

    lpwc_up = _reachable(linking.LPWC_ENDPOINT)
    soa_up = _reachable(linking.SOA_ENDPOINT)
    print(f"LPWC reachable: {lpwc_up} | SemOpenAlex reachable: {soa_up}")
    if not lpwc_up:
        sys.exit("LPWC endpoint is not reachable -- nothing to test.")
    if not soa_up:
        print("SemOpenAlex is down: author enrichment and contributor matching are SKIPPED in this run.")
        linking.find_authors_from_soa = lambda endpoint, uri: {
            "author_uri": uri, "author_names": [], "orcid_ids": [], "h_index_values": [],
        }

    repositories = list(linking.read_jsonl(folder / "repositories.jsonl"))
    contributions = list(linking.read_jsonl(folder / "contributions.jsonl"))
    contributors = list(linking.read_jsonl(folder / "contributors.jsonl"))
    source_links = list(linking.read_jsonl(folder / "source-repository-links.jsonl"))

    originals: dict[int, set[str]] = {}
    for link in source_links:
        repo_id = link.get("resolved_repository_github_id")
        if repo_id is not None:
            originals.setdefault(repo_id, set()).add(link["original_repository_url"])

    counts: Counter = Counter()
    match_types: Counter = Counter()
    relations: Counter = Counter()
    start = time.monotonic()

    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as out:
        for repo in repositories:
            repo_id, canonical = repo["github_repository_id"], repo["canonical_url"]
            counts["repositories"] += 1
            record = {"github_repository_id": repo_id, "canonical_url": canonical}
            try:
                result = linking.link_repository(linking.LPWC_ENDPOINT, linking.SOA_ENDPOINT, repo)
                matches, reviews = linking.add_repository_contributor_matches(result, contributions, contributors)
            except Exception as error:
                counts["errors"] += 1
                record.update(status="Error", error=f"{type(error).__name__}: {error}")
                out.write(json.dumps(record) + "\n")
                print(f"{repo_id}: ERROR {type(error).__name__}")
                continue

            record["status"] = result["status"]
            if result["status"] == "RepositoryMatched":
                counts["lpwc_matched"] += 1
                for m in result["lpwc_repository_matches"]:
                    counts["papers"] += len(m["papers"])
                    counts["mlsea_links"] += len(m["mlsea_software_uris"])
                    for paper in m["papers"]:
                        relations.update(paper.get("repository_relations") or [])
            counts["contributor_matches"] += len(matches)
            counts["review_records"] += len(reviews)
            match_types.update(m["match_type"] for m in matches)

            # Finding 2: does the original (LPWC-recorded) URL find what the canonical URL missed?
            other_urls = [u for u in originals.get(repo_id, set()) if _norm(u) != _norm(canonical)]
            if other_urls:
                counts["moved_repositories"] += 1
                record["original_urls"] = other_urls
                if result["status"] != "RepositoryMatched":
                    try:
                        if any(linking.find_lpwc_repository(linking.LPWC_ENDPOINT, u) for u in other_urls):
                            counts["missed_by_canonical_found_by_original"] += 1
                            record["found_by_original_url"] = True
                    except Exception as error:
                        counts["errors"] += 1
                        record["original_lookup_error"] = f"{type(error).__name__}: {error}"

            out.write(json.dumps(record) + "\n")
            print(f"{repo_id}: {result['status']}, {len(matches)} contributor matches")

    elapsed = time.monotonic() - start
    n = max(counts["repositories"], 1)
    summary = {
        "folder": str(folder),
        "endpoints": {"lpwc_reachable": lpwc_up, "semopenalex_reachable": soa_up},
        "counts": dict(counts),
        "lpwc_match_rate": round(counts["lpwc_matched"] / n, 3),
        "paper_relations": dict(relations),
        "contributor_match_types": dict(match_types),
        "sparql": dict(stats),
        "elapsed_seconds": round(elapsed, 1),
        "seconds_per_repository": round(elapsed / n, 2),
        "projection_hours_for_200k_sequential": round(TOTAL_REPOSITORIES * elapsed / n / 3600, 1),
        "note": "Without SemOpenAlex the time per repository is underestimated (no author queries).",
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()