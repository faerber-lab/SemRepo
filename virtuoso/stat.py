from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("http://localhost:8890/sparql")
# sparql = SPARQLWrapper("https://semrepo.org/sparql")

GRAPH = "https://semrepo.org"

def run_query(query):
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    return sparql.query().convert()["results"]["bindings"]


# ---------------------------------------------
# 0. Sample triples
# ---------------------------------------------
print("\n## Some triple samples:")

sample_q = f"""
SELECT ?s ?p ?o
WHERE {{
    GRAPH <{GRAPH}> {{
        ?s ?p ?o
    }}
}}
LIMIT 5
"""

for r in run_query(sample_q):
    print(
        r["s"]["value"],
        r["p"]["value"],
        r["o"]["value"]
    )


# ---------------------------------------------
# 1. Total triples
# ---------------------------------------------
print("\n## Metrics:")

triples_q = f"""
SELECT (COUNT(*) AS ?count)
WHERE {{
    GRAPH <{GRAPH}> {{
        ?s ?p ?o
    }}
}}
"""

triples = int(run_query(triples_q)[0]["count"]["value"])
print("Triples:", triples)


# ---------------------------------------------
# 2. Distinct entities
# Count IRIs and blank nodes appearing as
# subjects or objects (excluding literals).
# ---------------------------------------------
entities_q = f"""
SELECT (COUNT(DISTINCT ?entity) AS ?count)
WHERE {{
    GRAPH <{GRAPH}> {{
        {{
            ?entity ?p ?o .
            FILTER(isIRI(?entity) || isBlank(?entity))
        }}
        UNION
        {{
            ?s ?p ?entity .
            FILTER(isIRI(?entity) || isBlank(?entity))
        }}
    }}
}}
"""

entities = int(run_query(entities_q)[0]["count"]["value"])
print("Entities:", entities)


# ---------------------------------------------
# 3. Distinct relations (predicates)
# ---------------------------------------------
preds_q = f"""
SELECT (COUNT(DISTINCT ?p) AS ?count)
WHERE {{
    GRAPH <{GRAPH}> {{
        ?s ?p ?o
    }}
}}
"""

relations = int(run_query(preds_q)[0]["count"]["value"])
print("Relation Types:", relations)


# ---------------------------------------------
# 4. Average degree
# ---------------------------------------------
avg_degree = 2 * triples / entities if entities > 0 else 0

print("Average Degree (2E/V):", round(avg_degree, 2))


# ---------------------------------------------
# 5. Graph density
# ---------------------------------------------
density_q = f"""
SELECT (COUNT(*) AS ?count)
WHERE {{
    {{
        SELECT DISTINCT ?s ?o
        WHERE {{
            GRAPH <{GRAPH}> {{
                ?s ?p ?o
                FILTER(isIRI(?s) || isBlank(?s))
                FILTER(isIRI(?o) || isBlank(?o))
                FILTER(?s != ?o)
            }}
        }}
    }}
}}
"""

unique_edges = int(run_query(density_q)[0]["count"]["value"])

density = (
    unique_edges / (entities * (entities - 1))
    if entities > 1 else 0
)

print("Unique Subject-Object Links:", unique_edges)
print("Graph Density:", "{:.2e}".format(density))


# ---------------------------------------------
# 6. Entity types
# ---------------------------------------------
ent_type_q = f"""
SELECT ?type (COUNT(DISTINCT ?entity) AS ?count)
WHERE {{
    GRAPH <{GRAPH}> {{
        ?entity a ?type .
    }}
}}
GROUP BY ?type
ORDER BY DESC(?count)
"""

ent_types = run_query(ent_type_q)

print("\n## Entity Types:")

for t in ent_types:
    print(
        t["type"]["value"],
        int(t["count"]["value"])
    )


# ---------------------------------------------
# 7. Type coverage
# rdf:type OR dcterms:type
# ---------------------------------------------
typed_ent_q = f"""
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX dcterms: <http://purl.org/dc/terms/>

SELECT
    (COUNT(DISTINCT ?entity) AS ?totalCount)
    (COUNT(DISTINCT ?typedEntity) AS ?typedCount)
WHERE {{
    GRAPH <{GRAPH}> {{
        {{
            ?entity ?p ?o .
            FILTER(isIRI(?entity) || isBlank(?entity))
        }}
        UNION
        {{
            ?s ?p ?entity .
            FILTER(isIRI(?entity) || isBlank(?entity))
        }}

        OPTIONAL {{
            {{
                ?entity rdf:type ?anyType .
            }}
            UNION
            {{
                ?entity dcterms:type ?anyType .
            }}
            BIND(?entity AS ?typedEntity)
        }}
    }}
}}
"""

typed_ent = run_query(typed_ent_q)[0]

typed_count = int(typed_ent["typedCount"]["value"])
total_count = int(typed_ent["totalCount"]["value"])

type_coverage = (
    typed_count * 100 / total_count
    if total_count > 0 else 0
)

print(
    f"\nEntities with rdf:type or dcterms:type: "
    f"{typed_count}/{total_count} ({type_coverage:.2f}%)"
)


print("\n## Final Summary:")
print(f"Graph: {GRAPH}")
print(f"Triples: {triples:,}")
print(f"Entities: {entities:,}")
print(f"Relations: {relations:,}")
print(f"Unique subject-object links: {unique_edges:,}")
print(f"Average degree (2E/V): {avg_degree:.2f}")
print(f"Graph density: {density:.2e}")
print(f"Type coverage: {type_coverage:.2f}%")
