"""
Builds the publication copy of a full harvest: removes repositories that
were collected in more than one collection (the same GitHub repository can
be linked from papers in several .pkl files) and drops records that belong
to removed duplicates. The raw harvest folders are never changed.

Rule: a repository belongs to the first collection (in sorted order) that
collected it; later copies are dropped. Every source-repository-link
(original URL -> repository) is kept once, so the URL provenance stays
complete; collection activities are all kept (provenance of every API
call). Contributor profiles are written once, in the first collection that
references the account. Language names that differ only in spelling
("MATLAB"/"Matlab") are unified to the most frequent spelling.

Input:  <harvest root>/<collection>/*.jsonl   (only collections with _COMPLETE)
Output: <publish root>/<collection>/*.jsonl  + <publish root>/dedup-summary.json

Usage:
    python3 src/prepare_publication.py /data/semrepo/full-run /data/semrepo/publish
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

FILES = [
    "repositories.jsonl", "snapshots.jsonl", "issues.jsonl", "contributions.jsonl", "contributors.jsonl",
    "language-usage.jsonl", "source-repository-links.jsonl", "collection-activities.jsonl",
    "external-links.jsonl", "github-soa-match-review.jsonl",
]


def _read(path: Path) -> Iterable[dict]:
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def _language_key(name: str) -> str:
    """Same normalization as semrepo.identifiers.programming_language_uri."""
    return name.strip().lower().replace(" ", "-")


def canonical_language_names(collections: list[Path]) -> tuple[dict[str, str], dict[str, dict]]:
    """GitHub sometimes reports one language with different spellings (e.g.
    "MATLAB" and "Matlab"). They share one ProgrammingLanguage node, which must
    have exactly one name. The canonical name is the most frequent spelling over
    the whole harvest (ties: alphabetical), so it is the same in every collection."""
    seen: dict[str, Counter] = {}
    for col in collections:
        for file, field in (("snapshots.jsonl", "primary_language"), ("language-usage.jsonl", "language_name")):
            for rec in _read(col / file):
                name = rec.get(field)
                if name:
                    seen.setdefault(_language_key(name), Counter())[name] += 1
    canonical = {key: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] for key, c in seen.items()}
    unified = {key: {"canonical": canonical[key], "variants": dict(c)} for key, c in seen.items() if len(c) > 1}
    return canonical, unified


def _copy(src: Path, dst: Path, keep: Callable[[dict], bool],
          transform: Optional[Callable[[dict], dict]] = None) -> tuple[int, int]:
    kept = dropped = 0
    with dst.open("w", encoding="utf-8") as out:
        for rec in _read(src):
            if keep(rec):
                if transform:
                    rec = transform(rec)
                out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                kept += 1
            else:
                dropped += 1
    return kept, dropped


def _is_capped(activity: dict) -> bool:
    return activity.get("collection_status") == "PartialSuccess"


def prepare(harvest_root: Path, publish_root: Path, require_complete: bool = True) -> dict:
    collections = sorted(p for p in harvest_root.iterdir() if p.is_dir() and (p / "repositories.jsonl").exists())
    skipped = [p.name for p in collections if require_complete and not (p / "_COMPLETE").exists()]
    collections = [p for p in collections if p.name not in skipped]

    owner: dict[int, str] = {}
    for col in collections:
        for rec in _read(col / "repositories.jsonl"):
            owner.setdefault(rec["github_repository_id"], col.name)

    language_names, languages_unified = canonical_language_names(collections)

    def fix_language(field: str) -> Callable[[dict], dict]:
        def apply(r: dict) -> dict:
            if r.get(field):
                r[field] = language_names.get(_language_key(r[field]), r[field])
            return r
        return apply

    seen_urls: set[str] = set()
    seen_profiles: set[int] = set()
    seen_issues: set[int] = set()
    per_collection = {}
    totals: Counter = Counter()
    capped = Counter()

    for col in collections:
        out = publish_root / col.name
        out.mkdir(parents=True, exist_ok=True)
        mine = lambda rid, name=col.name: owner.get(rid) == name
        c: Counter = Counter()

        def track(key, result):
            c[f"{key}_kept"], c[f"{key}_dropped"] = result

        track("repositories", _copy(col / "repositories.jsonl", out / "repositories.jsonl",
                                    lambda r: mine(r["github_repository_id"])))
        track("snapshots", _copy(col / "snapshots.jsonl", out / "snapshots.jsonl",
                                 lambda r: mine(r["repository_github_id"]), fix_language("primary_language")))

        def keep_issue(r):
            if not mine(r["belongs_to_repository_github_id"]) or r["github_issue_id"] in seen_issues:
                return False
            seen_issues.add(r["github_issue_id"])
            return True
        track("issues", _copy(col / "issues.jsonl", out / "issues.jsonl", keep_issue))

        referenced: set[int] = set()
        def keep_contribution(r):
            if mine(r["repository_github_id"]):
                referenced.add(r["contributor_github_user_id"])
                return True
            return False
        track("contributions", _copy(col / "contributions.jsonl", out / "contributions.jsonl", keep_contribution))

        def keep_profile(r):
            uid = r.get("contributor_github_user_id")
            if uid in referenced and uid not in seen_profiles:
                seen_profiles.add(uid)
                return True
            return False
        track("contributors", _copy(col / "contributors.jsonl", out / "contributors.jsonl", keep_profile))

        track("language_usage", _copy(col / "language-usage.jsonl", out / "language-usage.jsonl",
                                      lambda r: mine(r["repository_github_id"]), fix_language("language_name")))

        def keep_url(r):
            url = r["original_repository_url"]
            if url in seen_urls:
                return False
            seen_urls.add(url)
            return True
        track("source_repository_links", _copy(col / "source-repository-links.jsonl",
                                               out / "source-repository-links.jsonl", keep_url))

        activities = list(_read(col / "collection-activities.jsonl"))
        with (out / "collection-activities.jsonl").open("w", encoding="utf-8") as f:
            for a in activities:
                f.write(json.dumps(a, ensure_ascii=False) + "\n")
                if _is_capped(a) and mine(a.get("resulted_in_repository_github_id")):
                    kind = "issues" if "/issues" in a["attempted_url"] else \
                           "contributors" if "/contributors" in a["attempted_url"] else "other"
                    capped[kind] += 1
        c["collection_activities_kept"] = len(activities)

        track("external_links", _copy(col / "external-links.jsonl", out / "external-links.jsonl",
                                      lambda r: mine(r["github_repository_id"])))
        track("soa_match_reviews", _copy(col / "github-soa-match-review.jsonl",
                                         out / "github-soa-match-review.jsonl",
                                         lambda r: mine(r["github_repository_id"])))
        per_collection[col.name] = dict(c)
        totals.update(c)
        print(f"{col.name}: {c['repositories_kept']} repositories kept, {c['repositories_dropped']} duplicates dropped",
              flush=True)

    summary = {
        "prepared_at": datetime.now(timezone.utc).isoformat(),
        "harvest_root": str(harvest_root),
        "collections": len(collections),
        "collections_skipped_incomplete": skipped,
        "unique_repositories": len(owner),
        "totals": dict(totals),
        "capped_repositories_partial_success": dict(capped),
        "language_names_unified": languages_unified,
        "per_collection": per_collection,
    }
    publish_root.mkdir(parents=True, exist_ok=True)
    (publish_root / "dedup-summary.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    result = prepare(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps({k: v for k, v in result.items() if k != "per_collection"}, indent=2))