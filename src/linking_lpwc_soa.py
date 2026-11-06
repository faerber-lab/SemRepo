from __future__ import annotations

import json
import argparse
from pathlib import Path
from typing import Iterator

from rdflib import Literal
from rdflib import URIRef
from SPARQLWrapper import SPARQLWrapper, JSON


SEMOPENALEX_ENDPOINT = "https://semopenalex.org/sparql"
LPWC_ENDPOINT = "https://linkedpaperswithcode.com/sparql"

LPWC_PREFIXES = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf: <http://xmlns.com/foaf/0.1/>
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX fabio: <http://purl.org/spar/fabio/>
PREFIX lpwc: <https://linkedpaperswithcode.com/property/>
PREFIX lpwc_class: <https://linkedpaperswithcode.com/class/>
PREFIX soa_class: <https://semopenalex.org/class/>
"""

def read_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def run_select(endpoint_url: str, query: str) -> list[dict]:
    """Execute a read-only SPARQL SELECT query."""
    client = SPARQLWrapper(endpoint_url)
    client.setQuery(query)
    client.setReturnFormat(JSON)
    client.setTimeout(60)
    return client.query().convert()["results"]["bindings"]


def binding_value(binding: dict, variable: str):
    """Return a SPARQL binding value, or None if unbound."""
    value = binding.get(variable)
    return value["value"] if value else None

def query_sparql(endpoint, query):
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)
    result = sparql.query().convert()
    return result["results"]["bindings"]

def find_lpwc_repository(endpoint, github_url):
    url_literal = Literal(github_url).n3()

    query = f"""
    PREFIX fabio: <http://purl.org/spar/fabio/>

    SELECT DISTINCT ?repository ?url
    WHERE {{
        ?repository fabio:hasURL ?url .
        FILTER(LCASE(STR(?url)) = LCASE(STR({url_literal})))
    }}
    """

    bindings = query_sparql(endpoint, query)

    return [
        {"lpwc_repository_uri": item["repository"]["value"],
         "github_url": item["url"]["value"]}
        for item in bindings
    ]

def find_papers_for_repository(lpwc_endpoint: str, lpwc_repository_uri: str) -> list[dict]:
    repository_iri = URIRef(lpwc_repository_uri).n3()

    query = LPWC_PREFIXES + f"""
    SELECT DISTINCT ?paper ?relation ?title ?paperUrl ?creatorName ?author ?authorType
    WHERE {{
        {{ ?paper lpwc:hasOfficialRepository {repository_iri} .
           BIND("hasOfficialRepository" AS ?relation) }}
        UNION
        {{ ?paper lpwc:hasRepository {repository_iri} .
           BIND("hasRepository" AS ?relation) }}

        OPTIONAL {{ ?paper dcterms:title ?title . }}
        OPTIONAL {{ ?paper fabio:hasURL ?paperUrl . }}
        OPTIONAL {{ ?paper lpwc:creatorName ?creatorName . }}
        OPTIONAL {{
            ?paper dcterms:creator ?author .
            OPTIONAL {{ ?author rdf:type ?authorType . }}
        }}
    }}
    ORDER BY ?paper
    """

    rows = run_select(lpwc_endpoint, query)
    papers = {}

    for row in rows:
        paper_uri = row["paper"]["value"]
        paper = papers.setdefault(paper_uri, {
            "lpwc_paper_uri": paper_uri,
            "title": None,
            "paper_url": None,
            "creator_names": [],
            "authors": [],
            "repository_relations": [],
        })

        relation = row.get("relation", {}).get("value")
        if relation and relation not in paper["repository_relations"]:
            paper["repository_relations"].append(relation)

        title = row.get("title", {}).get("value")
        if title:
            paper["title"] = title

        paper_url = row.get("paperUrl", {}).get("value")
        if paper_url:
            paper["paper_url"] = paper_url

        creator_name = row.get("creatorName", {}).get("value")
        if creator_name and creator_name not in paper["creator_names"]:
            paper["creator_names"].append(creator_name)

        author_uri = row.get("author", {}).get("value")
        if author_uri:
            author = {
                "lpwc_author_uri": author_uri,
                "rdf_type": row.get("authorType", {}).get("value"),
            }
            if author not in paper["authors"]:
                paper["authors"].append(author)

    return list(papers.values())


def link_repository(lpwc_endpoint: str, repository_record: dict) -> dict:
    repository_id = repository_record["github_repository_id"]
    github_url = repository_record["canonical_url"]

    lpwc_repositories = find_lpwc_repository(lpwc_endpoint, github_url)

    result = {
        "github_repository_id": repository_id,
        "github_repository_url": github_url,
        "lpwc_repository_matches": [],
        "status": None,
    }

    if not lpwc_repositories:
        result["status"] = "NoExactRepositoryMatch"
        return result

    for match in lpwc_repositories:
        papers = find_papers_for_repository(lpwc_endpoint, match["lpwc_repository_uri"])
        result["lpwc_repository_matches"].append({**match, "papers": papers})

    result["status"] = "RepositoryMatched"
    return result

def find_lpwc_papers(endpoint, repository_iri):
    repo = URIRef(repository_iri).n3()

    query = f"""
    PREFIX lpwc: <https://linkedpaperswithcode.com/property/>
    PREFIX dcterms: <http://purl.org/dc/terms/>

    SELECT DISTINCT ?paper ?relation ?title ?author
    WHERE {{
        VALUES ?relation {{ lpwc:hasOfficialRepository lpwc:hasRepository }}
        ?paper ?relation {repo} .
        OPTIONAL {{ ?paper dcterms:title ?title . }}
        OPTIONAL {{ ?paper dcterms:creator ?author . }}
    }}
    """

    return query_sparql(endpoint, query)

def run_linking(repositories_path: Path, output_path: Path, lpwc_endpoint: str) -> None:
    results = []

    for repository in read_jsonl(repositories_path):
        result = link_repository(lpwc_endpoint, repository)
        results.append(result)
        print(f"Repository {result['github_repository_id']}: {result['status']}")

    write_jsonl(output_path, results)
    print(f"Results written to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Link GitHub repositories to LPWC and SemOpenAlex."
    )
    parser.add_argument("--repositories", type=Path, default=Path("data/pilot/repositories.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("data/pilot/repository-links.jsonl"))

    args = parser.parse_args()
    run_linking(args.repositories, args.output, LPWC_ENDPOINT)
