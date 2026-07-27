# WP1.1 & WP1.2: Existing System Overview

**Date:** 2026-07-27
**Scope:** Freeze and understand the existing SemRepo v1 system before any modification (per WP1.1/WP1.2). This is a lightweight overview rather than a full file-by-file inventory; it complements the detailed WP1.3 ontology audit and WP1.3 live database audit already completed.

## 1. Public Resources (frozen references)

- GitHub repository: https://github.com/faerber-lab/SemRepo (branch `semrepo-v2-dev` created for this work; `main` untouched)
- Zenodo record: https://zenodo.org/records/15399468 (DOI 10.5281/zenodo.15399467) — contains `SemRepo-ontology.owl`, `SemRepo_2025-05-11.nt.gz`, `SemRepo_2025-05-11.ttl.gz`, `VoID.ttl`
- Public SPARQL endpoint: https://semrepo.org/sparql
- Project website: https://semrepo.org/
- ISWC 2026 submission (paper): `ISWC26_SemRepo-2.pdf` (rejected; see reviewer-issue-matrix, WP1.5)

## 2. Repository Structure (as of current `semrepo-v2-dev` state)

```
CQs/                              - Competency question SPARQL queries + example queries
crawling-gitHub-metadata/         - GitHub metadata harvesting pipeline
  github_links/*.pkl              - Raw harvested repo URL batches (1-5000 ... 195001-200000,
                                     i.e. covering the full ~200K scope locally)
  logger.py, main.py
  modules/crawler.py, utils.py
extract-libraries-from-code/      - Package/dependency extraction from repo code
make-package-kg/                  - Package-level KG construction
making-repo-metadata-kg/          - Main RDF construction pipeline
  main.py
  modules/Connect_to_LPWC_and_SOA/main.py   - LPWC + SemOpenAlex linking
  modules/RepoJson_to_RDF/RDF_Graphing.py   - JSON -> RDF conversion
  modules/Utils/constants.py, utils.py
ontologies/                       - SemRepo-ontology.owl, SemRepo-DCAT.ttl, VoID.ttl
usecase/                          - Reproducibility auditing notebook, semrepo-20k.csv, compute-indicators.sparql
docs/                             - This project's new audit documentation (WP1.3+)
```

## 3. Key Observation: No MLSea Linking Module

`making-repo-metadata-kg/modules/` contains only `Connect_to_LPWC_and_SOA/`. There is **no equivalent module for MLSea-KG linking** anywhere in the pipeline source. This independently confirms Reviewer 1's finding ("I was not able to locate a corresponding function for MLSea"). Combined with the WP1.3 live database audit finding of only 590 `hasMlseaUrl` triples (vs. 148,185 claimed), this suggests the MLSea links present in the live data were either produced by an undocumented/ad-hoc process, or are leftover from a partial/abandoned run, not from a reproducible pipeline step.

## 4. Key Observation: Raw Data Covers Full Scope, Live Endpoint Does Not

The `github_links/*.pkl` files span the full claimed range (1 to ~200,000), meaning the initial harvesting step likely did complete at the claimed scale. This means the ~99.5% data loss identified in the WP1.3 live database audit (952 live repositories vs. 197,566 claimed) most likely occurred **downstream** of harvesting — in the `making-repo-metadata-kg` RDF construction/loading step, or in what was actually deployed to the live triple store — not in the initial crawl itself. This narrows the scope of what WP1.4 needs to investigate.

## 5. Pipeline Stages (high-level, not yet verified line-by-line)

1. **Harvest** (`crawling-gitHub-metadata/`): GitHub URLs -> raw JSON/pkl batches
2. **Package extraction** (`extract-libraries-from-code/`, `make-package-kg/`): dependency/package metadata
3. **RDF construction + linking** (`making-repo-metadata-kg/`): JSON -> RDF, LPWC/SOA linking
4. **Competency question validation** (`CQs/`): SPARQL queries used for paper's evaluation section
5. **Use case computation** (`usecase/`): Reproducibility Risk Score notebook and pre-computed `semrepo-20k.csv`

**Note:** This overview intentionally does not include a full per-file Purpose/Input/Output/Works?/Test available? table (as WP1.2 originally specified) — Michael has indicated the proposal is a guideline rather than a strict checklist, so we are prioritizing depth on the ontology and live-data findings (WP1.3, WP1.4) over exhaustive per-file documentation at this stage. This can be expanded later if needed for the pipeline rebuild (WP4+).