"""
WP4.4 -- Thin GitHub REST API client with token rotation and retry/backoff.

This reuses the *design* (not the code) of two things found to be sound in
v1's crawling-gitHub-metadata/main.py during the pipeline audit (see
docs/wp4-pipeline-audit-findings.md): rotating across multiple tokens when
one is rate-limited, and retrying transient failures with backoff. The v1
implementation itself was not reused as-is -- it had hard-coded absolute
paths, no tests, and mixed this logic directly into the crawl loop. This is
a standalone, testable rewrite of the same underlying approach.

An empty tokens list means unauthenticated mode: no Authorization header is
sent, and requests count against GitHub's public 60-requests-per-hour
limit instead of the authenticated 5,000/hour. This is deliberate, not a
missing-credential fallback -- it lets small pilots and local testing run
without anyone needing to hand over a personal access token.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class AllTokensExhaustedError(RuntimeError):
    """Raised when every configured token (or the single unauthenticated
    slot) is rate-limited on the same call."""


@dataclass
class GitHubClient:
    tokens: List[str] = field(default_factory=list)
    api_base_url: str = GITHUB_API_BASE
    request_timeout_seconds: int = 30
    max_retries: int = 5
    retry_backoff_seconds: float = 2.0

    def __post_init__(self) -> None:
        # An empty list is a deliberate "unauthenticated" mode (see module
        # docstring), represented internally as one pseudo-slot with no
        # token to send -- not an error condition.
        self.authenticated = bool(self.tokens)
        self._slots: List[Optional[str]] = list(self.tokens) if self.tokens else [None]
        self._token_index = 0
        self._session = requests.Session()
        retry = Retry(
            total=self.max_retries,
            backoff_factor=self.retry_backoff_seconds,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        self._session.mount("https://", HTTPAdapter(max_retries=retry))

    @classmethod
    def from_env(cls, env_var: str = "SEMREPO_GITHUB_TOKENS", **kwargs) -> "GitHubClient":
        raw = os.environ.get(env_var, "")
        tokens = [t.strip() for t in raw.split(",") if t.strip()]
        if not tokens:
            raise ValueError(f"No tokens found in environment variable {env_var!r}")
        return cls(tokens=tokens, **kwargs)

    @property
    def _current_token(self) -> Optional[str]:
        return self._slots[self._token_index]

    def get(self, path: str) -> requests.Response:
        """GET against the GitHub API, rotating tokens on rate-limit
        responses. `path` may be a full URL or one relative to
        api_base_url. Raises AllTokensExhaustedError only if every
        configured token (or the single unauthenticated slot) is
        rate-limited on this call."""
        url = path if path.startswith("http") else f"{self.api_base_url}{path}"

        tokens_tried = 0
        while tokens_tried < len(self._slots):
            headers = {"Accept": "application/vnd.github+json"}
            if self._current_token:
                headers["Authorization"] = f"Bearer {self._current_token}"
            response = self._session.get(url, headers=headers, timeout=self.request_timeout_seconds)
            tokens_tried += 1

            is_rate_limited = (
                response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0"
            ) or response.status_code == 429

            if not is_rate_limited:
                return response

            logger.warning(
                "Token %d/%d rate-limited, rotating", self._token_index + 1, len(self._slots)
            )
            self._token_index = (self._token_index + 1) % len(self._slots)

        raise AllTokensExhaustedError(f"All {len(self._slots)} token slot(s) are rate-limited for {url}")