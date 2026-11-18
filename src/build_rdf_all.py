"""
Generates RDF for every collection of the publication copy, one collection
at a time (the whole graph does not fit in memory at once), optionally with
SHACL validation per collection. Re-running skips collections whose RDF
already exists (delete <rdf root>/<collection> to rebuild one).

Usage:
    python3 src/build_rdf_all.py /data/semrepo/publish /data/semrepo/rdf [--validate]
Output: <rdf root>/<collection>/semrepo-*.ttl and <rdf root>/rdf-summary.json
"""

from __future__ import annotations

import json
import sys
import time
from collections import Counter
from pathlib import Path

from generate_rdf_with_linking import generate_rdf

ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print(__doc__)
        sys.exit(1)
    publish_root, rdf_root = Path(argv[0]), Path(argv[1])
    validate = "--validate" in argv
    totals: Counter = Counter()
    report = {}

    for col in sorted(p for p in publish_root.iterdir() if p.is_dir()):
        out = rdf_root / col.name
        done_marker = out / "_RDF_DONE"
        if done_marker.exists():
            report[col.name] = json.loads(done_marker.read_text())
            totals.update(report[col.name]["counts"])
            print(f"{col.name}: already built -- skipped")
            continue
        started = time.monotonic()
        counts = generate_rdf(col, out)
        entry = {"counts": counts, "seconds": round(time.monotonic() - started, 1)}
        if validate:
            from semrepo.validate_rdf import validate_generated_rdf
            conforms, text = validate_generated_rdf(sorted(out.glob("*.ttl")), ROOT / "ontologies/semrepo-v2.ttl",
                                                    ROOT / "ontologies/semrepo-v2-shapes.ttl")
            entry["shacl_conforms"] = conforms
            if not conforms:
                (out / "shacl-report.txt").write_text(text)
        done_marker.write_text(json.dumps(entry))
        report[col.name] = entry
        totals.update(counts)
        print(f"{col.name}: {entry}", flush=True)

    summary = {"totals": dict(totals), "collections": report,
               "all_conform": all(e.get("shacl_conforms", True) for e in report.values())}
    rdf_root.mkdir(parents=True, exist_ok=True)
    (rdf_root / "rdf-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({"totals": summary["totals"], "all_conform": summary["all_conform"]}, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])