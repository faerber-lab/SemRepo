"""
linking.py — discovery and entity resolution
- Match GitHub repositories to LPWC repositories
- Retrieve LPWC papers and SemOpenAlex authors
- Enrich authors with SemOpenAlex metadata
- Retrieve MLSea software links
- Match GitHub contributors to SemOpenAlex authors
- Record exact, reversed, fuzzy, and ambiguous matches
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterator
import re
import unicodedata
from difflib import SequenceMatcher

from rdflib import Literal
from rdflib import URIRef
from SPARQLWrapper import SPARQLWrapper, JSON

LPWC_ENDPOINT = "https://linkedpaperswithcode.com/sparql"
SOA_ENDPOINT = "https://semopenalex.org/sparql"

SOA_PREFIXES = """
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX foaf:    <http://xmlns.com/foaf/0.1/>
PREFIX dbo:     <https://dbpedia.org/ontology/>
PREFIX bido:    <http://purl.org/spar/bido/>
"""

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

GITHUB_SOA_MATCH_METHODS = {
    "ExactNameMatch": "exact-name-match",
    "ReversedNameMatch": "reversed-name-match",
    "FuzzyNameMatch": "fuzzy-name-match",
}

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
        
        author_uri = binding_value(row, "author")
        if author_uri:
            author = {
                "lpwc_author_uri": author_uri,
                "rdf_type": binding_value(row, "authorType"),
            }

            if author not in paper["authors"]:
                paper["authors"].append(author)

    return list(papers.values())

def find_mlsea_uris(lpwc_endpoint: str, lpwc_repository_uri: str) -> list[str]:
    repository_iri = URIRef(lpwc_repository_uri).n3()

    query = LPWC_PREFIXES + f"""
    SELECT DISTINCT ?mlsea
    WHERE {{
        {repository_iri} owl:sameAs ?mlsea .

        FILTER(
            STRSTARTS(STR(?mlsea), "http://w3id.org/mlsea/")
            ||
            STRSTARTS(STR(?mlsea), "https://w3id.org/mlsea/")
        )
    }}
    ORDER BY ?mlsea
    """

    rows = run_select(lpwc_endpoint, query)

    return sorted({
        row["mlsea"]["value"]
        for row in rows
        if row.get("mlsea", {}).get("value")
    })

def find_authors_from_soa(soa_endpoint: str, author_uri: str) -> dict:
    author_iri = URIRef(author_uri).n3()
    query = SOA_PREFIXES + """
    SELECT DISTINCT ?name ?label ?orcidId ?hindex
    WHERE {
        OPTIONAL { AUTHOR foaf:name ?name . }
        OPTIONAL { AUTHOR rdfs:label ?label . }
        OPTIONAL { AUTHOR dbo:orcidId ?orcidId . }
        OPTIONAL { AUTHOR bido:h-index ?hindex . }
    }
    """.replace("AUTHOR", author_iri)
    rows = run_select(soa_endpoint, query)
    author_details = {
        "author_uri": author_uri,
        "author_names": [],
        "orcid_ids": [],
        "h_index_values": [],
    }
    for row in rows:
        name = binding_value(row, "name")
        label = binding_value(row, "label")
        orcid = binding_value(row, "orcidId")
        hindex = binding_value(row, "hindex")
        for candidate_name in (name, label):
            if candidate_name and candidate_name not in author_details["author_names"]:
                author_details["author_names"].append(candidate_name)
        if orcid and orcid not in author_details["orcid_ids"]:
            author_details["orcid_ids"].append(orcid)
        if hindex and hindex not in author_details["h_index_values"]:
            author_details["h_index_values"].append(hindex)
    return author_details

def enrich_papers_with_soa_authors(papers: list[dict], soa_endpoint: str) -> list[dict]:
    author_cache = {}
    for paper in papers:
        enriched_authors = []
        for author in paper.get("authors") or []:
            author_uri = author.get("lpwc_author_uri")
            if not author_uri:
                continue
            if author_uri not in author_cache:
                author_cache[author_uri] = find_authors_from_soa(soa_endpoint, author_uri)
            enriched_authors.append({**author, **author_cache[author_uri]})
        paper["authors"] = enriched_authors
    return papers

def normalize_author_name(name: str) -> str:
    if not name:
        return ""
    name = unicodedata.normalize("NFKC", name).casefold()
    name = "".join(char for char in unicodedata.normalize("NFKD", name) if not unicodedata.combining(char))
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

def reverse_name_order(name: str) -> str:
    tokens = name.split()
    if len(tokens) < 2:
        return name
    return " ".join(tokens[1:] + tokens[:1])

def name_similarity(name1: str, name2: str) -> float:
    # .ratio() returns a float in [0, 1], measuring the “similarity” of the sequences. As a rule of thumb, a .ratio() value over 0.6 means the sequences are close matches:
    return SequenceMatcher(None, name1, name2).ratio()

def compare_author_names(github_name: str, soa_name: str, fuzzy_threshold: float = 0.60) -> dict | None:
    github_normalized = normalize_author_name(github_name)
    soa_normalized = normalize_author_name(soa_name)
    if not github_normalized or not soa_normalized:
        return None
    if github_normalized == soa_normalized:
        return {"match_type": "ExactNameMatch", "similarity": 1.0}
    if github_normalized == reverse_name_order(soa_normalized) or soa_normalized == reverse_name_order(github_normalized):
        return {"match_type": "ReversedNameMatch", "similarity": 1.0}
    similarity = max(name_similarity(github_normalized, soa_normalized), name_similarity(github_normalized, reverse_name_order(soa_normalized)))
    if similarity >= fuzzy_threshold:
        return {"match_type": "FuzzyNameMatch", "similarity": round(similarity, 4)}
    return None

def find_author_matches(github_name: str, candidate_authors: list[dict], fuzzy_threshold: float = 0.60) -> list[dict]:
    matches_by_uri = {}
    if not normalize_author_name(github_name):
        return []
    priority = {"ExactNameMatch": 3, "ReversedNameMatch": 2, "FuzzyNameMatch": 1}
    for author in candidate_authors:
        author_uri = author.get("author_uri")
        author_names = author.get("author_names") or []
        if not author_uri:
            continue
        for soa_name in author_names:
            comparison = compare_author_names(github_name, soa_name, fuzzy_threshold)
            if comparison is None:
                continue
            candidate = {**author, "matched_soa_name": soa_name, **comparison}
            existing = matches_by_uri.get(author_uri)
            if existing is None or priority[candidate["match_type"]] > priority[existing["match_type"]] or (candidate["match_type"] == existing["match_type"] and candidate["similarity"] > existing["similarity"]):
                matches_by_uri[author_uri] = candidate
    return list(matches_by_uri.values())

def add_repository_contributor_matches(repository_result: dict, contributions: list[dict], contributors: list[dict], fuzzy_threshold: float = 0.60) -> tuple[list[dict], list[dict]]:
    contributor_profiles = {rec["contributor_github_user_id"]: rec for rec in contributors if rec.get("contributor_github_user_id") is not None}
    repository_id = repository_result.get("github_repository_id")
    authors_by_repository = {}
    for match in repository_result.get("lpwc_repository_matches") or []:
        for paper in match.get("papers") or []:
            paper_uri = paper.get("lpwc_paper_uri")
            if not paper_uri or not paper_uri.startswith("https://linkedpaperswithcode.com/paper/"):
                continue
            for author in paper.get("authors") or []:
                author_uri = author.get("author_uri") or author.get("lpwc_author_uri")
                author_names = author.get("author_names") or []
                if not author_uri or not author_names:
                    continue
                existing = authors_by_repository.setdefault(author_uri, {"author_uri": author_uri, "author_names": set()})
                existing["author_names"].update(name for name in author_names if name)
    candidate_authors = [{"author_uri": author["author_uri"], "author_names": list(author["author_names"])} for author in authors_by_repository.values()]
    matches_records = []
    review_records = []
    created_matches = set()
    for contribution in contributions:
        if contribution.get("repository_github_id") != repository_id:
            continue
        contributor_id = contribution.get("contributor_github_user_id")
        if contributor_id is None:
            continue
        profile = contributor_profiles.get(contributor_id)
        if not profile:
            continue
        account_type = (contribution.get("contributor_account_type") or profile.get("contributor_account_type") or "").strip().lower()
        if account_type != "user":
            continue
        github_name = profile.get("name")
        if not normalize_author_name(github_name):
            continue
        author_matches = find_author_matches(github_name, candidate_authors, fuzzy_threshold=fuzzy_threshold)
        if not author_matches:
            continue
        base_record = {
            "github_repository_id": repository_id,
            "contributor_github_user_id": contributor_id,
            "contributor_github_login": contribution.get("contributor_github_login"),
            "github_name": github_name,
        }
        if len(author_matches) > 1:
            review_records.append({**base_record, "match_status": "AmbiguousNameMatch", "candidates": author_matches})
            continue
        author_match = author_matches[0]
        if author_match["match_type"] == "FuzzyNameMatch":
            review_records.append({
                **base_record,
                "soa_author_uri": author_match["author_uri"],
                "soa_author_names": author_match.get("author_names", []),
                "matched_soa_name": author_match.get("matched_soa_name"),
                "similarity": author_match.get("similarity"),
                "match_status": "FuzzyNameMatch",
            })
        linking_method = GITHUB_SOA_MATCH_METHODS.get(author_match["match_type"])
        if not linking_method:
            continue
        soa_author_uri = author_match["author_uri"]
        match_key = (contributor_id, soa_author_uri, "same person as", linking_method)
        if match_key in created_matches:
            continue
        created_matches.add(match_key)
        match_record = {
            **base_record,
            "soa_author_uri": soa_author_uri,
            "soa_author_names": author_match.get("author_names", []),
            "matched_soa_name": author_match.get("matched_soa_name"),
            "match_type": author_match["match_type"],
            "similarity": author_match.get("similarity"),
            "linking_method": linking_method,
        }
        matches_records.append(match_record)
    return matches_records, review_records

def link_repository(lpwc_endpoint: str, soa_endpoint: str, repository_record: dict) -> dict:
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
        lpwc_repository_uri = match["lpwc_repository_uri"]
        papers = find_papers_for_repository(lpwc_endpoint, lpwc_repository_uri)
        papers = enrich_papers_with_soa_authors(papers, soa_endpoint)
        mlsea_software_uris = find_mlsea_uris(lpwc_endpoint, lpwc_repository_uri)

        result["lpwc_repository_matches"].append({
            **match,
            "papers": papers,
            "mlsea_software_uris": mlsea_software_uris,
        })
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

def run_linking(repositories_path: Path, output_path: Path, lpwc_endpoint: str, soa_endpoint: str, contributions_path: Path, contributors_path: Path, review_output_path: Path | None = None) -> None:
    repositories = list(read_jsonl(repositories_path))
    contributions = list(read_jsonl(contributions_path))
    contributors = list(read_jsonl(contributors_path))
    results = []
    review_records = []
    for repository in repositories:
        result = link_repository(lpwc_endpoint, soa_endpoint, repository)
        matches, reviews = add_repository_contributor_matches(result, contributions, contributors, fuzzy_threshold=0.60)
        result["github_contributor_soa_matches"] = matches
        results.append(result)
        review_records.extend(reviews)
        print(f"Linked repository {repository.get('github_repository_id')}: {len(matches)} contributor matches")
    write_jsonl(output_path, results)
    print(f"Results written to: {output_path}")
    if review_output_path is not None:
        write_jsonl(review_output_path, review_records)
        print(f"Match reviews written to: {review_output_path}")
        results = []

if __name__ == "__main__":
    folder = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/pilot")
    run_linking(
        folder / "repositories.jsonl",
        folder / "external-links.jsonl",
        LPWC_ENDPOINT,
        SOA_ENDPOINT,
        folder / "contributions.jsonl",
        folder / "contributors.jsonl",
        folder / "github-soa-match-review.jsonl",
    )

# python linking.py data/out-test/1_5000/

# Linked repository 790680512: 0 contributor matches
# Linked repository 741251289: 0 contributor matches
# Linked repository 823210233: 0 contributor matches
# Linked repository 408447491: 1 contributor matches
# Linked repository 645270986: 2 contributor matches
# Linked repository 705126352: 1 contributor matches
# Linked repository 450564762: 0 contributor matches