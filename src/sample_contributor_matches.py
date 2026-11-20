"""
Precision check of the GitHub contributor -> SemOpenAlex author matches
(evaluation step 9.4).

1) sample: draws a stratified random sample of the matches for manual
   labelling -- fuzzy matches per similarity band, plus exact and reversed
   matches -- and writes it as a CSV with an empty "label" column.
2) score: reads the labelled CSV and reports precision per stratum and the
   population-weighted precision per match type.

Usage:
    python3 src/sample_contributor_matches.py sample /data/semrepo/full-run /data/semrepo/eval/contributor-match-sample.csv
    python3 src/sample_contributor_matches.py score  /data/semrepo/eval/contributor-match-sample-labelled.csv

Labels: 1 = same person, 0 = different person, ? = cannot decide (excluded
from precision, reported separately). Population sizes are stored in
<csv>.population.json next to the sample, so the scores can be weighted.
"""

from __future__ import annotations

import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

SEED = 42
FUZZY_BANDS = [(0.60, 0.70), (0.70, 0.80), (0.80, 0.90), (0.90, 1.00)]
PER_FUZZY_BAND = 25
PER_TYPE = {"ExactNameMatch": 50, "ReversedNameMatch": 25}
COLUMNS = ["sample_id", "stratum", "match_type", "similarity", "github_login", "github_name",
           "matched_soa_name", "soa_author_names", "github_profile", "soa_author_uri", "repository",
           "label", "note"]


def stratum(match: dict) -> str:
    if match["match_type"] != "FuzzyNameMatch":
        return match["match_type"]
    sim = float(match.get("similarity") or 0)
    for low, high in FUZZY_BANDS:
        if low <= sim < high or (high == 1.00 and sim == 1.00):
            return f"Fuzzy {low:.2f}-{high:.2f}"
    return "Fuzzy other"


def load_matches(harvest_root: Path) -> list[dict]:
    """All contributor matches of linked, completely harvested collections; one per (contributor, author)."""
    seen, matches = set(), []
    for col in sorted(p for p in harvest_root.iterdir() if p.is_dir()):
        path = col / "external-links.jsonl"
        if not (col / "_COMPLETE").exists() or not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                for m in rec.get("github_contributor_soa_matches") or []:
                    key = (m["contributor_github_user_id"], m["soa_author_uri"])
                    if key in seen:
                        continue
                    seen.add(key)
                    matches.append({**m, "repository": rec.get("github_repository_url", "")})
    return matches


def sample(harvest_root: Path, out_csv: Path) -> dict:
    matches = load_matches(harvest_root)
    by_stratum: dict[str, list[dict]] = defaultdict(list)
    for m in matches:
        by_stratum[stratum(m)].append(m)

    rng = random.Random(SEED)
    rows = []
    for name in sorted(by_stratum):
        pool = sorted(by_stratum[name], key=lambda m: (m["contributor_github_user_id"], m["soa_author_uri"]))
        size = PER_FUZZY_BAND if name.startswith("Fuzzy") else PER_TYPE.get(name, 0)
        for m in rng.sample(pool, min(size, len(pool))):
            rows.append({
                "stratum": name, "match_type": m["match_type"],
                "similarity": "" if m.get("similarity") is None else round(float(m["similarity"]), 3),
                "github_login": m.get("contributor_github_login") or "", "github_name": m.get("github_name") or "",
                "matched_soa_name": m.get("matched_soa_name") or "",
                "soa_author_names": " | ".join(m.get("soa_author_names") or []),
                "github_profile": f"https://github.com/{m.get('contributor_github_login') or ''}",
                "soa_author_uri": m["soa_author_uri"], "repository": m["repository"], "label": "", "note": "",
            })
    rng.shuffle(rows)            # mixed order, so the labeller does not see the strata one after another
    for i, r in enumerate(rows, 1):
        r["sample_id"] = i

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    population = {"total_matches": len(matches), "strata": {k: len(v) for k, v in sorted(by_stratum.items())},
                  "sampled": dict(Counter(r["stratum"] for r in rows)), "seed": SEED}
    Path(str(out_csv) + ".population.json").write_text(json.dumps(population, indent=2))
    return population


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return (round(centre - half, 3), round(centre + half, 3))


def _read_labelled(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8-sig")
    dialect = csv.Sniffer().sniff(text.splitlines()[0], delimiters=",;\t")   # Excel/Numbers may save with ';'
    return list(csv.DictReader(text.splitlines(), dialect=dialect))


def score(labelled_csv: Path, population_json: Path | None = None) -> dict:
    rows = _read_labelled(labelled_csv)
    population_json = population_json or Path(str(labelled_csv).replace("-labelled", "") + ".population.json")
    strata_sizes = json.loads(population_json.read_text())["strata"] if population_json.exists() else {}

    per = defaultdict(Counter)
    for r in rows:
        label = (r.get("label") or "").strip()
        per[r["stratum"]]["correct" if label == "1" else "wrong" if label == "0" else
                          "unsure" if label == "?" else "unlabelled"] += 1

    result = {"strata": {}, "match_types": {}}
    for name, c in sorted(per.items()):
        n = c["correct"] + c["wrong"]
        result["strata"][name] = {**c, "precision": round(c["correct"] / n, 3) if n else None,
                                  "wilson_95": _wilson(c["correct"], n), "population": strata_sizes.get(name)}

    # population-weighted precision per match type (fuzzy bands weighted by their size)
    groups = defaultdict(list)
    for name, s in result["strata"].items():
        groups["FuzzyNameMatch" if name.startswith("Fuzzy") else name].append(s)
    for mtype, strata in groups.items():
        usable = [s for s in strata if s["precision"] is not None and s["population"]]
        weight = sum(s["population"] for s in usable)
        result["match_types"][mtype] = {
            "weighted_precision": round(sum(s["precision"] * s["population"] for s in usable) / weight, 3) if weight else None,
            "population": weight,
        }
    return result


def main(argv: list[str]) -> None:
    if len(argv) >= 3 and argv[0] == "sample":
        print(json.dumps(sample(Path(argv[1]), Path(argv[2])), indent=2))
    elif len(argv) >= 2 and argv[0] == "score":
        print(json.dumps(score(Path(argv[1]), Path(argv[2]) if len(argv) > 2 else None), indent=2))
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main(sys.argv[1:])