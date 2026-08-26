"""Small shared helpers for the src/semrepo/github/* modules."""

from __future__ import annotations

from datetime import datetime


def parse_github_datetime(value: str) -> datetime:
    """GitHub timestamps look like '2011-01-26T19:01:12Z'. Python's
    datetime.fromisoformat() only accepts the 'Z' suffix from 3.11+; this
    project targets >=3.10 (pyproject.toml), so we normalize it by hand."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))