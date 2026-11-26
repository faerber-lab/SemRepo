"""
Writes the RDF of every collection as N-Triples (one file per collection),
so that the whole release can be checked with standard command-line tools.

N-Triples has exactly one triple per line, so the number of distinct triples
of the whole release -- what a triple store holds after loading all files into
one graph -- is

    LC_ALL=C sort -u -S 8G -T <tmp dir> <out dir>/*.nt | wc -l

Summing len(graph) over the Turtle files counts a triple once per file it
appears in; triples about resources shared by several collections (papers,
GitHub accounts, programming languages, ...) are repeated in each of them.

Usage:
    python3 src/export_ntriples.py <rdf root> <out dir> [--workers 3]
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from rdflib import Graph


def export_collection(collection_dir: str, out_dir: str) -> dict:
    col = Path(collection_dir)
    out = Path(out_dir) / f"{col.name}.nt"
    triples = 0
    with out.open("w", encoding="utf-8") as f:
        for ttl in sorted(col.glob("*.ttl")):
            g = Graph()
            g.parse(ttl, format="turtle")
            triples += len(g)
            f.write(g.serialize(format="nt"))
    return {"collection": col.name, "triples": triples, "file": out.name}


def main(argv: list[str]) -> None:
    if len(argv) < 2:
        print(__doc__)
        sys.exit(1)
    rdf_root, out_dir = Path(argv[0]), Path(argv[1])
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 1
    out_dir.mkdir(parents=True, exist_ok=True)
    cols = [str(p) for p in sorted(rdf_root.iterdir()) if p.is_dir()]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(export_collection, cols, [str(out_dir)] * len(cols)))
    for r in results:
        print(f"{r['collection']}: {r['triples']:,} triples", flush=True)
    summary = {"collections": len(results), "triples_summed_over_files": sum(r["triples"] for r in results)}
    (out_dir / "export-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main(sys.argv[1:])