"""
Full-scale GitHub harvest for SemRepo v2.

Runs the normal pipeline (semrepo.pipeline.run_pipeline) over every .pkl URL
collection in an input folder, with what a multi-day run needs:

- authenticated requests, with several tokens (SEMREPO_GITHUB_TOKENS,
  comma-separated; tokens of different GitHub users add up);
- the caps agreed with Michael (default: 1,000 issues+PRs and
  100 contributors per repository; capped repositories are recorded as
  PartialSuccess in collection-activities.jsonl);
- rate-limit waiting: when every token is close to its limit, the run
  sleeps until the earliest reset instead of recording failures;
- parallel processes, one .pkl collection per process;
- resume: re-running the same command skips finished collections and
  already processed URLs (checkpoint/resume of run_pipeline);
- progress files per collection (progress.json) and one log file each.

Output layout (same as harvest_github_metadata.py):
    <output>/<collection>/repositories.jsonl, snapshots.jsonl, ...
    <output>/<collection>/progress.json
    <output>/<collection>/_COMPLETE          (written when a collection is done)
    <output>/logs/<collection>.log
    <output>/run-summary.json

Usage (from the repository root):
    export SEMREPO_GITHUB_TOKENS=tok1,tok2,tok3
    python3 src/run_full_harvest.py src/data/github_urls data/full-run --workers 3

    # quick smoke test: 5 URLs from one collection
    python3 src/run_full_harvest.py src/data/github_urls data/smoke --only 1_5000.pkl --limit-per-collection 5
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pickle
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, List, Optional

TOKENS_ENV = "SEMREPO_GITHUB_TOKENS"
RATE_LIMIT_URL = "https://api.github.com/rate_limit"
CHUNK_SIZE = 250          # URLs per run_pipeline call (progress is saved after each chunk)
CHECK_EVERY = 100         # check all tokens' remaining budget every N requests
SAFETY_MARGIN = 200       # treat a token as exhausted below this many remaining requests

logger = logging.getLogger("full_harvest")


# ---------------------------------------------------------------------------
# Rate-limit handling
# ---------------------------------------------------------------------------

def _fetch_rate_limit(token: str) -> tuple[int, float]:
    """(remaining, reset_epoch) of one token. GET /rate_limit is free."""
    import requests
    response = requests.get(
        RATE_LIMIT_URL,
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=30,
    )
    response.raise_for_status()
    core = response.json()["resources"]["core"]
    return int(core["remaining"]), float(core["reset"])


class RateLimitGuard:
    """Sleeps when every token is below SAFETY_MARGIN, until the earliest
    reset. Asks GitHub directly, so several processes sharing the same
    tokens all see the real remaining budget."""

    def __init__(self, tokens: List[str], safety_margin: int = SAFETY_MARGIN,
                 fetch: Callable[[str], tuple[int, float]] = _fetch_rate_limit,
                 sleep: Callable[[float], None] = time.sleep,
                 now: Callable[[], float] = time.time):
        self.tokens = tokens
        self.safety_margin = safety_margin
        self._fetch = fetch
        self._sleep = sleep
        self._now = now
        self.total_slept = 0.0

    def status(self) -> list[tuple[int, float]]:
        result = []
        for token in self.tokens:
            try:
                result.append(self._fetch(token))
            except Exception as error:  # network blip: assume usable, check again later
                logger.warning("Could not read rate limit for one token: %s", type(error).__name__)
                result.append((self.safety_margin + 1, self._now()))
        return result

    def wait_if_exhausted(self) -> bool:
        """Returns True if it slept."""
        status = self.status()
        if any(remaining > self.safety_margin for remaining, _ in status):
            return False
        wake = min(reset for _, reset in status) + 5
        seconds = max(wake - self._now(), 1.0)
        logger.info("All %d token(s) near the limit -- sleeping %.0f s until reset", len(self.tokens), seconds)
        self._sleep(seconds)
        self.total_slept += seconds
        return True


class GuardedClient:
    """Wraps GitHubClient: checks the shared budget every CHECK_EVERY calls
    and when a response reports a low budget, and retries a request that
    failed because every token was exhausted."""

    def __init__(self, inner, guard: RateLimitGuard, check_every: int = CHECK_EVERY, max_retries: int = 3):
        self._inner = inner
        self._guard = guard
        self._check_every = check_every
        self._max_retries = max_retries
        self.calls = 0
        self._low = False

    def get(self, path, *args, **kwargs):
        self.calls += 1
        if self._low or self.calls % self._check_every == 0:
            self._guard.wait_if_exhausted()
            self._low = False

        for attempt in range(self._max_retries + 1):
            try:
                response = self._inner.get(path, *args, **kwargs)
            except Exception:
                # e.g. "all tokens exhausted" from GitHubClient, or a network error:
                # if the budget is the problem, wait and retry; otherwise re-raise.
                if attempt < self._max_retries and self._guard.wait_if_exhausted():
                    continue
                raise
            remaining = (getattr(response, "headers", None) or {}).get("X-RateLimit-Remaining")
            if remaining is not None and remaining.isdigit() and int(remaining) < 2 * self._guard.safety_margin:
                self._low = True
            if (getattr(response, "status_code", None) in (403, 429) and remaining == "0"
                    and attempt < self._max_retries and self._guard.wait_if_exhausted()):
                continue
            return response
        return response

    def __getattr__(self, name):
        return getattr(self._inner, name)


# ---------------------------------------------------------------------------
# One collection (.pkl file)
# ---------------------------------------------------------------------------

def load_urls(pkl_path: Path, limit: Optional[int] = None) -> List[str]:
    with pkl_path.open("rb") as f:
        data = pickle.load(f)
    urls = [str(u) for u in data]
    return urls[:limit] if limit else urls


def _chunks(items: list, size: int):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def harvest_collection(pkl_path: Path, output_root: Path, tokens: List[str], max_issues: Optional[int],
                       max_contributors: Optional[int], fetch_last_commit: bool, fetch_profiles: bool,
                       limit: Optional[int] = None, client_factory=None, pipeline=None) -> dict:
    """Harvests one collection into output_root/<stem>/. Safe to call again."""
    out_dir = output_root / pkl_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / "_COMPLETE").exists():
        logger.info("%s already complete -- skipped", pkl_path.name)
        return json.loads((out_dir / "progress.json").read_text())

    if pipeline is None:
        from semrepo.pipeline import run_pipeline as pipeline
    if client_factory is None:
        from semrepo.github.github_client import GitHubClient
        client_factory = lambda: GitHubClient(tokens=tokens)

    guard = RateLimitGuard(tokens)
    client = GuardedClient(client_factory(), guard)

    urls = load_urls(pkl_path, limit)
    counts: Counter = Counter()
    totals: Counter = Counter()
    started = time.monotonic()
    done = 0
    progress: dict = {}

    for chunk in _chunks(urls, CHUNK_SIZE):
        summary = pipeline(
            chunk, out_dir, client, pkl_path.name,
            max_issues=max_issues, max_contributors=max_contributors,
            fetch_last_commit=fetch_last_commit, fetch_profiles=fetch_profiles,
        )
        counts.update(summary.get("resolution_counts", {}))
        totals.update(summary.get("totals", {}))
        done += len(chunk)
        elapsed = time.monotonic() - started
        progress = {
            "collection": pkl_path.name,
            "urls_total": len(urls),
            "urls_done": done,
            "resolution_counts": dict(counts),
            "records": dict(totals),
            "api_calls": client.calls,
            "elapsed_seconds": round(elapsed, 1),
            "rate_limit_wait_seconds": round(guard.total_slept, 1),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "settings": {"max_issues": max_issues, "max_contributors": max_contributors,
                         "fetch_last_commit": fetch_last_commit, "fetch_profiles": fetch_profiles},
        }
        (out_dir / "progress.json").write_text(json.dumps(progress, indent=2))
        logger.info("%s: %d/%d URLs, %d API calls, %.0f s", pkl_path.name, done, len(urls), client.calls, elapsed)

    (out_dir / "_COMPLETE").write_text(datetime.now(timezone.utc).isoformat() + "\n")
    logger.info("%s complete", pkl_path.name)
    return progress


def _worker(pkl_path: str, output_root: str, tokens: List[str], options: dict) -> dict:
    """Runs in a separate process: own logging file, own client."""
    output_root_path = Path(output_root)
    log_dir = output_root_path / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(pkl_path).stem
    file_handler = logging.FileHandler(log_dir / f"{stem}.log", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    # Console: only this script's own progress lines (not every pipeline message), prefixed with the collection.
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(f"%(asctime)s [{stem}] %(levelname)s %(message)s"))
    console_handler.addFilter(lambda record: record.name == "full_harvest" or record.levelno >= logging.WARNING)
    root = logging.getLogger()
    root.handlers = [file_handler, console_handler]
    root.setLevel(logging.INFO)
    return harvest_collection(Path(pkl_path), output_root_path, tokens, **options)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def _limit(value: str) -> Optional[int]:
    return None if value.lower() in ("none", "0") else int(value)


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Full-scale SemRepo GitHub harvest.")
    parser.add_argument("input_dir", type=Path, help="folder with .pkl URL collections")
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--workers", type=int, default=3, help="parallel processes (default 3)")
    parser.add_argument("--max-issues", type=_limit, default=1000, help="issues+PRs per repo (default 1000, 'none' = no cap)")
    parser.add_argument("--max-contributors", type=_limit, default=100, help="contributors per repo (default 100)")
    parser.add_argument("--no-last-commit", action="store_true", help="skip the extra /commits call per repo")
    parser.add_argument("--no-profiles", action="store_true", help="skip contributor profile (/users) calls")
    parser.add_argument("--only", nargs="*", default=None, help="only these .pkl file names")
    parser.add_argument("--limit-per-collection", type=int, default=None, help="first N URLs per collection (testing)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    tokens = [t.strip() for t in os.environ.get(TOKENS_ENV, "").split(",") if t.strip()]
    if not tokens:
        sys.exit(f"{TOKENS_ENV} is not set. Export one or more tokens, comma-separated.")

    pkl_files = sorted(args.input_dir.glob("*.pkl"))
    if args.only:
        pkl_files = [p for p in pkl_files if p.name in set(args.only)]
    if not pkl_files:
        sys.exit(f"No .pkl files found in {args.input_dir}")

    guard = RateLimitGuard(tokens)
    budgets = [remaining for remaining, _ in guard.status()]
    logger.info("%d token(s), remaining budgets: %s", len(tokens), budgets)
    logger.info("%d collection(s), %d worker(s), caps: issues=%s contributors=%s",
                len(pkl_files), args.workers, args.max_issues, args.max_contributors)

    options = {
        "max_issues": args.max_issues,
        "max_contributors": args.max_contributors,
        "fetch_last_commit": not args.no_last_commit,
        "fetch_profiles": not args.no_profiles,
        "limit": args.limit_per_collection,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results, failures = {}, {}
    started = time.monotonic()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_worker, str(p), str(args.output_dir), tokens, options): p.name for p in pkl_files}
        for future in as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
                logger.info("Finished %s (%d/%d)", name, len(results), len(pkl_files))
            except Exception as error:
                failures[name] = f"{type(error).__name__}: {error}"
                logger.error("Collection %s failed: %s -- re-run the same command to resume it", name, failures[name])

    summary = {
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_hours": round((time.monotonic() - started) / 3600, 2),
        "collections_done": sorted(results),
        "collections_failed": failures,
        "resolution_counts": dict(sum((Counter(r.get("resolution_counts", {})) for r in results.values()), Counter())),
        "records": dict(sum((Counter(r.get("records", {})) for r in results.values()), Counter())),
        "api_calls": sum(r.get("api_calls", 0) for r in results.values()),
        "settings": options,
    }
    (args.output_dir / "run-summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()