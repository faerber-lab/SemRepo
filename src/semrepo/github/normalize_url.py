"""
WP4.3 -- Normalize raw GitHub repository URLs (as extracted from LPWC) into
a canonical owner/repo form, without making any network calls.

This is a full rewrite, not a reuse of v1's get_repo_name_username()
(crawling-gitHub-metadata/modules/crawler.py): that function was regex-only
with no handling of scheme/www variants, trailing slashes, .git suffixes,
query strings, fragments, or GitHub's own reserved top-level paths -- see
docs/current-file-inventory.csv and docs/wp4-pipeline-audit-findings.md.

Deliberately offline-testable: normalization is pure string/URL parsing.
Anything that needs the network (redirect following, existence checks,
canonical ID lookup) belongs in resolve_repository.py, not here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional
from urllib.parse import urlparse

# GitHub reserves these as top-level path segments for its own site
# sections -- a URL like github.com/marketplace/actions/foo LOOKS like
# owner=marketplace, repo=actions but is not a repository at all. Catching
# this here avoids wasting a GitHub API call (and rate-limit budget) in
# resolve_repository.py only to get a misleading 404/wrong-entity result.
# Not exhaustive -- extend as new false positives are found in practice.
_RESERVED_TOP_LEVEL_PATHS = {
    "marketplace", "settings", "notifications", "orgs", "sponsors",
    "topics", "collections", "trending", "explore", "issues", "pulls",
    "codespaces", "search", "about", "pricing", "features", "security",
    "contact", "site", "apps", "login", "join", "logout", "dashboard",
    "new", "organizations",
}

# GitHub usernames/org names: alphanumeric + single hyphens, no leading/
# trailing hyphen. Repo names: alphanumeric, hyphen, underscore, dot.
# Slightly permissive on purpose -- we'd rather pass a borderline-valid
# name through to the API (which will reject it authoritatively) than
# silently drop a real repository due to an overly strict local regex.
_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?$")
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class ParseStatus(str, Enum):
    OK = "ok"
    NOT_GITHUB = "not_github"
    MALFORMED = "malformed"


@dataclass
class NormalizedUrl:
    original_url: str
    normalized_candidate_url: Optional[str]
    parse_status: ParseStatus
    error_reason: Optional[str] = None


def normalize_github_url(raw_url: str) -> NormalizedUrl:
    """Normalizes one raw URL string into a canonical
    https://github.com/{owner}/{repo} form, or explains why it couldn't."""
    original_url = raw_url
    candidate = raw_url.strip()

    if not candidate:
        return NormalizedUrl(original_url, None, ParseStatus.MALFORMED, "empty URL")

    # Be lenient about missing scheme (LPWC data sometimes has bare
    # "github.com/owner/repo" entries) -- try adding https:// once.
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", candidate):
        candidate = "https://" + candidate

    try:
        parsed = urlparse(candidate)
    except ValueError as e:
        return NormalizedUrl(original_url, None, ParseStatus.MALFORMED, f"URL parse error: {e}")

    if parsed.scheme not in ("http", "https"):
        return NormalizedUrl(original_url, None, ParseStatus.MALFORMED, f"unsupported scheme: {parsed.scheme!r}")

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[len("www."):]
    if host != "github.com":
        return NormalizedUrl(original_url, None, ParseStatus.NOT_GITHUB, f"host is {parsed.netloc!r}, not github.com")

    # Path only -- query strings and fragments are discarded, they don't
    # affect repository identity.
    path = parsed.path.strip("/")
    if not path:
        return NormalizedUrl(original_url, None, ParseStatus.MALFORMED, "no path after github.com")

    segments = path.split("/")
    if len(segments) < 2:
        return NormalizedUrl(original_url, None, ParseStatus.MALFORMED, "path has fewer than 2 segments (need owner/repo)")

    owner, repo = segments[0], segments[1]

    if owner.lower() in _RESERVED_TOP_LEVEL_PATHS:
        return NormalizedUrl(original_url, None, ParseStatus.NOT_GITHUB, f"{owner!r} is a reserved GitHub path, not a username/org")

    # Strip a trailing .git suffix on the repo segment, e.g. "foo.git" -> "foo"
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]

    if not repo:
        return NormalizedUrl(original_url, None, ParseStatus.MALFORMED, "empty repository name after stripping .git")

    if not _OWNER_RE.match(owner):
        return NormalizedUrl(original_url, None, ParseStatus.MALFORMED, f"owner {owner!r} has invalid characters")
    if not _REPO_RE.match(repo):
        return NormalizedUrl(original_url, None, ParseStatus.MALFORMED, f"repo name {repo!r} has invalid characters")

    # Any remaining segments (issues/123, tree/main, blob/main/file.py,
    # releases/tag/v1, ...) are intentionally discarded -- WP2 scoped the
    # unit of interest to the repository itself, not its sub-resources.
    normalized = f"https://github.com/{owner}/{repo}"
    return NormalizedUrl(original_url, normalized, ParseStatus.OK)