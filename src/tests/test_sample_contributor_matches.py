"""Tests for sample_contributor_matches.py (evaluation step 9.4)."""

import csv
import json

from sample_contributor_matches import sample, score, stratum


def _match(uid, author, mtype, sim=None):
    return {"contributor_github_user_id": uid, "contributor_github_login": f"user{uid}", "github_name": f"Name {uid}",
            "soa_author_uri": f"https://semopenalex.org/author/{author}", "soa_author_names": [f"N {uid}"],
            "matched_soa_name": f"N {uid}", "match_type": mtype, "similarity": sim}


def _harvest(root):
    col = root / "a"
    col.mkdir(parents=True)
    (col / "_COMPLETE").write_text("x")
    matches = [_match(i, f"A{i}", "FuzzyNameMatch", 0.6 + (i % 40) / 100) for i in range(200)]
    matches += [_match(1000 + i, f"E{i}", "ExactNameMatch", 1.0) for i in range(80)]
    matches += [_match(2000 + i, f"R{i}", "ReversedNameMatch", 1.0) for i in range(10)]
    matches.append(_match(0, "A0", "FuzzyNameMatch", 0.6))     # duplicate (contributor, author) in another repo
    with (col / "external-links.jsonl").open("w") as f:
        for i in range(0, len(matches), 10):
            f.write(json.dumps({"github_repository_url": f"https://github.com/o/r{i}",
                                "github_contributor_soa_matches": matches[i:i + 10]}) + "\n")
    incomplete = root / "b"
    incomplete.mkdir()
    (incomplete / "external-links.jsonl").write_text(json.dumps(
        {"github_contributor_soa_matches": [_match(5000, "X", "ExactNameMatch", 1.0)]}) + "\n")


def test_stratum_bands():
    assert stratum({"match_type": "FuzzyNameMatch", "similarity": 0.6}) == "Fuzzy 0.60-0.70"
    assert stratum({"match_type": "FuzzyNameMatch", "similarity": 0.95}) == "Fuzzy 0.90-1.00"
    assert stratum({"match_type": "ExactNameMatch", "similarity": None}) == "ExactNameMatch"


def test_sample_is_stratified_deduplicated_and_reproducible(tmp_path):
    _harvest(tmp_path / "h")
    out = tmp_path / "eval" / "s.csv"
    pop = sample(tmp_path / "h", out)

    assert pop["total_matches"] == 290                  # duplicate and incomplete collection excluded
    assert pop["sampled"] == {"Fuzzy 0.60-0.70": 25, "Fuzzy 0.70-0.80": 25, "Fuzzy 0.80-0.90": 25,
                              "Fuzzy 0.90-1.00": 25, "ExactNameMatch": 50, "ReversedNameMatch": 10}
    first = out.read_text()
    sample(tmp_path / "h", out)
    assert out.read_text() == first                     # fixed seed


def test_score_reads_semicolon_csv_and_weights_by_population(tmp_path):
    _harvest(tmp_path / "h")
    out = tmp_path / "s.csv"
    sample(tmp_path / "h", out)
    rows = list(csv.DictReader(out.open()))
    for r in rows:   # wrong only in the lowest fuzzy band; one unsure
        r["label"] = "0" if r["stratum"] == "Fuzzy 0.60-0.70" else "1"
    rows[0]["label"] = "?"
    labelled = tmp_path / "s-labelled.csv"
    with labelled.open("w", newline="") as f:          # Excel with a Turkish/German locale saves with ';'
        w = csv.DictWriter(f, fieldnames=rows[0].keys(), delimiter=";")
        w.writeheader()
        w.writerows(rows)

    result = score(labelled)

    assert result["strata"]["Fuzzy 0.60-0.70"]["precision"] == 0.0
    assert result["strata"]["ExactNameMatch"]["precision"] == 1.0
    assert sum(s.get("unsure", 0) for s in result["strata"].values()) == 1
    assert result["match_types"]["FuzzyNameMatch"]["weighted_precision"] == 0.75   # 4 equal bands of 50, one wrong