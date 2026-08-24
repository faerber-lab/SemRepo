"""
WP4.2 -- Extract GitHub repository URLs from LPWC (Linked Papers With Code),
paired with their source paper for provenance.

This module did not exist anywhere in the v1 codebase (see
docs/wp4-pipeline-audit-findings.md, Finding 7) and had to be built from
scratch.

It also fixes the O(repos x lpwc_lines) performance problem found in v1's
Connect_to_LPWC_and_SOA/main.py (Finding 4): instead of re-scanning the LPWC
file from disk once per repository, this module builds two in-memory
indexes in a single pass over the file, then joins them.

LPWC triple patterns relied on (confirmed by reading v1's
Connect_to_LPWC_and_SOA/main.py, the only place these predicates were
previously used):

    <paper_entity>      <https://linkedpaperswithcode.com/property/hasOfficialRepository>  <lpwc_repo_entity> .
    <lpwc_repo_entity>  <http://purl.org/spar/fabio/hasURL>                                <github_repo_url>  .

Output schema matches the project proposal's WP4.2 spec exactly:
lpwc_entity, paper_entity, original_repository_url, source_release,
extraction_timestamp -- written as JSONL to
data/intermediate/lpwc_repository_links.jsonl.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

HAS_OFFICIAL_REPOSITORY = "https://linkedpaperswithcode.com/property/hasOfficialRepository"
FABIO_HAS_URL = "http://purl.org/spar/fabio/hasURL"

# Lightweight N-Triples line parser. Handles both
#   <s> <p> <o> .
# and
#   <s> <p> "literal"[^^<datatype>|@lang] .
# forms. No external RDF library needed for a single streaming pass over a
# potentially large (multi-GB) file -- rdflib's full parser is unnecessary
# overhead here since we only need two predicates.
_NTRIPLES_LINE = re.compile(
    r'^<([^>]*)>\s+<([^>]*)>\s+(?:<([^>]*)>|"((?:[^"\\]|\\.)*)"[^.]*)\s*\.\s*$'
)


@dataclass
class LpwcRepositoryLink:
    lpwc_entity: str
    paper_entity: str
    original_repository_url: str
    source_release: str
    extraction_timestamp: str


def _parse_ntriples_line(line: str) -> Optional[Tuple[str, str, str]]:
    """Returns (subject, predicate, object_iri) for one N-Triples line, or
    None if the line doesn't match or its object is a literal (irrelevant
    for the two IRI-valued predicates this module cares about)."""
    match = _NTRIPLES_LINE.match(line.strip())
    if not match:
        return None
    subject, predicate, obj_iri, _obj_literal = match.groups()
    if obj_iri is None:
        return None
    return subject, predicate, obj_iri


def _build_indexes(lpwc_path: Path) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """Single pass over the LPWC dump.

    Returns:
        repo_entity_to_url: lpwc_repo_entity IRI -> GitHub URL
        paper_to_repo_entities: paper_entity IRI -> [lpwc_repo_entity IRI, ...]
    """
    repo_entity_to_url: Dict[str, str] = {}
    paper_to_repo_entities: Dict[str, List[str]] = {}

    lines_scanned = 0
    with open(lpwc_path, "r", encoding="utf-8") as f:
        for line in f:
            lines_scanned += 1
            parsed = _parse_ntriples_line(line)
            if parsed is None:
                continue
            subject, predicate, obj = parsed

            if predicate == FABIO_HAS_URL:
                repo_entity_to_url[subject] = obj
            elif predicate == HAS_OFFICIAL_REPOSITORY:
                paper_to_repo_entities.setdefault(subject, []).append(obj)

    logger.info(
        "Scanned %d lines: %d repo-URL triples, %d paper-repository links",
        lines_scanned,
        len(repo_entity_to_url),
        sum(len(v) for v in paper_to_repo_entities.values()),
    )
    return repo_entity_to_url, paper_to_repo_entities


def extract_lpwc_repository_links(
    lpwc_path: Path,
    source_release: str,
) -> Iterator[LpwcRepositoryLink]:
    """Joins the two indexes built from a single pass over the LPWC dump
    and yields one LpwcRepositoryLink per (paper, repository) pair that has
    a resolvable GitHub URL."""
    repo_entity_to_url, paper_to_repo_entities = _build_indexes(lpwc_path)
    extraction_timestamp = datetime.now(timezone.utc).isoformat()

    unresolved_count = 0
    for paper_entity, repo_entities in paper_to_repo_entities.items():
        for repo_entity in repo_entities:
            github_url = repo_entity_to_url.get(repo_entity)
            if github_url is None:
                unresolved_count += 1
                continue
            yield LpwcRepositoryLink(
                lpwc_entity=repo_entity,
                paper_entity=paper_entity,
                original_repository_url=github_url,
                source_release=source_release,
                extraction_timestamp=extraction_timestamp,
            )

    if unresolved_count:
        logger.warning(
            "%d paper-repository links pointed at an LPWC repo entity with "
            "no matching fabio:hasURL triple -- skipped, not silently dropped",
            unresolved_count,
        )


def run(lpwc_path: Path, source_release: str, output_path: Path) -> int:
    """Writes results as JSONL. Returns the number of records written."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(output_path, "w", encoding="utf-8") as out:
        for link in extract_lpwc_repository_links(lpwc_path, source_release):
            out.write(json.dumps(asdict(link)) + "\n")
            count += 1
    logger.info("Wrote %d LPWC repository links to %s", count, output_path)
    return count


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(
        description="Extract GitHub repository URLs from an LPWC N-Triples dump."
    )
    parser.add_argument("--lpwc-path", type=Path, required=True)
    parser.add_argument("--source-release", type=str, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("data/intermediate/lpwc_repository_links.jsonl")
    )
    args = parser.parse_args()

    written = run(args.lpwc_path, args.source_release, args.output)
    sys.exit(0 if written > 0 else 1)


if __name__ == "__main__":
    main()