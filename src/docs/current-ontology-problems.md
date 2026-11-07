# WP1.3: SemRepo v1 Ontology — Problem Summary

**Date:** 2026-07-27
**Companion document to:** `docs/current-ontology-inventory.csv` (full class-by-class technical detail)
**Source:** Manual audit of `ontologies/SemRepo-ontology.owl` in Protégé (29 classes), cross-referenced against ISWC 2026 reviewer comments.

This document summarizes the structural problems found in the existing ontology in prose form, grouped by severity, for quick review ahead of the WP3 redesign.

## Critical (directly caused/contributed to the ISWC rejection)

**1. `fabio:hasURL` domain-intersection bug (7 classes affected)**
`fabio:hasURL`/`fabio:hasUrl` is declared with `rdfs:domain` spanning `Repository`, `Person`, `GitHubBot`, `ForkedRepository`, `GitHubRepositoryIssues`, `organization`, and `Package` simultaneously. Under OWL semantics, multiple `rdfs:domain` declarations on one property are interpreted as an intersection, not a union — meaning a reasoner would infer that any subject using this property belongs to *all* of these classes at once. This is the exact issue Reviewer 1 identified (subjects incorrectly inferred as `frbr:Endeavour`). The same intersection pattern also affects `dcterms:created`, `dcterms:title`, and most `foaf:*` properties (accountName, description, mbox, name) and GitHub-specific properties (hasBlog, hasFollowers, hasLocation, hasPublicRepos, hasTwitterAccount) — all shared across `Person`, `organization`, and unrelated classes.

**2. Live data namespace does not match the ontology namespace**
The ontology declares classes under `https://semrepo.org/ontology#` (e.g. `#Repository`), but the live SPARQL endpoint uses `https://semrepo.org/class/` with lowercase names (e.g. `/class/repository`). These are two disconnected IRI schemes with no `owl:equivalentClass` or similar bridge. The ontology cannot currently be used to validate or reason over the live data. (See `docs/wp1-3-live-db-audit.md` for full evidence.)

**3. `Repository` lacks any time/snapshot separation**
Mutable, time-dependent values — `hasTotalForks`, `hasTotalOpenIssues`, `hasTotalStargazers`, `hasTotalWatchers` — and external-link properties (`hasLpwcUrl`, `hasMlseaUrl`, `hasSoaUrl`) are all attached directly to `Repository`, with no dated snapshot entity. There is no way to represent "this repo had X stars as of date Y" — every update overwrites the previous value, which conflicts with the project's reproducibility goals.

## High (structural design flaws, not yet flagged by reviewers but likely to resurface)

**4. Role modeling is duplicated and contradictory**
Every GitHub account is modeled as `Person`, with role information expressed in two incompatible ways at once: (a) permanent `rdf:type` subclasses — `Author`, `Contributor`, `Forker`, `IssueAuthor`, `Stargazer`, `Watcher` — and (b) a separate `Person's type (e.g. Author, Contributor)` property. Investigation showed these 6 subclasses are effectively orphaned: no property in the ontology references them directly as domain or range (all point to generic `Person` instead), suggesting they may only be assigned manually on individual instances and duplicate the property-based approach.

**5. External links to SemOpenAlex/LPWC/MLSea carry no evidence or confidence**
Properties like `hasSoaUrl` assert a direct link with no way to express how the link was produced, how confident the alignment is, or whether it was manually verified. This directly enabled the "6% of persons linked, but why not more?" criticism (Reviewer 3) and is inconsistent with treating cross-KG author alignment as an uncertain, evidence-based claim rather than an identity claim.

**6. Unnecessary local proxy classes for external KG entities**
`Repository in LinkedPapersWithCode` and `Software entities` are locally-defined classes that exist only to serve as the `rdfs:range` of `hasLpwcUrl`/`hasMlseaUrl`. This is architecturally unnecessary — a link to an external KG entity does not require asserting a local `rdf:type` for that entity; the property should point directly to the external IRI.

## Medium (naming/consistency debt)

**7. At least 6 duplicate class pairs from inconsistent naming conventions**
`repository` vs `Repository`, `organization` vs `GitHub organisation`, `issue`/`GitHub Repository Issues`, `contributorReference`/`GitHubContributorReference`/`hasContributorReference` (three names for one concept), `languageReference`/`GitHubRepositoryLanguageReference`, `IssueLabelReference`/`GitHubIssueLabelReference`/`hasIssueLabelReference` (also three names). These suggest the ontology was extended over time without a consistent naming convention or review process.

**8. Two classes are misleadingly named as if they were properties**
`hasContributorReference` and `hasIssueLabelReference` are declared as `owl:Class` (used as `rdfs:range` of separate properties called "Reference object for Contributor/Issue Labels"), but their names follow object-property naming convention (`has...`). This is confusing and error-prone for anyone extending the ontology.

**9. 9 classes typed as `rdf:Class` instead of `owl:Class`**
`Author`, `Contributor`, `Forker`, `GitHubBot`, `GitHub organisation`, `IssueAuthor`, `Person`, `Stargazer`, `Watcher` use the RDFS-style `rdf:Class` type declaration rather than the OWL-standard `owl:Class`. Non-standard for an OWL/DL ontology; may cause some reasoners to not treat them as full OWL classes.

**10. `Package` is included without a clear justification**
The ontology includes a `Package utilised in a Code base.` class (note: label is a full sentence, not a concise name) whose inclusion is not tied to a stated competency question. Per the WP2/WP3 planning discussion, Package should only remain in the core model if a competency question explicitly requires it.

## Not yet verified

- **File parse error**: The `.owl` file was missing an `xmlns:owl` namespace declaration in the root `<rdf:RDF>` tag, preventing it from opening in Protégé until manually fixed. Root cause (manual edit vs. faulty export script) not yet investigated — worth checking `making-repo-metadata-kg/modules/RepoJson_to_RDF/RDF_Graphing.py` for how the OWL/TTL files are serialized.
- **License inconsistency** (CC0 vs CC-BY-4.0, flagged by Reviewer 2) is a Zenodo/paper metadata issue, not an ontology structure issue — tracked separately in the reviewer-issue-matrix (WP1.5).

## Summary Table

| Severity | Count | Examples |
|---|---|---|
| Critical | 3 | fabio:hasURL intersection, namespace mismatch, no snapshot model |
| High | 3 | duplicated role modeling, unqualified external links, unnecessary proxy classes |
| Medium | 4 | naming duplicates, misleading class names, rdf:Class typing, unjustified Package inclusion |

Full technical detail (per-class domain/range, triple usage) is in `docs/current-ontology-inventory.csv`.