"""
WP4.6 -- Serialize the typed records produced by WP4.4/WP4.5's collectors
(resolve_repository.py, collect_repository.py, collect_languages.py,
collect_issues.py, collect_contributors.py) into the JSONL files the
project proposal specifies for this stage.

Named "normalize" per the proposal's WP4.6, but most of the actual
normalization already happens where each record is *created*: every
collect_*.py function returns one of the typed dataclasses from models.py
directly, not a raw untyped dict. What's left here is turning those
dataclasses into JSON safely -- dataclasses.asdict() alone does not know
how to serialize datetime or Enum fields, and most of our models
(CollectionActivity, SourceRepositoryLink, every timestamped record) use
one or both. A single, tested serializer here means every writer in the
pipeline handles this the same way, instead of each call site inventing
its own datetime/Enum-to-JSON logic.

Nothing is silently dropped: dataclasses.asdict() keeps every field,
including ones that are None, and to_json_dict() below does not filter
None values out -- a missing or not-yet-collected value stays visible as
null in the output rather than disappearing from the record entirely
(the WP4.6 proposal spec's "do not silently omit missing values").
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

# Canonical output file names. The first five match the project proposal's
# WP4.6 spec exactly; source_repository_link and collection_activity are
# additions of ours, not in the original proposal list, needed because our
# design tracks resolution outcomes and pipeline provenance as first-class
# records (see docs/wp4-pipeline-audit-findings.md on why that provenance
# tracking matters).
OUTPUT_FILES = {
    "repository": "repositories.jsonl",
    "snapshot": "snapshots.jsonl",
    "issue": "issues.jsonl",
    "contribution": "contributions.jsonl",
    "language_usage": "language-usage.jsonl",
    "source_repository_link": "source-repository-links.jsonl",
    "collection_activity": "collection-activities.jsonl",
}


def _json_safe(value: Any) -> Any:
    """Recursively converts datetime and Enum values into JSON-safe
    equivalents. Everything else passes through unchanged."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


def to_json_dict(record: Any) -> dict:
    """Converts one dataclass instance (any of models.py's types) into a
    plain, JSON-safe dict. Raises TypeError for non-dataclass input --
    this is meant for our typed records, not arbitrary objects."""
    if not is_dataclass(record):
        raise TypeError(f"to_json_dict expects a dataclass instance, got {type(record)!r}")
    return {k: _json_safe(v) for k, v in asdict(record).items()}


def write_jsonl(records: Iterable[Any], output_path: Path, mode: str = "a") -> int:
    """Writes records to a JSONL file, one JSON object per line, and
    returns how many were written. Defaults to append mode: this pipeline
    processes repositories one at a time, and each repository's records
    are added to the same growing files rather than a fresh file per
    repository."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(output_path, mode, encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(to_json_dict(record)) + "\n")
            count += 1
    return count


def write_repository_records(
    output_dir: Path,
    canonical_repository: Optional[Any] = None,
    snapshot: Optional[Any] = None,
    source_repository_link: Optional[Any] = None,
    issues: Optional[list] = None,
    contributions: Optional[list] = None,
    language_usages: Optional[list] = None,
    collection_activities: Optional[list] = None,
) -> Dict[str, int]:
    """Writes every record collected for one repository to its
    corresponding JSONL file under output_dir. All arguments are optional
    -- a repository that failed to resolve has no snapshot or issues at
    all, but its SourceRepositoryLink and CollectionActivity records still
    get written, so the failure itself stays visible in the output rather
    than the repository simply not appearing anywhere.

    Returns {file_key: records_written} for logging/completeness
    reporting."""
    written: Dict[str, int] = {}

    def _write(key: str, records: list) -> None:
        if not records:
            written[key] = 0
            return
        written[key] = write_jsonl(records, output_dir / OUTPUT_FILES[key])

    _write("repository", [canonical_repository] if canonical_repository else [])
    _write("snapshot", [snapshot] if snapshot else [])
    _write("source_repository_link", [source_repository_link] if source_repository_link else [])
    _write("issue", issues or [])
    _write("contribution", contributions or [])
    _write("language_usage", language_usages or [])
    _write("collection_activity", collection_activities or [])

    return written