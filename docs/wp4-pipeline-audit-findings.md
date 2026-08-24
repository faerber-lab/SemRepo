# WP4: Pipeline Code Audit — Detailed Findings

**Companion document to:** `docs/current-file-inventory.csv` (reuse/rewrite/remove decision table)
**Source:** Manual line-by-line audit of `crawling-gitHub-metadata/` and `making-repo-metadata-kg/` in the `semrepo-v2-dev` branch, cross-referenced against `docs/current-ontology-inventory.csv` and `docs/current-ontology-problems.md` (WP1.3).

Purpose of this document: WP1.3 audited the ontology file and found structural problems (domain-intersection bugs, orphaned classes, duplicate naming). This document traces those same problems back to the pipeline code that generates the data, to confirm root causes before making WP4 reuse/rewrite decisions.

---

## Finding 1: `fabio:hasURL` / `fabio:hasUrl` bug — confirmed at line level

**Ontology audit said (Critical #1):** the property is declared with `rdfs:domain` spanning 7 unrelated classes, causing an OWL intersection bug matching Reviewer 1's finding.

**Pipeline code shows:** `making-repo-metadata-kg/modules/RepoJson_to_RDF/RDF_Graphing.py`

- Line 10 (`make_repo_url`): `FABIO.hasURL` — **correct casing** — used only for `Repository`.
- Lines 79, 104, 135, 148, 163, 185, 196, 222, 254, 262 — **10 separate call sites**, all use `FABIO.hasUrl` — **wrong casing** — for organization, person, forked_repo, and issue-author (person/bot) entities.

**Interpretation:** looks like a single original typo that was then copy-pasted across every subsequent entity-writing function. Repository is the only entity type that escaped it, likely because `make_repo_url` was written first and separately from the rest.

**Relevant for WP4:** confirms `RDF_Graphing.py` is a **rewrite**, not a patch — the bug is structural (repeated at every call site), not a single fixable line.

---

## Finding 2: Orphaned role subclasses — root cause identified

**Ontology audit said (High #4):** `Author`, `Contributor`, `Forker`, `IssueAuthor`, `Stargazer`, `Watcher` are orphaned — no property references them as domain or range; role information instead flows through a separate `hasPersonType` property.

**Pipeline code shows:** every single call site that creates a person entity (`make_repo_author_user`, `make_repo_stargazers`, `make_repo_watchers`, `make_repo_contributors`, `make_repo_forks`, `make_repo_issue_author`) uses the identical two-line pattern:

```python
graph.add((make_uri('person', X), RDF.type, make_uri('_class', 'person')))
graph.add((make_uri('person', X), make_uri('property', 'hasPersonType'), make_uri('_class', 'stargazer')))
```

**Interpretation:** the code *never* asserts `rdf:type` as one of the six role subclasses. Every person entity is typed generically as `person`, and role is encoded exclusively through the `hasPersonType` property pointing at a `_class:*` individual. This fully explains why the subclasses are orphaned in the ontology — they were never instantiated by the pipeline that's supposed to populate the graph, not just undocumented in the schema. Two competing design ideas exist in the ontology (subclassing vs. property-based typing); the code committed to only one.

**Contrast — bots are handled differently:** `make_repo_issue_author`'s `elif repo_issue_author_type == 'Bot':` branch *does* assert `RDF.type` as `_class:bot` directly (a real top-level type, not a role-subclass pattern), consistent with the ontology inventory's separate observation that `GitHubBot` sits independently from the `Person` hierarchy.

**Also notable:** bots and persons acting as issue authors are both tagged with the same role individual `_class:issueauthor`, despite being asserted as fundamentally different `rdf:type`s (`bot` vs. `person`). The role vocabulary isn't scoped to a single type hierarchy.

**Relevant for WP4/WP3:** validates the v2 decision to drop the six role subclasses entirely and represent GitHub accounts via the `GitHubAccount`/`GitHubUser`/`GitHubOrganisation`/`GitHubBot` hierarchy instead.

---

## Finding 3: Issue nodes are never explicitly typed (new finding, not in WP1 ontology audit)

**Pipeline code shows:** in `make_repo_issues`, the issue node is created and given `DCTERMS.title`, `FABIO.hasUrl`, `issueState`, `DCTERMS.created`, labels, and an issue-author link — but **no `RDF.type` triple is ever added for the issue node itself**. The issue node also reuses the `'repository'` URI-namespace helper (`make_uri('repository', temp_string)`) rather than a dedicated `'issue'` namespace.

**Hypothesis (not yet confirmed against real output):** if issue nodes are never explicitly typed, any appearance of `GitHubRepositoryIssues` class membership in the actual generated/live data is likely coming **purely from reasoner inference** through the `fabio:hasURL`/`dcterms:created`/`dcterms:title` domain-intersection bug (Finding 1) — meaning the intersection bug may not just be a side effect, but the *only* mechanism by which these entities get typed at all.

**To confirm:** would need to run a reasoner over an actual generated `.nt`/`.ttl` sample from this pipeline and check whether `GitHubRepositoryIssues` membership is asserted or only inferred. Not yet done — flagged as a follow-up, not a confirmed conclusion.

**Relevant for WP4:** if confirmed, this is a strong argument for the v2 pipeline to explicitly assert `rdf:type :Issue` (or `:PullRequest`) on every issue node it writes, rather than relying on any implicit/inferred typing.

---

## Finding 4: External linking (LPWC/SemOpenAlex) — confirmed + new performance issue

**Ontology audit said (High #5):** external links carry no evidence/confidence, enabling the "why only 6% linked" criticism.

**Pipeline code shows:** `making-repo-metadata-kg/modules/Connect_to_LPWC_and_SOA/main.py`

- No MLSea logic anywhere in the file — confirms the WP1 file-listing finding.
- SemOpenAlex author matching is exact full-string equality (`author_name_obj == author_name`) — exactly the "exact-name matching as identity" pattern the project proposal explicitly bans.
- **New finding, performance:** `get_repository_object` / `get_obj` / `get_author_objs` each do a fresh line-by-line scan of the entire LPWC `.nt` file, opened and read from scratch on every call. `connect_lpwc_and_soa` is called once per repository from a nested folder/file loop in `making-repo-metadata-kg/main.py` — meaning the LPWC file is re-scanned line-by-line **once per repository** with no indexing. At ~200k repos this is an O(repos × lpwc_lines) algorithm and a plausible contributor to the pipeline being slow or incomplete at full scale.

**Relevant for WP4:** confirms this module is a **rewrite**, both for the missing MLSea logic and the identity-matching approach, and now also for a genuine scalability reason — a v2 version should index the LPWC data (e.g. a dict/DB keyed by repository URL) rather than re-scanning per repository.

---

## Finding 5: Language data — confirms a WP3 design decision was correct

**Pipeline code shows:** `crawler.py`'s `get_languages` scrapes percentage values from repository page HTML (fragile to GitHub UI changes) rather than calling `GET /repos/{owner}/{repo}/languages` (stable, returns byte counts). `RDF_Graphing.py`'s `make_repo_language` stores these as `xsd:float` percentages, and separately flags only the first-sorted language as `hasPrimaryProgrammingLanguage`.

**Relevant for WP3/WP4:** directly validates the WP3 decision to model `languageBytes` as a raw byte count (`xsd:nonNegativeInteger`) rather than a precomputed percentage — the byte-count approach is both more stable (API-based, not HTML-scraped) and avoids baking in a lossy transformation. `hasPrimaryProgrammingLanguage` is a small piece of information not currently in the v2 model; worth a note but not necessarily required unless a competency question needs it.

---

## Finding 6: Datatype inconsistency to watch for in the new pipeline

**Pipeline code shows:** dates are written as `Literal(..., datatype=XSD.date)` throughout `RDF_Graphing.py` (via raw rdflib, no Protégé involved).

**Relevant for WP4:** WP3's ontology work standardized on `xsd:dateTime` everywhere (Protégé's OWL2 datatype list doesn't include `xsd:date`). Since rdflib doesn't enforce that restriction, it would be easy for a rewritten pipeline to silently reintroduce `xsd:date` literals unless this is deliberately checked — worth a unit test (`tests/test_rdf_generation.py` per the proposal's suggested structure) asserting no `xsd:date` literals appear in generated output.

---

## Finding 7: LPWC extraction code does not exist in this repo

**Searched for:** the script that produces `crawling-gitHub-metadata/github_links/*.pkl` (WP4.2's `extract_lpwc_urls.py` equivalent).

**Result:** no such code exists anywhere in the repository. The `.pkl` files are present as static data artifacts (40 files, ~5,000 URLs each, ≈200,000 total — consistent with the paper's claimed 197,566 repositories), each a plain `List[str]` of GitHub URLs. A path reference in `extract-libraries-from-code/main.py` (`.../LPWC_Extension/Creating_LPWC_Snapshot/data/urls.pkl`) suggests this extraction step existed as a separate module in the original author's local workspace but was never committed to this repository.

**Relevant for WP4:** this is not a reuse/rewrite decision — there is nothing to reuse or rewrite. `extract_lpwc_urls.py` must be built from scratch per WP4.2. Scope is well-defined by the existing output format: read an LPWC release (per the WP2.1 version-pinning decision), emit a list of GitHub repository URLs with source provenance (paper entity, extraction timestamp) — actually a slightly richer output than v1's bare URL list, matching the proposal's suggested `lpwc_repository_links.jsonl` schema (`lpwc_entity`, `paper_entity`, `original_repository_url`, `source_release`, `extraction_timestamp`).

---

## Summary: reuse/rewrite implications

| Module | Confirms | New info | Decision |
|---|---|---|---|
| `RDF_Graphing.py` | fabio:hasUrl bug (line-level), orphan subclass root cause | Issue nodes never typed | Rewrite |
| `Connect_to_LPWC_and_SOA/main.py` | No MLSea logic, exact-name matching | O(repos × lpwc_lines) performance issue | Rewrite |
| `crawler.py` (language fields) | — | Validates v2 `languageBytes` decision | Reuse pattern idea, not code |
| LPWC extraction (`extract_lpwc_urls.py`) | — | Code does not exist in this repo at all | Build from scratch |

Full per-file reuse/rewrite/remove table remains in `docs/current-file-inventory.csv`; this document exists to preserve the *reasoning trail* connecting ontology-level problems to their pipeline-level source.