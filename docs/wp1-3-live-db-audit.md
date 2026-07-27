# WP1.3: SemRepo v1 Live Database Audit

**Date:** 2026-07-23 to 2026-07-24
**Status:** Complete
**Endpoint tested:** https://semrepo.org/sparql
**Ontology tested:** `ontologies/SemRepo-ontology.owl` (branch `semrepo-v2-dev`)

## 1. Executive Summary

This audit independently verifies, at the data level, the core reliability concerns raised by ISWC 2026 reviewers. All queries below were executed directly against the live SPARQL endpoint and confirmed with query results. The live system currently exposes a small, structurally inconsistent dataset that does not match the figures reported in the ISWC 2026 submission.

Key findings:

- The live repository count is **952**, not the 197,566 claimed in the paper (0.48%).
- The live database uses a **different IRI namespace scheme** than the one declared in `SemRepo-ontology.owl`, meaning the ontology and the live data are not formally connected.
- Only **4 classes** are actually instantiated in the live data (`person`, `repository`, `bot`, `organization`) out of 29 classes defined in the ontology. Core entity types such as `Issue`, `LanguageReference`, `Package`, and `Topic` have zero instances.
- The `fabio:hasUrl` (incorrect casing) property is used **5,443 times more often** than the correct `fabio:hasURL` casing.
- Total live triple count (35,264,649) is **43% of the paper's claimed 81.5 million**, closely matching Reviewer 1's independent post-rebuttal count (35.3M), confirming the endpoint has not been corrected since the rebuttal period.

## 2. Ontology–Data Namespace Discrepancy

The ontology file declares its namespace as:

```
https://semrepo.org/ontology#
```

(e.g. `https://semrepo.org/ontology#Repository`, verified via Protégé's Ontology header).

However, querying the live data for distinct classes in use returns a completely different IRI scheme:

**Query:**
```sparql
SELECT DISTINCT ?class WHERE {
  GRAPH <https://semrepo.org> {
    ?s a ?class .
  }
}
LIMIT 20
```

**Result:**
| class |
|---|
| https://semrepo.org/class/person |
| https://semrepo.org/class/repository |
| https://semrepo.org/class/bot |
| https://semrepo.org/class/organization |

**Finding:** The live data uses `https://semrepo.org/class/{lowercase}` while the ontology declares `https://semrepo.org/ontology#{PascalCase}`. These are two distinct, unrelated IRI schemes. No `owl:equivalentClass`, `rdfs:subClassOf`, or `owl:sameAs` bridges them. This means:
- The published ontology cannot be used to validate or reason over the live data as-is.
- Any SHACL shapes written against the ontology's namespace would silently validate nothing against the live graph.

**Additional finding:** Only 4 distinct classes appear in the live data at all. The ontology defines 29 classes; entity types such as `Issue`, `LanguageReference`, `Package`, `Topic`, and all "Reference"/n-ary relation classes have **zero live instances**. This indicates the live endpoint is not a reduced sample of the full production graph, but a much more limited dataset lacking most of the modeled entity types entirely.

## 3. Repository Count Discrepancy

**Claim (paper, Table 1):** 197,566 `sr:Repository` instances.

**Query:**
```sparql
SELECT (COUNT(*) AS ?n) WHERE {
  GRAPH <https://semrepo.org> {
    ?s a <https://semrepo.org/class/repository> .
  }
}
```

**Result:** `n = 952`

**Finding:** The live repository count is 0.48% of the claimed figure.

## 4. External Link Coverage

**Claim (paper, Section 3.3):** 197,566 LPWC links (100% of repositories); 148,185 MLSea-KG links (~75% of repositories).

**Query (LPWC):**
```sparql
PREFIX sr: <https://semrepo.org/property/>
SELECT (COUNT(*) AS ?n) WHERE {
  GRAPH <https://semrepo.org> {
    ?s sr:hasLpwcUrl ?o .
  }
}
```
**Result:** `n = 952`

**Query (MLSea):**
```sparql
PREFIX sr: <https://semrepo.org/property/>
SELECT (COUNT(*) AS ?n) WHERE {
  GRAPH <https://semrepo.org> {
    ?s sr:hasMlseaUrl ?o .
  }
}
```
**Result:** `n = 590`

**Finding:** LPWC coverage matches 100% of the live (952) repositories, consistent internally, but this is 0.48% of the paper's claimed dataset. MLSea coverage (590) is 0.4% of the claimed 148,185 — and only 62% of the live 952 repositories, not the ~75% reported at the full-dataset scale.

## 5. `fabio:hasUrl` Casing Inconsistency

**Query:**
```sparql
PREFIX fabio: <http://purl.org/spar/fabio/>
SELECT ?property (COUNT(*) AS ?n) WHERE {
  GRAPH <https://semrepo.org> {
    VALUES ?property { fabio:hasURL fabio:hasUrl }
    ?s ?property ?o .
  }
}
GROUP BY ?property
```

**Result:**
| property | n |
|---|---|
| http://purl.org/spar/fabio/hasUrl | 5,181,290 |
| http://purl.org/spar/fabio/hasURL | 952 |

**Finding:** The incorrect casing (`hasUrl`) is used 5,443x more often than the FaBiO-correct casing (`hasURL`). The correct-casing count (952) exactly matches the live repository count, suggesting `hasURL` was used only for an early/initial batch before the pipeline switched to (or always primarily used) the incorrect casing. Since FaBiO declares `rdfs:domain frbr:Endeavour` on this property, this reproduces the exact reasoner-inference issue Reviewer 1 identified (subjects like Person/Bot being incorrectly inferred as FRBR Endeavours).

## 6. Total Triple Count

**Query:**
```sparql
SELECT (COUNT(*) AS ?triples) WHERE {
  GRAPH <https://semrepo.org> {
    ?s ?p ?o .
  }
}
```

**Result:** `triples = 35,264,649`

**Finding:** This is 43% of the paper's claimed 81.5M triples, and closely matches Reviewer 1's independently reported count of ~35.3M from their post-rebuttal check (29–30 June 2026). This indicates the live endpoint has not changed materially since the rebuttal period, despite the authors' claim in the rebuttal that endpoint issues were fixed.

## 7. Conclusion

The live SemRepo v1 endpoint does not reflect the dataset described in the ISWC 2026 submission. It currently exposes a small (952-repository), structurally disconnected dataset — disconnected both from the published ontology (namespace mismatch) and from the paper's reported scale (triple count, external link counts). This independently confirms the central reason for the paper's rejection and establishes a concrete, evidence-based starting point for the WP3 rebuild: any new release **must** keep the ontology namespace and the live data namespace identical, and **must** verify reported statistics against the live endpoint before publication, not just against local dump files.

## 8. Queries Index

All queries in this report were executed directly against https://semrepo.org/sparql and independently verified via the SPARQL HTML5 table output, not taken from prior review reports.