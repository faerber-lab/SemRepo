"""
Generates RDF for every collection of the publication copy, per collection
(the whole graph does not fit in memory at once; --workers N builds N in parallel), optionally with
SHACL validation per collection. Re-running skips collections whose RDF
already exists (delete <rdf root>/<collection> to rebuild one).

Usage:
    python3 src/build_rdf_all.py /data/semrepo/publish /data/semrepo/rdf [--validate] [--workers N]
Output: <rdf root>/<collection>/semrepo-*.ttl and <rdf root>/rdf-summary.json
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from generate_rdf_with_linking import RDF_FUZZY_THRESHOLD, generate_rdf

ROOT = Path(__file__).resolve().parents[1]


def build_collection(col: Path, out: Path, validate: bool) -> dict:
    """Generates (and optionally validates) one collection; writes the _RDF_DONE marker."""
    started = time.monotonic()
    counts = generate_rdf(col, out)
    entry = {"counts": counts, "seconds": round(time.monotonic() - started, 1)}
    if validate:
        from semrepo.validate_rdf import validate_generated_rdf
        started = time.monotonic()
        conforms, text = validate_generated_rdf(sorted(out.glob("*.ttl")), ROOT / "ontologies/semrepo-v2.ttl",
                                                ROOT / "ontologies/semrepo-v2-shapes.ttl")
        entry["validation_seconds"] = round(time.monotonic() - started, 1)
        entry["shacl_conforms"] = conforms
        if not conforms:
            (out / "shacl-report.txt").write_text(text)
    (out / "_RDF_DONE").write_text(json.dumps(entry))
    return entry


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print(__doc__)
        sys.exit(1)
    publish_root, rdf_root = Path(argv[0]), Path(argv[1])
    validate = "--validate" in argv
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 1
    totals: Counter = Counter()
    report = {}
    started = time.monotonic()

    pending = []
    for col in sorted(p for p in publish_root.iterdir() if p.is_dir()):
        done_marker = rdf_root / col.name / "_RDF_DONE"
        if done_marker.exists():
            report[col.name] = json.loads(done_marker.read_text())
            print(f"{col.name}: already built -- skipped")
        else:
            pending.append(col)

    # each worker holds one collection graph in memory (~3 GB during validation)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(build_collection, col, rdf_root / col.name, validate): col for col in pending}
        for future in as_completed(futures):
            col = futures[future]
            report[col.name] = future.result()
            print(f"{col.name}: {report[col.name]}", flush=True)

    for entry in report.values():
        totals.update(entry["counts"])
    summary = {"rdf_fuzzy_threshold": RDF_FUZZY_THRESHOLD, "workers": workers,
               "wall_clock_minutes_this_run": round((time.monotonic() - started) / 60, 1),
               "totals": dict(totals), "collections": dict(sorted(report.items())),
               "all_conform": all(e.get("shacl_conforms", True) for e in report.values())}
    rdf_root.mkdir(parents=True, exist_ok=True)
    (rdf_root / "rdf-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({"totals": summary["totals"], "all_conform": summary["all_conform"],
                      "wall_clock_minutes_this_run": summary["wall_clock_minutes_this_run"]}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])