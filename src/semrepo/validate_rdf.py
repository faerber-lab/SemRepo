"""
WP5.6 -- Validate freshly generated RDF (src/semrepo/generate_rdf.py's
output) against the v2 ontology's SHACL shapes
(ontologies/semrepo-v2-shapes.ttl), the same shapes independently verified
in WP3 against synthetic data. This is the first time those shapes are
run against real pipeline output rather than hand-written test fixtures.

Wrapped as an importable, testable function rather than a one-off CLI
command so this check can be part of the same automated-testing
discipline as the rest of the pipeline (WP4.7's "don't rely on manual
steps" spirit), and so it can be re-run identically every time a new
sample is generated for review.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from pyshacl import validate as pyshacl_validate
from rdflib import Graph


def validate_generated_rdf(
    rdf_files: List[Path],
    ontology_path: Path,
    shapes_path: Path,
) -> Tuple[bool, str]:
    """Loads all rdf_files plus the ontology into one data graph, validates
    it against shapes_path, and returns (conforms, human_readable_report).
    The ontology is included in the data graph because some individuals
    referenced by generated data (:Resolved, :Success, and the other
    ResolutionStatus/CollectionStatus individuals) are only defined there,
    not in the generated instance data itself."""
    data_graph = Graph()
    for path in rdf_files:
        data_graph.parse(path, format="turtle")
    data_graph.parse(ontology_path, format="turtle")

    shapes_graph = Graph()
    shapes_graph.parse(shapes_path, format="turtle")

    conforms, _results_graph, results_text = pyshacl_validate(
        data_graph, shacl_graph=shapes_graph, inference=None
    )
    return conforms, results_text


if __name__ == "__main__":
    import sys

    rdf_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/rdf")
    ontology_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("ontologies/semrepo-v2.ttl")
    shapes_path = Path(sys.argv[3]) if len(sys.argv) > 3 else Path("ontologies/semrepo-v2-shapes.ttl")

    rdf_files = sorted(rdf_dir.glob("*.ttl"))
    if not rdf_files:
        print(f"No .ttl files found in {rdf_dir}")
        sys.exit(1)

    conforms, report = validate_generated_rdf(rdf_files, ontology_path, shapes_path)
    print(report)
    sys.exit(0 if conforms else 1)