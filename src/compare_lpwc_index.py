"""
Checks the local LPWC index (lpwc_index.py) against the live LPWC SPARQL
endpoint, on repositories that were already harvested.

For each repository (up to N), it asks:
- live:  the queries linking.py uses today (current/canonical URL only);
- local: the index, with the canonical URL and with the original URLs
         from source-repository-links.jsonl (renamed/transferred repos).

Live "papers" include reference nodes and dataloaders; for a fair
comparison reference nodes are mapped to their paper
(repositoryreferences/<paper-slug>/... -> paper/<paper-slug>) and
dataloaders are counted separately.

Usage:
    python3 src/compare_lpwc_index.py /data/semrepo/lpwc/lpwc-index.sqlite /data/semrepo/full-run/10001_15000 50
Output: <folder>/lpwc-index-check.json (+ printed summary)
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

import linking
from lpwc_index import LpwcIndex, normalize_repo_url

L = "https://linkedpaperswithcode.com/"


def _retry(fn, *args, attempts=3):
    for attempt in range(attempts):
        try:
            return fn(*args)
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(5 * (attempt + 1))


def _paper_of(live_subject: str):
    """Maps a live 'paper' result to (kind, paper IRI)."""
    if live_subject.startswith(L + "paper/"):
        return "paper", live_subject
    if live_subject.startswith(L + "repositoryreferences/"):
        slug = live_subject[len(L + "repositoryreferences/"):].split("/")[0]
        return "reference_node", L + "paper/" + slug
    if live_subject.startswith(L + "dataloader/"):
        return "dataloader", None
    return "other", None


def _read_jsonl(path: Path):
    if path.exists():
        for line in path.open(encoding="utf-8"):
            if line.strip():
                yield json.loads(line)


def main(db: str, folder: str, limit: int) -> None:
    folder_path = Path(folder)
    index = LpwcIndex(Path(db))
    repos = list(_read_jsonl(folder_path / "repositories.jsonl"))[:limit]
    originals = {}
    for link in _read_jsonl(folder_path / "source-repository-links.jsonl"):
        if link.get("resolved_repository_github_id") is not None:
            originals.setdefault(link["resolved_repository_github_id"], set()).add(link["original_repository_url"])

    c = Counter()
    live_kinds = Counter()
    examples = []
    started = time.monotonic()

    for repo in repos:
        rid, url = repo["github_repository_id"], repo["canonical_url"]
        c["repositories"] += 1
        try:
            live_repos = _retry(linking.find_lpwc_repository, linking.LPWC_ENDPOINT, url)
            live_papers = set()
            for match in live_repos:
                for row in _retry(linking.find_papers_for_repository, linking.LPWC_ENDPOINT, match["lpwc_repository_uri"]):
                    kind, paper = _paper_of(row["lpwc_paper_uri"])
                    live_kinds[kind] += 1
                    if paper:
                        live_papers.add(paper)
        except Exception as error:
            c["live_errors"] += 1
            print(f"{rid}: live error {type(error).__name__}")
            continue

        local_canonical = index.find_repositories(url)
        other_urls = {u for u in originals.get(rid, set()) if normalize_repo_url(u) != normalize_repo_url(url)}
        local_any = {r["repo_iri"]: r for r in local_canonical}
        for u in other_urls:
            local_any.update({r["repo_iri"]: r for r in index.find_repositories(u)})
        local_papers = {p["paper_iri"] for iri in local_any for p in index.papers_for_repository(iri)}

        c["live_found"] += bool(live_repos)
        c["local_found_canonical"] += bool(local_canonical)
        c["local_found_any_url"] += bool(local_any)
        if bool(live_repos) != bool(local_canonical):
            c["repo_match_disagreement"] += 1
            examples.append({"repo": url, "live": bool(live_repos), "local": bool(local_canonical)})
        if live_repos and local_canonical:
            c["both_found"] += 1
            if live_papers == local_papers:
                c["same_papers"] += 1
            else:
                c["different_papers"] += 1
                if len(examples) < 10:
                    examples.append({"repo": url, "only_live": sorted(live_papers - local_papers)[:5],
                                     "only_local": sorted(local_papers - live_papers)[:5]})
        print(f"{rid}: live={bool(live_repos)} local={bool(local_canonical)} local_any={bool(local_any)} "
              f"papers live/local={len(live_papers)}/{len(local_papers)}")

    summary = {
        "index": index.meta(),
        "folder": str(folder_path),
        "counts": dict(c),
        "live_subject_kinds": dict(live_kinds),
        "examples": examples,
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    (folder_path / "lpwc-index-check.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "index"}, indent=2))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 50)