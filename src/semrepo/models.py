"""
Typed intermediate data models for the SemRepo v2 pipeline.

These mirror the ontology patterns defined in ontologies/semrepo-v2.ttl and
validated by ontologies/semrepo-v2-shapes.ttl (see docs/wp3-* notes). Field
names deliberately match the ontology property names 1:1 so the eventual
RDF generation step (WP5) is a direct, unambiguous mapping rather than a
second translation layer.

Every record carries provenance/completeness fields where the corresponding
SHACL shape made a field mandatory (e.g. Repository.collection_source),
directly motivated by the WP1 finding that v1 could not trace which code
produced its MLSea links.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# GitHubAccount pattern
# ---------------------------------------------------------------------------

class GitHubAccountType(str, Enum):
    USER = "GitHubUser"
    ORGANISATION = "GitHubOrganisation"
    BOT = "GitHubBot"


@dataclass
class GitHubAccount:
    github_user_id: int
    github_login: str
    account_type: GitHubAccountType
    profile_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Repository / RepositorySnapshot pattern
# ---------------------------------------------------------------------------

@dataclass
class CanonicalRepository:
    """Stable identity only -- mirrors sr:Repository. No mutable fields here;
    see RepositorySnapshot for anything that changes over time (WP3 decision)."""
    github_repository_id: int
    canonical_url: str
    created_at: Optional[datetime] = None


@dataclass
class RepositorySnapshot:
    """One dated observation of a repository's mutable metadata.
    collected_at is mandatory (matches SHACL: minCount 1 on :collectedAt)."""
    repository_github_id: int          # foreign key -> CanonicalRepository.github_repository_id
    collected_at: datetime
    stars_count: Optional[int] = None
    forks_count: Optional[int] = None
    open_issues_count: Optional[int] = None
    description: Optional[str] = None
    archived: Optional[bool] = None


# ---------------------------------------------------------------------------
# ExternalLink pattern
# ---------------------------------------------------------------------------

class LinkSourceType(str, Enum):
    REPOSITORY = "Repository"
    GITHUB_ACCOUNT = "GitHubAccount"


@dataclass
class ExternalLink:
    """Confidence-scored link to an entity in an external KG (SemOpenAlex,
    LPWC, MLSea-KG). link_source_type + link_source_id together stand in for
    the ontology's sh:or constraint (Repository or any GitHubAccount
    subtype) -- there's no single foreign-key column that can span both
    possible target types cleanly."""
    link_target: str                       # external KG entity IRI/URL
    target_knowledge_graph: str
    link_source_type: LinkSourceType
    link_source_id: int                    # github_repository_id or github_user_id, per link_source_type
    link_relation_type: Optional[str] = None
    linking_method: Optional[str] = None
    confidence_score: Optional[float] = None
    link_decision: Optional[str] = None


# ---------------------------------------------------------------------------
# SourceRepositoryLink / ResolutionStatus pattern
# ---------------------------------------------------------------------------

class ResolutionStatus(str, Enum):
    RESOLVED = "Resolved"
    RENAMED = "Renamed"
    TRANSFERRED = "Transferred"
    DELETED = "Deleted"
    PRIVATE = "Private"
    INVALID = "Invalid"
    API_ERROR = "ApiError"


@dataclass
class SourceRepositoryLink:
    """Tracks resolving one LPWC-recorded URL to a canonical Repository."""
    original_repository_url: str
    resolution_status: ResolutionStatus
    final_resolved_url: Optional[str] = None
    resolved_repository_github_id: Optional[int] = None  # set only when actually resolved


# ---------------------------------------------------------------------------
# CollectionActivity / CollectionStatus pattern
# ---------------------------------------------------------------------------

class CollectionStatus(str, Enum):
    SUCCESS = "Success"
    FAILED = "Failed"
    NOT_FOUND = "NotFound"
    RATE_LIMITED = "RateLimited"
    FORBIDDEN = "Forbidden"
    PARTIAL_SUCCESS = "PartialSuccess"


@dataclass
class CollectionActivity:
    """One attempt by the pipeline to fetch/resolve data for a target URL.
    collection_source is mandatory -- directly motivated by the WP1 finding
    that v1's MLSea links could not be traced to the code that produced
    them (see docs/wp4-pipeline-audit-findings.md, Finding 4)."""
    collection_timestamp: datetime
    attempted_url: str
    collection_source: str
    collection_status: CollectionStatus
    resulted_in_repository_github_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Contribution pattern
# ---------------------------------------------------------------------------

@dataclass
class Contribution:
    """A GitHub account's commit contribution to one repository snapshot.
    (repository_github_id, snapshot_collected_at) together identify the
    target snapshot -- snapshots don't get a standalone stable ID until
    WP5's URI generation step."""
    repository_github_id: int
    snapshot_collected_at: datetime
    contributor_github_user_id: int
    commit_count: int


# ---------------------------------------------------------------------------
# LanguageUsage / ProgrammingLanguage pattern
# ---------------------------------------------------------------------------

@dataclass
class ProgrammingLanguage:
    language_name: str


@dataclass
class LanguageUsage:
    """Raw byte count per language, not a precomputed percentage -- see
    docs/wp4-pipeline-audit-findings.md Finding 5: v1 scraped percentage
    chips from repository HTML pages; the GitHub API's /languages endpoint
    gives stable byte counts instead."""
    repository_github_id: int
    snapshot_collected_at: datetime
    language_name: str
    language_bytes: int


# ---------------------------------------------------------------------------
# Issue / PullRequest pattern
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    """Covers both Issue and PullRequest -- is_pull_request distinguishes
    them at this layer; the RDF generation step (WP5) maps this to the
    correct ontology class (:Issue vs :PullRequest) rather than carrying a
    parallel class hierarchy through the normalized pipeline layer."""
    github_issue_id: int
    issue_number: int
    issue_state: str
    issue_created_at: datetime
    belongs_to_repository_github_id: int
    is_pull_request: bool = False
    issue_closed_at: Optional[datetime] = None