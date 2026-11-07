# WP2: Scope and Requirements for SemRepo v2

**Date:** 2026-07-28  
**Status:** Finalized for WP3

This document consolidates source population decisions, competency questions, and non-goals for SemRepo v2. It intentionally merges what the original proposal split into `scope-and-requirements.md` + `metadata-selection.csv` + `competency-questions.md` into one document — field-by-field metadata selection will instead happen inline during WP3 ontology design, since it is naturally a per-class decision rather than a separate pre-step.

## 1. Source Population

**Source:** Linked Papers With Code (LPWC), as in v1. No change proposed — LPWC remains the only source of paper-repository associations; this is a known, documented limitation (see Non-goals, item 2, and Reviewer 3's bias comment).

### Decisions carried over from v1 (verified as reasonable, no change needed)

- Only `github.com` URLs are supported (v1 scope; no evidence GitLab/Bitbucket links exist in LPWC data at meaningful scale).

### Decisions that MUST change based on WP1 audit findings

- **Deduplication:** v1 used filename-collision checks (Reviewer 1's critical finding — renames/transfers bypass this). v2 must deduplicate using GitHub's stable numeric repository ID, resolved via the GitHub API, not URL string matching. This is already required by the ontology redesign (`sr:githubRepositoryId` as the URI basis, per 15-point plan point 3).
- **Redirects/transfers:** Must be explicitly modeled via `sr:SourceRepositoryLink` with a `sr:resolutionStatus` (Resolved/Renamed/Transferred/Deleted/Private/Invalid/ApiError), not silently followed and merged as in v1.

### Core Baseline Decisions (adopted 2026-07-28)

These structural decisions form the working basis for WP3 and WP4 execution:

- **Forks:** Out of scope. Only original/source repositories are harvested and modeled; forked repositories are not collected as first-class entities. (Note: `ForkedRepository` as a v1 ontology class is therefore not carried into v2 at all, superseding the earlier "convert to boolean flag" recommendation in `current-ontology-inventory.csv`.)
- **Deleted/inaccessible repositories:** Not represented as ontology nodes. Recorded only in pipeline collection logs (`sr:CollectionStatus` per plan point 10) with a reason (e.g. Deleted, Private, ApiError), so the reason for a missing repository is traceable without polluting the graph with empty nodes.
- **LPWC version:** Use the latest stable static LPWC dump available at the time of harvesting. The specific version/date will be pinned and recorded as provenance metadata at harvest time (addressing v1's complete lack of source-version provenance).

## 2. Competency Questions

The following eight competency questions (CQs) are selected/adapted from the proposal's suggested list, prioritized by direct traceability to a reviewer concern or an audit finding. Each is written before any WP3 ontology modeling begins, to avoid Reviewer 4's "CQs appear post hoc" criticism.

| CQ ID | Question | Why needed (traceability) |
|-------|----------|----------------------------|
| **CQ1** | Which GitHub repositories are associated with papers from a given venue and publication year? | Directly requested by Reviewer 4 ("how many repos/papers from ISWC/ESWC/SEMANTiCS over time"). |
| **CQ2** | Which repositories have changed canonical GitHub location (renamed/transferred) since being recorded in LPWC? | Directly targets Reviewer 1's deduplication/URL-resolution finding (R1-05). |
| **CQ3** | Which programming languages are used by repositories associated with a given research topic? | Reused from v1 (CQ1 in the old paper); still a valid, non-trivial cross-cutting question. |
| **CQ4** | Which GitHub contributors can be linked with sufficient confidence to a scholarly author identity, and what is the confidence basis? | Directly targets Reviewer 3's "6% alignment, why not more?" concern (R3-02) and requires the new `ExternalLink`/`confidenceScore` model. |
| **CQ5** | Which repositories can be connected to datasets or experiments in MLSea-KG, and via what linking method? | Directly targets Reviewer 1's missing MLSea module finding (R1-04); forces the new MLSea linking module to be documented and queryable. |
| **CQ6** | What proportion of LPWC repository URLs are reachable, redirected, duplicated, unavailable, or invalid? | Makes collection completeness a first-class, queryable fact instead of a footnote (relates to plan point 10, `CollectionStatus`). |
| **CQ7** | Which repository metadata fields are incomplete or missing due to API errors or collection limits, and for which snapshot? | Directly targets Reviewer 1's undocumented hardcoded caps (R1-07) and plan point 10. |
| **CQ8** | For a given repository, how have its star/fork/issue counts changed across collected snapshots? | Forces the `RepositorySnapshot` model (plan point 4) to actually be used and queryable, not just theoretically present. |

**Explicitly deferred (not in the core eight, but noted for later consideration):**

- Venue-based institutional analysis (proposal's CQ7).
- Old CQs about organizations/packages — only add if `Package` is confirmed in scope (see Non-goals).

## 3. Non-Goals

Adapted from the proposal's suggested list, kept as-is since they are all reasonable and directly pre-empt reviewer criticism:

- No GitLab or Bitbucket integration (source remains GitHub-only via LPWC).
- No claim of covering all scientific software — SemRepo v2 explicitly documents its LPWC/ML-AI sourcing bias rather than implying broader coverage (directly addresses Reviewer 3's generalizability concern, R3-03).
- No real-time update infrastructure — periodic versioned releases only, as in v1, but with verified dump-endpoint consistency at each release (addresses R1-01).
- No causal analysis of software evolution vs. reproducibility outcomes (left for future work, as the original paper's conclusion already states).
- No storage of all individual stargazers as named entities — aggregate counts only, per snapshot.
- No unvalidated reproducibility-risk prediction — if RRS is retained in WP6, it will be explicitly labeled illustrative unless validated against ground truth (addresses R2-06/R3's shared concern).
- No optimization for maximum triple count — explicitly reject the "quantity over quality" framing that likely contributed to the original rejection.
- No sophisticated user-facing portal — SPARQL endpoint + dumps only, consistent with the Resource Track's expectations.
- No automatic author linking without an evaluated confidence mechanism — every SemOpenAlex alignment must go through the qualified `sr:ExternalLink` pattern with a documented linking method (addresses R3-02).

## 4. Completion Checklist

- [x] Source population decisions fully documented and locked in as baseline.
- [x] Eight competency questions defined, each traceable to a reviewer finding or audit result.
- [x] Non-goals documented.
- [ ] Metadata field selection — deferred to WP3, handled per-class during ontology design.