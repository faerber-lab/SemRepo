# SemRepo v2 — Full Run Notes (November 2026)

Notes on the first full production run of the SemRepo v2 pipeline: processing
times, errors, issues found and how they were fixed, and the automatic and
manual validation steps.

All numbers come from the run's own summary files
(`run-summary.json`, `linking-summary.json`, `dedup-summary.json`,
`rdf-summary.json`) or from the evaluation files named below.

---

## 1. Setup

| Item | Value |
|---|---|
| Machine | virtual machine: Ubuntu 24.04, Python 3.12.3, 4 cores, 31 GB RAM, ~300 GB data disk |
| Code | branch `semrepo-v2-dev` of `faerber-lab/SemRepo` |
| Source URL list | 40 `.pkl` collections (`1_5000` … `195001_200000`), 198,334 source URLs |
| GitHub access | 3 fine-grained personal tokens from 3 accounts (the rate limit is per account: 5,000 requests/hour each) |
| LPWC | Zenodo dump `linkedpaperswithcode_2024-09-05.nt` (2,645,294,632 bytes, MD5 `3512477cd716ef8c1cf71b184b3a16ca`, 10,648,236 lines), loaded into a local SQLite index |
| SemOpenAlex, MLSea | live SPARQL endpoints, batched queries, local response cache |

Pipeline:

```
run_full_harvest.py   -> link_repositories.py --all -> prepare_publication.py -> build_rdf_all.py --validate
(GitHub API)             (LPWC index, SemOpenAlex,     (cross-collection        (RDF per collection,
                          MLSea)                        dedup, publication copy)  SHACL per collection)
```

Caps set before the run: at most **1,000 issues + pull requests**
and **100 contributors** per repository. Issues and pull requests are stored
separately. E-mail addresses are removed from the published data (the raw
harvest keeps them).

---

## 2. Processing times

| Step | Wall-clock time | Notes |
|---|---|---|
| Pilot measurement (before the run) | — | 7.6 API calls/URL, 3.6 s/URL with one token; predicted ~4.5 days for the full list with 3 tokens |
| LPWC index build | 71.6 s | one pass over the 2.6 GB N-Triples dump |
| **Harvest** | **103.1 h** (18 Nov ~16:30 – 22 Nov 23:39 UTC) | 1,487,218 API calls (7.5/URL); rate-limit bound (~1,930 URLs/h); 140.4 h of rate-limit waiting summed over the parallel workers |
| Linking, first 15 collections | ~14 min | 0 SPARQL queries for the 6 collections already cached, ~125–140 per new collection |
| Linking, remaining 25 collections | ~25 min | resume skips already linked repositories |
| Publication copy (`prepare_publication`) | a few minutes | |
| **RDF generation + SHACL validation, 40 collections** | **84.1 min** with 3 workers | 89 min generation + 158 min validation CPU time in total; per collection ~2.2 min generation and ~4 min validation; ~3 GB RAM per worker |

The prediction from the pilot held: 103 h actual vs ~4.5 days (108 h)
predicted, 7.5 vs 7.6 API calls per URL.

A first sequential RDF run (1 worker) took 1,268 min wall-clock but only
273 min CPU time; the machine was idle when checked afterwards, so the extra
time was most likely caused by other load on the shared machine. The
build now records generation and validation time per collection, and the
parallel re-run took 84 min.

---

## 3. Harvest results

| Item | Count |
|---|---|
| Source URLs processed | 198,334 |
| Resolved | 178,154 |
| Renamed (resolved via redirect) | 6,529 |
| Transferred (resolved via redirect) | 11,330 |
| **Resolved to a repository, total** | **196,013 (98.8%)** |
| Invalid (deleted or private) | 2,283 (1.2%) |
| Same repository as another URL in the list | 169 |
| API errors after retries | 15 |
| URL could not be normalised | 23 |
| Failed collections | 0 |
| `ERROR` lines in the harvest logs | 0 |

Raw records (before cross-collection dedup): 3,614,047 issues and pull
requests, 537,499 contributions, 483,361 contributor profiles, 439,513
language usages.

Known benign warnings in the logs (not errors):
- 404 for the profile of GitHub's Copilot bot account.
- 204 (no content) for the contributor list of empty repositories. These are
  recorded as `Failed` although the repository is simply empty (see §8).
- `RemoteDisconnected` network errors, recovered by retries.
- 403 for the contributor list of very large repositories (GitHub does not
  list contributors for them).

---

## 4. Linking results

Counts before cross-collection dedup (195,844 linked repositories = 196,013
resolved − 169 duplicates in the URL list; no repository was lost between
harvest and linking).

| Item | Count |
|---|---|
| Repositories linked | 195,844 |
| Found in LPWC | 195,374 (99.8%) |
| … found only through the original (pre-redirect) URL | 13,384 (6.8%) |
| Repository → paper links | 251,997 |
| … official implementation links | 157,994 (63%) |
| Papers with a SemOpenAlex work (`owl:sameAs` in LPWC) | 179,670 (71%) |
| MLSea links | 150,590 |
| GitHub contributor → SemOpenAlex author matches (similarity ≥ 0.60) | 89,926 |
| Match review records (ambiguous / fuzzy) | 31,470 |

The linking keeps every fuzzy match from similarity 0.60 (the
SequenceMatcher "close match" rule of thumb); the published RDF applies the
stricter threshold 0.70 (see §6.2). The threshold is one constant
(`RDF_FUZZY_THRESHOLD` in `generate_rdf_with_linking.py`) and is recorded in
`rdf-summary.json`, so it can be changed without re-linking.

LPWC tasks and research areas: 864,083 paper → task links; 2,277 tasks have
their own research area and 1,577 more inherit one from a parent task (up to 3
levels); 339,483 of 485,899 LPWC papers (70%) have a research area.

---

## 5. Publication copy and RDF

### 5.1 Cross-collection dedup (`prepare_publication.py`)

The same repository can be linked from papers in several collections. A
repository belongs to the first collection (in sorted order) that collected
it.

| Item | Count |
|---|---|
| **Unique repositories** | **190,072** |
| Repositories dropped as duplicates | 5,772 (2.9%) |
| Issues and pull requests kept / dropped | 3,278,320 / 335,727 |
| Contributions kept / dropped | 507,372 / 30,127 |
| Unique contributor profiles | 229,908 (from 483,361 raw) |
| Language usages kept | 425,515 |
| Source-repository-links (one per original URL) | 198,311 |
| Collection activities (one per API request type and repository) | 587,532 |
| Repositories that hit the issue cap (1,000) | 840 |
| Repositories that hit the contributor cap (100) | 780 |

Fewer than 0.5% of the repositories hit either cap.

Language names unified (GitHub reports some languages with different
spellings; one language node must have one name, so the most frequent
spelling over the whole harvest is used): MATLAB (17,787) / Matlab (852),
Fortran (1,942) / FORTRAN (8), FreeBASIC (11) / FreeBasic (3), WDL (2) / wdl (1).

Issue and pull request authors by account type: User 3,023,419; Bot 254,400
(7.8%); Organization 491; Mannequin 10.

### 5.2 RDF

| Item | Count |
|---|---|
| Repositories / snapshots | 190,072 / 190,072 |
| Issues and pull requests (of which pull requests) | 3,278,320 (1,583,073) |
| Contributions | 507,372 |
| Contributor profiles | 229,908 |
| Language usages | 425,515 |
| External links (all types) | 992,990 |
| GitHub account → SemOpenAlex author links (published) | 73,567 |
| Fuzzy matches below the RDF threshold (not published) | 9,358 |
| LPWC authorship statements | 637,348 |
| LPWC paper metadata nodes (title, date, tasks, areas) | 223,767 |
| Size | 4.5 GB Turtle, 40 collections × 7 files |

**SHACL: all 40 collections conform (0 violations).**

### 5.3 Final dataset statistics

Computed directly from the published data with `src/compute_statistics.py`
(distinct entities, after cross-collection dedup).

| Item | Count |
|---|---|
| **Triples (distinct)** | **71,570,940** |
| Triples summed over the 280 files | 78,304,508 |
| … issues / pull requests / external links | 26,809,547 / 23,526,453 / 10,209,432 |
| … contributions / snapshots / core / languages | 5,447,678 / 5,322,084 / 5,272,438 / 1,716,876 |
| Repositories | 190,072 |
| … linked to at least one paper | 189,236 (99.6%) |
| … linked to a SemOpenAlex work | 133,628 (70.3%) |
| … linked to MLSea | 143,420 (75.5%) |
| … with issues / with pull requests / with contributions | 94,983 / 56,745 / 183,893 |
| Distinct papers (LPWC) | 176,196 |
| … with an official-implementation link | 147,970 |
| … with a research area | 108,519 |
| Distinct SemOpenAlex works | 115,688 |
| Distinct MLSea software resources | 127,773 |
| Distinct LPWC tasks | 4,127 |
| Issues / pull requests | 1,695,247 / 1,583,073 |
| Distinct issue and pull request authors | 600,785 |
| Distinct contributors | 229,910 |
| Published GitHub account → SemOpenAlex author pairs | 38,962 |
| … distinct GitHub accounts / distinct SemOpenAlex authors | 37,609 / 37,903 |
| Programming languages | 481 |

The 6,733,568 triples counted more than once are about resources that are
referenced from several collections and written into each of them: GitHub
accounts (type, user id, login, profile URL; ~1.14 million repetitions each for
id, login and URL), LPWC papers (authors, tasks, research areas, title, date),
topics, programming languages and GitHub account → SemOpenAlex author links.
The repeated triples are identical, so loading all files into one graph keeps
each of them once.

Most frequent primary languages: Python (114,806), Jupyter Notebook (30,267),
C++ (7,745), MATLAB (6,142), R (4,438).

Research areas by distinct papers: computer vision (68,650), methodology
(52,220), natural language processing (47,094), miscellaneous (28,814),
medical (24,380), computer code (17,289), adversarial (14,929), graphs
(12,705), reasoning (12,590), time series (12,142).

### 5.4 Comparison with SemRepo v1

| Item | v1 (RDF dump 2025-05-11) | v2 |
|---|---|---|
| Triples | 82,078,636 | 71,570,940 |
| Repositories | 197,566 | 190,072 |
| Persons / accounts linked to SemOpenAlex authors | 11,867 | 37,609 |
| Issues (v1: `hasIssue` usages; v2: typed issues and pull requests) | 2,609,510 | 3,278,320 |
| Repositories with an MLSea link | 148,186 | 143,420 |

Notes on the comparison: v2 has fewer repositories because repositories
reached through several source URLs or collections are published once, and
deleted or private repositories (2,283) are not published. Triple counts are
not directly comparable, since the two versions use different data models
(e.g. v1 also writes 7,786,024 URL values under a second property spelling,
`fabio:hasUrl` next to `fabio:hasURL`). The v1 MLSea links do not come from a documented pipeline step; the v2
links are produced by the linking script.

---

## 6. Validation procedures

### 6.1 Automatic

- **Unit and integration tests:** 137 tests (`pytest`), run before every push.
  Every bug in §7 has a regression test that fails on the old code and passes
  on the fix.
- **Syntactic validity:** all 280 Turtle files (40 collections × 7) were
  parsed with RDFLib without errors when counting the triples (§5.3), and the
  whole release was loaded into a Virtuoso triple store without errors.
- **Distinct triples:** the release was exported to N-Triples
  (`src/export_ntriples.py`) and the distinct lines counted with
  `sort | uniq`: 71,570,940, the same number the Virtuoso graph reports.
- **SHACL:** every collection of the published RDF is validated against
  `ontologies/semrepo-v2-shapes.ttl` (pySHACL, with the ontology). The
  pipeline writes a `shacl-report.txt` for any non-conforming collection.
- **Consistency checks between steps:**
  - 196,013 resolved URLs − 169 duplicate URLs = 195,844 linked repositories.
  - 195,844 linked = 190,072 kept + 5,772 dropped in the publication copy.
  - Records moved between collections in the publication copy (5,784
    source-repository-links, 17,316 collection activities) equal exactly the
    SHACL violations of the first RDF run (§7, issue 9).
  - Re-linking the first 6 collections after code changes reproduced the
    earlier link counts exactly (29,613 repositories, 38,386 paper links,
    13,770 contributor matches).
- **Pilot vs full run:** API calls per URL (7.6 vs 7.5) and runtime (~108 h vs
  103 h) matched the prediction.

### 6.2 Manual

**Contributor → author matching precision.** A stratified random sample of
175 matches (seed 42) from the first 15 linked collections (23,391 unique
contributor–author pairs) was labelled by hand (1 = same person, 0 =
different person, ? = cannot decide). Labelling rule: compare the GitHub
display name with the SemOpenAlex author name in the context of the linked
paper; consult the GitHub profile when the names are ambiguous.
Scripts: `src/sample_contributor_matches.py` (`sample`, `score`).

| Stratum | Precision | 95% Wilson interval | Matches in stratum |
|---|---|---|---|
| Exact name | 100% (50/50) | 92.9–100% | 16,229 |
| Reversed name order | 100% (25/25) | 86.7–100% | 306 |
| Fuzzy 0.90–1.00 | 100% (25/25) | 86.7–100% | 1,153 |
| Fuzzy 0.80–0.90 | 96% (24/25) | 80.5–99.3% | 1,165 |
| Fuzzy 0.70–0.80 | 79% (19/24, 1 unsure) | 59.5–90.8% | 1,544 |
| Fuzzy 0.60–0.70 | 44% (11/25) | 26.7–62.9% | 2,994 |

Population-weighted precision on the first 15 collections: fuzzy 70%, all
matches 91.3% at threshold 0.60, 98.2% at 0.70 while keeping ~87% of the
matches. Applied to the stratum sizes of the full data (45,424 unique pairs
from 0.60), the estimated precision is 90.4% for all matches and **98.1% for
the 38,962 published matches**. Decision: linking keeps matches from 0.60, the published RDF uses
0.70. Typical error in the lowest band: a contributor matched to a different
co-author of the same paper with a similar name.

**LPWC local index vs live endpoint.** For a sample of repositories, the papers
found through the local index were compared with the live LPWC SPARQL
endpoint: 47/47 the same papers, 50/50 found when the original URL was also
used. The comparison also showed that the earlier (live-endpoint) linking
counted LPWC repository-reference nodes as separate papers (duplicated
links); the index-based linking fixes this.

**SHACL report review.** The SHACL reports of the first real-data runs were
read and every violation type traced to its cause (§7, issues 6, 7, 9, 10).

---

## 7. Issues found and how they were fixed

| # | Issue | Found by | Fix |
|---|---|---|---|
| 1 | `UnboundLocalError` on `contributors` when a repository URL failed; contributor collection returned a 2-tuple on error paths (crash on 403 for very large repositories) | first test runs | `pipeline.py`, `collect_contributors.py` (commit 4973612) |
| 2 | The public linking endpoints timed out under load; one SPARQL request per repository was too slow for 200k repositories | linking checks before the run | local SQLite index of the LPWC dump, batched SemOpenAlex/MLSea queries (100 per request, POST), local response cache, retries, per-repository resume |
| 3 | The old linking created duplicate paper links (LPWC repository-reference nodes counted as papers) | local index vs live endpoint comparison | index maps reference nodes to their paper |
| 4 | One token gives 5,000 requests/hour per account; a single-token run would take ~2 weeks | pilot measurement | multi-token harvest with a rate-limit guard that sleeps until the earliest reset, parallel workers, per-collection checkpoints and resume (`run_full_harvest.py`) |
| 5 | Repositories renamed or transferred after the paper was published | harvest | follow GitHub redirects; keep the original URL as provenance; link with both URLs (13,384 repositories found only through the original URL) |
| 6 | SHACL `maxCount 1` violation on LPWC evidence flags: a renamed repository can match two LPWC repository nodes with different flags | SHACL on the first real collection | flags merged with OR (commit a84f8c9) |
| 7 | One language node with two names ("MATLAB"/"Matlab") | SHACL on the first real collection | most frequent spelling over the whole harvest (commit a84f8c9); found 3 more languages on the full data |
| 8 | Fuzzy contributor matches between 0.60 and 0.70 only 44% correct | manual precision study (§6.2) | published RDF uses 0.70; linking keeps all matches from 0.60 (commit 3bae52e) |
| 9 | 23,100 SHACL `sh:class :Repository` violations in 39 of 40 collections: after dedup, source-repository-links and collection activities pointed to repositories written to another collection, which per-collection validation cannot see | SHACL on the full data (first RDF run) | provenance records are written to the collection that owns the repository, so every collection is self-contained; regression test |
| 10 | 19 SHACL violations on `issueAuthor`: GitHub also has the account type "Mannequin" (10 issues/PRs; accounts imported from other platforms). The code types unknown accounts as generic `sr:GitHubAccount`, but the shapes accepted only User/Organisation/Bot | SHACL on the full data (first RDF run) | shapes accept `sr:GitHubAccount` for account-valued properties, plus a shape that validates generic accounts |
| 11 | Sequential RDF build: 1,268 min wall-clock for 273 min CPU | first RDF run | parallel build (`--workers`), generation and validation time recorded per collection: 84 min with 3 workers |
| 12 | The first triple count (78,304,508) summed the triples per file; triples about resources shared by several collections were counted once per collection | comparison with the triple count of the Virtuoso graph (71,570,940) | distinct count over an N-Triples export (`src/export_ntriples.py`); the statistics script now reports the sum as `triples_summed_over_files` (§5.3) |

---

## 8. Open points

- `linking-summary.json` of a collection is overwritten with zeros when a
  re-run skips all of its repositories (the link data itself is not affected).
  Final statistics are therefore computed from the link files, not from these
  summaries.
- 204 (empty repository) on the contributor list is recorded as `Failed`; it
  should count as success with zero contributors.
- Profile requests for bot accounts (e.g. Copilot) return 404 and could be
  skipped.
- Only one snapshot per repository (collected 18–23 Nov 2026). Competency
  questions about change over time need a second snapshot (postponed).
- A later run may use an extended, updated source URL list. The pipeline can be re-run on a new list; with 3 tokens it processes about
  2,000 URLs per hour.
- Precision was measured on a sample from the first 15 collections; the
  estimate for the full data applies the per-stratum precision to the full
  stratum sizes (§6.2).

---

## 9. Reproducing the run

```bash
# 1. harvest (3 tokens, comma-separated)
export SEMREPO_GITHUB_TOKENS=...
python3 src/run_full_harvest.py ...                      # see the script's --help
# 2. LPWC index
python3 src/lpwc_index.py build linkedpaperswithcode_2024-09-05.nt lpwc-index.sqlite
# 3. linking
python3 src/link_repositories.py --index lpwc-index.sqlite --cache linking-cache.sqlite --all <harvest root>
# 4. publication copy
python3 src/prepare_publication.py <harvest root> <publish root>
# 5. RDF + SHACL
python3 src/build_rdf_all.py <publish root> <rdf root> --validate --workers 3
# manual precision study
python3 src/sample_contributor_matches.py sample <harvest root> sample.csv
python3 src/sample_contributor_matches.py score sample-labelled.csv
```