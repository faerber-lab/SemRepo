"""
WP5.1 -- Stable, deterministic SemRepo v2 URIs for every entity type in the
ontology (ontologies/semrepo-v2.ttl).

Core rule, non-negotiable: the same source entity must always produce the
same URI. Reruns, resumed pipelines (WP4.7's checkpoint/resume), and
future WP6 releases all depend on this holding exactly.

Where GitHub already provides a stable numeric ID (repository, account,
issue), that ID IS the identifier's key -- this is the entire reason
WP4.4 resolves to the numeric ID before doing anything else, rather than
trusting a URL or name that can change (see
docs/wp4-pipeline-audit-findings.md and the proposal's explicit ban on
URL/filename-based deduplication, which v1 used).

For entities with no natural GitHub ID -- Contribution, LanguageUsage,
ExternalLink, SourceRepositoryLink, CollectionActivity, all n-ary relation
nodes or event records in the ontology rather than GitHub-native objects
-- the URI is a deterministic hash of the fields that define that
record's identity. "Deterministic" means exactly that: the same inputs
always hash to the same URI, not randomness with a fixed seed.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

BASE = "https://semrepo.org/resource"


def _stable_hash(*parts: str) -> str:
    """Short, deterministic hex digest from an ordered tuple of string
    parts. Not cryptographic -- it only needs to be stable and
    collision-safe enough to identify pipeline records, not to secure
    anything."""
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def repository_uri(github_repository_id: int) -> str:
    return f"{BASE}/repository/{github_repository_id}"


def github_account_uri(github_user_id: int) -> str:
    """Covers GitHubUser, GitHubOrganisation, and GitHubBot alike -- the
    ontology's three subclasses share one identity space keyed on
    GitHub's numeric account ID, matching WP3's GitHubAccount design."""
    return f"{BASE}/github-account/{github_user_id}"


def issue_uri(github_issue_id: int) -> str:
    """Keyed on GitHub's issue ID, which is globally stable across the
    whole platform -- NOT issueNumber, which only holds within one
    repository (see WP3's Issue design notes)."""
    return f"{BASE}/github-issue/{github_issue_id}"


def programming_language_uri(language_name: str) -> str:
    """One shared URI per language name across the entire dataset -- e.g.
    every repository's "Python" LanguageUsage points at the same
    ProgrammingLanguage node. Case/whitespace-normalized so "Python",
    "python", and " Python " never silently produce three different
    nodes for what is obviously the same language."""
    slug = language_name.strip().lower().replace(" ", "-")
    return f"{BASE}/programming-language/{slug}"


def repository_snapshot_uri(github_repository_id: int, collected_at: datetime) -> str:
    return f"{BASE}/repository-snapshot/{github_repository_id}/{collected_at.isoformat()}"


def contribution_uri(
    github_repository_id: int, collected_at: datetime, contributor_github_user_id: int
) -> str:
    digest = _stable_hash(
        str(github_repository_id), collected_at.isoformat(), str(contributor_github_user_id)
    )
    return f"{BASE}/contribution/{digest}"


def language_usage_uri(github_repository_id: int, collected_at: datetime, language_name: str) -> str:
    digest = _stable_hash(
        str(github_repository_id), collected_at.isoformat(), language_name.strip().lower()
    )
    return f"{BASE}/language-usage/{digest}"


def source_repository_link_uri(original_repository_url: str) -> str:
    """Keyed on the original URL as recorded in LPWC -- that URL is this
    record's natural identity, since the record exists specifically to
    describe what happened when THAT URL was resolved."""
    digest = _stable_hash(original_repository_url)
    return f"{BASE}/source-repository-link/{digest}"


def external_link_uri(link_source_uri: str, target_knowledge_graph: str, link_target: str) -> str:
    digest = _stable_hash(link_source_uri, target_knowledge_graph, link_target)
    return f"{BASE}/external-link/{digest}"


def collection_activity_uri(
    attempted_url: str, collection_timestamp: datetime, collection_source: str
) -> str:
    digest = _stable_hash(attempted_url, collection_timestamp.isoformat(), collection_source)
    return f"{BASE}/collection-activity/{digest}"