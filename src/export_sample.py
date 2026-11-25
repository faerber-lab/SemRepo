"""
Exports a small, complete sample of the release for the repository: for each
selected repository, all of its JSONL records (input) and the RDF generated
from them (output), validated with SHACL.

The repositories are chosen to cover the main cases of the pipeline (one per
criterion, reproducible with a fixed seed). E-mail addresses are removed from
the JSONL, as in the published RDF.

Usage:
    python3 src/export_sample.py <publish root> <output dir>
Output:
    <output dir>/<owner>__<repo>/jsonl/*.jsonl
    <output dir>/<owner>__<repo>/rdf/*.ttl
    <output dir>/README.md   (which repository shows what)
"""

from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Iterator

from generate_rdf_with_linking import RDF_FUZZY_THRESHOLD, generate_rdf

ROOT = Path(__file__).resolve().parents[1]
SEED = 42
MAX_ISSUES_FOR_SMALL = 300      # keeps the sample small unless a criterion needs a large repository

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")

# file name -> field holding the repository id
REPO_FILES = {
    "repositories.jsonl": "github_repository_id",
    "snapshots.jsonl": "repository_github_id",
    "issues.jsonl": "belongs_to_repository_github_id",
    "contributions.jsonl": "repository_github_id",
    "language-usage.jsonl": "repository_github_id",
    "source-repository-links.jsonl": "resolved_repository_github_id",
    "collection-activities.jsonl": "resulted_in_repository_github_id",
    "external-links.jsonl": "github_repository_id",
    "github-soa-match-review.jsonl": "github_repository_id",
}


def _read(path: Path) -> Iterator[dict]:
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def scrub(value):
    """Removes e-mail addresses (fields named 'email' and addresses inside text)."""
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items() if k.lower() != "email"}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return _EMAIL.sub("[email removed]", value)
    return value


def repository_features(cols: list[Path]) -> dict[int, dict]:
    f: dict[int, dict] = defaultdict(lambda: Counter())
    for c in cols:
        for r in _read(c / "repositories.jsonl"):
            f[r["github_repository_id"]]["collection"] = c.name
            f[r["github_repository_id"]]["url"] = r.get("canonical_url") or ""
        for r in _read(c / "source-repository-links.jsonl"):
            if r.get("resolution_status") in ("Renamed", "Transferred") and r.get("resolved_repository_github_id"):
                f[r["resolved_repository_github_id"]]["renamed_or_transferred"] = 1
        for a in _read(c / "collection-activities.jsonl"):
            if a.get("collection_status") == "PartialSuccess" and a.get("resulted_in_repository_github_id"):
                kind = "issue_cap" if "/issues" in a.get("attempted_url", "") else \
                       "contributor_cap" if "/contributors" in a.get("attempted_url", "") else "other_cap"
                f[a["resulted_in_repository_github_id"]][kind] = 1
        for r in _read(c / "issues.jsonl"):
            x = f[r["belongs_to_repository_github_id"]]
            x["issues"] += 1
            x["prs"] += bool(r.get("is_pull_request"))
            x["bot_authored"] += r.get("issue_author_type") == "Bot"
        for r in _read(c / "external-links.jsonl"):
            x = f[r["github_repository_id"]]
            matches = r.get("lpwc_repository_matches") or []
            x["no_lpwc_match"] = int(not matches)
            for m in matches:
                x["mlsea"] += len(m.get("mlsea_software_uris") or [])
                for p in m.get("papers") or []:
                    x["papers"] += 1
                    rel = p.get("repository_relations") or []
                    x["official"] += "hasOfficialRepository" in rel
                    x["referenced"] += any(r_ != "hasOfficialRepository" for r_ in rel)
                    x["soa_work"] += bool(p.get("soa_work_uri"))
                    x["research_area"] += bool(p.get("research_areas"))
            for m in r.get("github_contributor_soa_matches") or []:
                if m.get("match_status") == "AmbiguousNameMatch":
                    continue
                fuzzy = m.get("match_type") == "FuzzyNameMatch"
                if fuzzy and float(m.get("similarity") or 0) < RDF_FUZZY_THRESHOLD:
                    x["fuzzy_below_threshold"] += 1
                else:
                    x["author_match"] += 1
    return {k: v for k, v in f.items() if "collection" in v}


def _small(x) -> bool:
    return x["issues"] <= MAX_ISSUES_FOR_SMALL


# (criterion shown in the README, test on the features)
CRITERIA: list[tuple[str, Callable[[Counter], bool]]] = [
    ("Official implementation of a paper, linked to a SemOpenAlex work and to MLSea",
     lambda x: x["official"] and x["soa_work"] and x["mlsea"] and _small(x)),
    ("Repository renamed or transferred since the paper (resolved via redirect)",
     lambda x: x["renamed_or_transferred"] and x["papers"] and _small(x)),
    ("Contributor matched to a SemOpenAlex author (published link)",
     lambda x: x["author_match"] and _small(x)),
    ("Fuzzy contributor match below the RDF threshold (kept in JSONL, not published in RDF)",
     lambda x: x["fuzzy_below_threshold"] and _small(x)),
    ("Issues and pull requests, including bot-authored ones",
     lambda x: x["bot_authored"] and x["prs"] and x["issues"] > x["prs"] and _small(x)),
    ("Several linked papers (official and referencing)",
     lambda x: x["official"] and x["referenced"] and x["papers"] >= 3 and _small(x)),
    ("Linked papers with LPWC tasks and research areas",
     lambda x: x["research_area"] and _small(x)),
    ("Issue cap reached (1,000 issues and pull requests)",
     lambda x: x["issue_cap"]),
    ("Contributor cap reached (100 contributors)",
     lambda x: x["contributor_cap"] and not x["issue_cap"]),
    ("No LPWC match for the resolved repository",
     lambda x: x["no_lpwc_match"] and _small(x)),
]


def select(features: dict[int, dict]) -> list[tuple[int, str]]:
    rng = random.Random(SEED)
    chosen: list[tuple[int, str]] = []
    for label, test in CRITERIA:
        pool = sorted(rid for rid, x in features.items() if test(x) and rid not in {c for c, _ in chosen})
        if pool:
            chosen.append((rng.choice(pool), label))
    return chosen


def _folder_name(url: str, rid: int) -> str:
    parts = url.rstrip("/").split("/")[-2:]
    return "__".join(parts) if len(parts) == 2 and all(parts) else f"repository-{rid}"


def export(publish_root: Path, out_root: Path) -> list[dict]:
    cols = sorted(p for p in publish_root.iterdir() if p.is_dir())
    features = repository_features(cols)
    chosen = select(features)
    report = []
    for rid, label in chosen:
        x = features[rid]
        col = publish_root / x["collection"]
        folder = out_root / _folder_name(x["url"], rid)
        jsonl = folder / "jsonl"
        jsonl.mkdir(parents=True, exist_ok=True)

        contributors: set[int] = set()
        for name, field in REPO_FILES.items():
            with (jsonl / name).open("w", encoding="utf-8") as f:
                for r in _read(col / name):
                    if r.get(field) == rid:
                        f.write(json.dumps(scrub(r), ensure_ascii=False) + "\n")
                        if name == "contributions.jsonl":
                            contributors.add(r["contributor_github_user_id"])
        # a profile is published once, in the first collection that references the account
        with (jsonl / "contributors.jsonl").open("w", encoding="utf-8") as f:
            found: set[int] = set()
            for c in cols:
                for r in _read(c / "contributors.jsonl"):
                    uid = r.get("contributor_github_user_id")
                    if uid in contributors and uid not in found:
                        found.add(uid)
                        f.write(json.dumps(scrub(r), ensure_ascii=False) + "\n")

        counts = generate_rdf(jsonl, folder / "rdf")
        from semrepo.validate_rdf import validate_generated_rdf
        conforms, text = validate_generated_rdf(sorted((folder / "rdf").glob("*.ttl")),
                                                ROOT / "ontologies/semrepo-v2.ttl",
                                                ROOT / "ontologies/semrepo-v2-shapes.ttl")
        if not conforms:
            (folder / "shacl-report.txt").write_text(text)
        report.append({"folder": folder.name, "url": x["url"], "shows": label, "issues_and_prs": x["issues"],
                       "papers": x["papers"], "shacl_conforms": conforms, "counts": counts})

    lines = ["# SemRepo v2 — sample data", "",
             "Complete input and output for a few repositories of the release: the JSONL records",
             "collected and linked by the pipeline (`jsonl/`) and the RDF generated from them (`rdf/`).",
             "The repositories were chosen to cover the main cases of the pipeline.",
             "E-mail addresses are removed. Regenerate the RDF of one repository with:", "",
             "```bash", "python3 src/generate_rdf_with_linking.py sample-data/<folder>/jsonl <output dir>", "```", "",
             "| Repository | Shows | Issues + PRs | Linked papers | SHACL |", "|---|---|---|---|---|"]
    for r in report:
        lines.append(f"| [{r['folder']}]({r['url']}) | {r['shows']} | {r['issues_and_prs']:,} | {r['papers']} | "
                     f"{'conforms' if r['shacl_conforms'] else 'see shacl-report.txt'} |")
    (out_root / "README.md").write_text("\n".join(lines) + "\n")
    return report


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print(__doc__)
        sys.exit(1)
    report = export(Path(argv[0]), Path(argv[1]))
    for r in report:
        print(f"{r['folder']}: {r['shows']} | issues+PRs {r['issues_and_prs']} | papers {r['papers']} | "
              f"SHACL {r['shacl_conforms']}")


if __name__ == "__main__":
    main(sys.argv[1:])