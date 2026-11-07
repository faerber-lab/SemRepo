"""
WP5.2 -- Generate RDF from the normalized JSONL records produced by
WP4.6/pipeline.py, using identifiers.py's deterministic URIs and the
classes/properties defined in ontologies/semrepo-v2.ttl.

Account typing: GitHub returns a 'type' field (User / Organization / Bot)
for repository owners, contributors and issue authors; it is mapped to
:GitHubUser / :GitHubOrganisation / :GitHubBot by _account_class(). Records
written before ontology v2.1 have no type field and fall back to
:GitHubUser (the previous, documented default).

Numeric values are written as plain xsd:integer (Turtle: 103257), not
xsd:nonNegativeInteger; non-negativity is enforced by sh:minInclusive 0 in
the shapes (ontology v2.1, per reviewer feedback).

Output is split into the files the project proposal names for WP5.2,
plus one addition (semrepo-languages.ttl) the proposal's file list
doesn't include but our ontology needs (LanguageUsage/ProgrammingLanguage
weren't part of v1's data model, so the proposal's WP5.2 list predates
this pattern):

    semrepo-core.ttl          Repository, SourceRepositoryLink, CollectionActivity
    semrepo-snapshots.ttl     RepositorySnapshot
    semrepo-issues.ttl        Issue / PullRequest
    semrepo-contributions.ttl Contribution
    semrepo-languages.ttl     LanguageUsage, ProgrammingLanguage
"""

# python generate_rdf_with_linking.py data/pilot data/rdf-4

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import quote
import hashlib

from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef

from semrepo.identifiers import (
    contribution_uri, github_account_uri, issue_uri, language_usage_uri,
    programming_language_uri, repository_snapshot_uri, repository_uri,
    source_repository_link_uri,
)

SR = Namespace("https://semrepo.org/ontology/v2#")
RESOURCE_NS = Namespace("https://semrepo.org/resource/")
DCTERMS = Namespace("http://purl.org/dc/terms/")
LPWC_CLASS = Namespace("https://linkedpaperswithcode.com/class/")
SOA_CLASS = Namespace("https://semopenalex.org/class/")

LPWC_KNOWLEDGE_GRAPH = "LPWC"
MLSEA_KNOWLEDGE_GRAPH = "MLSea"

LPWC_REPOSITORY_MATCH_METHOD = "lpwc-repository-url-match"
MLSEA_SAME_AS_METHOD = "lpwc-owl-sameAs"

LPWC_RELATION_CONFIG = {
    "hasOfficialRepository": {
        "relation_type": "official implementation of",
        "linking_method": "lpwc-curated-official-repository",
    },
    "hasRepository": {
        "relation_type": "repository referenced by",
        "linking_method": "lpwc-curated-repository-reference",
    },
}

def _read_jsonl(path: Path) -> Iterator[dict]:
    if not path.exists():
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    return datetime.fromisoformat(value) if value else None

_ACCOUNT_CLASSES = { #new 06.11
    "user": SR.GitHubUser,
    "organization": SR.GitHubOrganisation,
    "organisation": SR.GitHubOrganisation,
    "bot": SR.GitHubBot,
}

def _account_class(github_type: Optional[str]) -> URIRef: #new 06.11
    """
    Unknown or missing types are represented as generic GitHubAccount.
    """
    normalized_type = (github_type or "").strip().lower()
    return _ACCOUNT_CLASSES.get(normalized_type, SR.GitHubAccount)

def _add_account(graph: Graph, github_id: int, login: str, github_type: Optional[str]) -> URIRef:
    uri = URIRef(github_account_uri(github_id))
    graph.add((uri, RDF.type, SR.GitHubAccount)) #new 06.11 Every account is explicitly typed as a GitHubAccount.
    # graph.add((uri, RDF.type, _account_class(github_type))) # more specific type when it is known.
    account_class = _account_class(github_type)
    if account_class != SR.GitHubAccount:
        graph.add((uri, RDF.type, account_class))
    graph.add((uri, SR.githubUserId, Literal(github_id, datatype=XSD.integer)))
    graph.add((uri, SR.githubLogin, Literal(login)))
    graph.add((uri, SR.profileUrl, Literal(f"https://github.com/{login}", datatype=XSD.anyURI)))
    return uri

def _int(value) -> Literal:
    return Literal(int(value), datatype=XSD.integer)


def license_uri(spdx_id: str) -> URIRef:
    """Real SPDX ids -> official SPDX IRI. GitHub's 'NOASSERTION' (license
    file present but not recognised) is not an SPDX license, so it gets a
    SemRepo-local IRI instead of a fake spdx.org one."""
    if spdx_id == "NOASSERTION":
        return URIRef(RESOURCE_NS["license/NOASSERTION"])
    return URIRef(f"https://spdx.org/licenses/{quote(spdx_id, safe='.-+')}")


def topic_uri(topic: str) -> URIRef:
    return URIRef(RESOURCE_NS[f"topic/{quote(topic.lower(), safe='-')}"])


def _new_graph() -> Graph:
    g = Graph()
    g.bind("sr", SR)
    g.bind("res", RESOURCE_NS)
    return g


def add_repositories(graph: Graph, path: Path) -> int:
    count = 0
    for rec in _read_jsonl(path):
        uri = URIRef(repository_uri(rec["github_repository_id"]))
        graph.add((uri, RDF.type, SR.Repository))
        graph.add((uri, SR.githubRepositoryId, Literal(rec["github_repository_id"], datatype=XSD.integer)))
        graph.add((uri, SR.canonicalUrl, Literal(rec["canonical_url"], datatype=XSD.anyURI)))
        if rec.get("created_at"):
            graph.add((uri, SR.createdAt, Literal(rec["created_at"], datatype=XSD.dateTime)))
        count += 1
    return count


def add_snapshots(graph: Graph, path: Path) -> int:
    count = 0
    for rec in _read_jsonl(path):
        repo_uri = URIRef(repository_uri(rec["repository_github_id"]))
        collected_at = _parse_dt(rec["collected_at"])
        snap_uri = URIRef(repository_snapshot_uri(rec["repository_github_id"], collected_at))

        graph.add((snap_uri, RDF.type, SR.RepositorySnapshot))
        graph.add((snap_uri, SR.collectedAt, Literal(rec["collected_at"], datatype=XSD.dateTime)))
        graph.add((snap_uri, SR.snapshotOf, repo_uri))
        graph.add((repo_uri, SR.hasSnapshot, snap_uri))

        for key, prop in (("stars_count", SR.starsCount), ("forks_count", SR.forksCount),
                          ("open_issues_count", SR.openIssuesCount), ("watchers_count", SR.watchersCount),
                          ("size_kb", SR.sizeKb)):
            if rec.get(key) is not None:
                graph.add((snap_uri, prop, _int(rec[key])))
        for key, prop in (("description", SR.description), ("repository_name", SR.repositoryName),
                          ("full_name", SR.fullName), ("default_branch", SR.defaultBranch)):
            if rec.get(key):
                graph.add((snap_uri, prop, Literal(rec[key])))
        for key, prop in (("archived", SR.archived), ("is_fork", SR.isFork)):
            if rec.get(key) is not None:
                graph.add((snap_uri, prop, Literal(rec[key], datatype=XSD.boolean)))
        for key, prop in (("pushed_at", SR.pushedAt), ("updated_at", SR.updatedAt),
                          ("last_commit_at", SR.lastCommitAt)):
            if rec.get(key):
                graph.add((snap_uri, prop, Literal(rec[key], datatype=XSD.dateTime)))
        if rec.get("homepage_url"):
            graph.add((snap_uri, SR.homepageUrl, Literal(rec["homepage_url"], datatype=XSD.anyURI)))

        if rec.get("license_spdx_id"):
            lic = license_uri(rec["license_spdx_id"])
            graph.add((lic, RDF.type, SR.License))
            graph.add((lic, SR.spdxId, Literal(rec["license_spdx_id"])))
            if rec.get("license_name"):
                graph.add((lic, SR.licenseName, Literal(rec["license_name"])))
            graph.add((snap_uri, SR.hasLicense, lic))

        for topic in rec.get("topics") or []:
            t = topic_uri(topic)
            graph.add((t, RDF.type, SR.Topic))
            graph.add((t, SR.topicName, Literal(topic)))
            graph.add((snap_uri, SR.hasTopic, t))

        if rec.get("primary_language"):
            lang = URIRef(programming_language_uri(rec["primary_language"]))
            graph.add((lang, RDF.type, SR.ProgrammingLanguage))
            graph.add((lang, SR.languageName, Literal(rec["primary_language"])))
            graph.add((snap_uri, SR.primaryLanguage, lang))

        if rec.get("owner_github_id") is not None and rec.get("owner_login"):
            owner = _add_account(graph, rec["owner_github_id"], rec["owner_login"], rec.get("owner_type"))
            graph.add((snap_uri, SR.ownerAccount, owner))
        count += 1
    return count


def add_source_repository_links(graph: Graph, path: Path) -> int:
    count = 0
    for rec in _read_jsonl(path):
        uri = URIRef(source_repository_link_uri(rec["original_repository_url"]))
        graph.add((uri, RDF.type, SR.SourceRepositoryLink))
        graph.add((uri, SR.originalRepositoryUrl, Literal(rec["original_repository_url"], datatype=XSD.anyURI)))
        graph.add((uri, SR.resolutionStatus, SR[rec["resolution_status"]]))
        if rec.get("final_resolved_url"):
            graph.add((uri, SR.finalResolvedUrl, Literal(rec["final_resolved_url"], datatype=XSD.anyURI)))
        if rec.get("resolved_repository_github_id") is not None:
            graph.add((uri, SR.resolvedRepository, URIRef(repository_uri(rec["resolved_repository_github_id"]))))
        count += 1
    return count


def add_collection_activities(graph: Graph, path: Path) -> int:
    count = 0
    for rec in _read_jsonl(path):
        from semrepo.identifiers import collection_activity_uri
        uri = URIRef(collection_activity_uri(
            rec["attempted_url"], _parse_dt(rec["collection_timestamp"]), rec["collection_source"]
        ))
        graph.add((uri, RDF.type, SR.CollectionActivity))
        graph.add((uri, SR.collectionTimestamp, Literal(rec["collection_timestamp"], datatype=XSD.dateTime)))
        graph.add((uri, SR.attemptedUrl, Literal(rec["attempted_url"], datatype=XSD.anyURI)))
        graph.add((uri, SR.collectionSource, Literal(rec["collection_source"])))
        graph.add((uri, SR.collectionStatus, SR[rec["collection_status"]]))
        if rec.get("resulted_in_repository_github_id") is not None:
            graph.add((uri, SR.resultedInRepository, URIRef(repository_uri(rec["resulted_in_repository_github_id"]))))
        count += 1
    return count


def add_issues(graph: Graph, path: Path) -> int:
    count = 0
    for rec in _read_jsonl(path):
        uri = URIRef(issue_uri(rec["github_issue_id"]))
        graph.add((uri, RDF.type, SR.PullRequest if rec.get("is_pull_request") else SR.Issue))
        graph.add((uri, SR.githubIssueId, Literal(rec["github_issue_id"], datatype=XSD.integer)))
        graph.add((uri, SR.issueNumber, Literal(rec["issue_number"], datatype=XSD.integer)))
        graph.add((uri, SR.issueState, Literal(rec["issue_state"])))
        graph.add((uri, SR.issueCreatedAt, Literal(rec["issue_created_at"], datatype=XSD.dateTime)))
        if rec.get("issue_closed_at"):
            graph.add((uri, SR.issueClosedAt, Literal(rec["issue_closed_at"], datatype=XSD.dateTime)))
        if rec.get("issue_title"):
            graph.add((uri, SR.issueTitle, Literal(rec["issue_title"])))
        if rec.get("issue_url"):
            graph.add((uri, SR.issueUrl, Literal(rec["issue_url"], datatype=XSD.anyURI)))
        if rec.get("issue_updated_at"):
            graph.add((uri, SR.issueUpdatedAt, Literal(rec["issue_updated_at"], datatype=XSD.dateTime)))
        if rec.get("issue_comment_count") is not None:
            graph.add((uri, SR.issueCommentCount, _int(rec["issue_comment_count"])))
        for label in rec.get("issue_labels") or []:
            graph.add((uri, SR.issueLabel, Literal(label)))
        if rec.get("is_pull_request") and rec.get("pull_request_merged_at"):
            graph.add((uri, SR.pullRequestMergedAt, Literal(rec["pull_request_merged_at"], datatype=XSD.dateTime)))
        if rec.get("issue_author_github_id") is not None and rec.get("issue_author_login"):
            author = _add_account(graph, rec["issue_author_github_id"], rec["issue_author_login"],
                                  rec.get("issue_author_type"))
            graph.add((uri, SR.issueAuthor, author))
        repo_uri = URIRef(repository_uri(rec["belongs_to_repository_github_id"]))
        graph.add((uri, SR.belongsToRepository, repo_uri))
        graph.add((repo_uri, SR.hasIssue, uri))
        count += 1
    return count


def add_contributions(graph: Graph, path: Path) -> int:
    """Contributor class comes from GitHub's 'type' field (see module docstring)."""
    count = 0
    for rec in _read_jsonl(path):
        collected_at = _parse_dt(rec["snapshot_collected_at"])
        uri = URIRef(contribution_uri(rec["repository_github_id"], collected_at, rec["contributor_github_user_id"]))
        snap_uri = URIRef(repository_snapshot_uri(rec["repository_github_id"], collected_at))

        account_uri = _add_account(graph, rec["contributor_github_user_id"], rec["contributor_github_login"],
                                   rec.get("contributor_account_type"))

        graph.add((uri, RDF.type, SR.Contribution))
        graph.add((uri, SR.contributionToSnapshot, snap_uri))
        graph.add((uri, SR.contributor, account_uri))
        graph.add((uri, SR.commitCount, _int(rec["commit_count"])))
        count += 1
    return count


def add_language_usage(graph: Graph, path: Path) -> int:
    count = 0
    for rec in _read_jsonl(path):
        collected_at = _parse_dt(rec["snapshot_collected_at"])
        uri = URIRef(language_usage_uri(rec["repository_github_id"], collected_at, rec["language_name"]))
        lang_uri = URIRef(programming_language_uri(rec["language_name"]))
        snap_uri = URIRef(repository_snapshot_uri(rec["repository_github_id"], collected_at))

        graph.add((lang_uri, RDF.type, SR.ProgrammingLanguage))
        graph.add((lang_uri, SR.languageName, Literal(rec["language_name"])))

        graph.add((uri, RDF.type, SR.LanguageUsage))
        graph.add((uri, SR.languageUsageIn, snap_uri))
        graph.add((uri, SR.programmingLanguage, lang_uri))
        graph.add((uri, SR.languageBytes, _int(rec["language_bytes"])))
        count += 1
    return count


def external_link_uri(source_uri: str, target_uri: str, relation_type: str, linking_method: str) -> URIRef:
    """Generate a deterministic URI for an ExternalLink."""
    key = "|".join([source_uri, target_uri, relation_type, linking_method])
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return URIRef(RESOURCE_NS[f"external-link/{digest}"])

def add_external_links(graph: Graph, path: Path) -> int:
    """Generate SemRepo repository -> LPWC and MLSea external links."""
    count = 0

    def add_link(
        source_uri: URIRef,
        target_uri: str,
        relation_type: str,
        linking_method: str,
        knowledge_graph: str,
    ) -> None:
        nonlocal count

        if not target_uri:
            return

        link_uri = external_link_uri(str(source_uri), target_uri, relation_type, linking_method)
        if (source_uri, SR.hasExternalLink, link_uri) in graph:
            return

        graph.add((source_uri, SR.hasExternalLink, link_uri))
        graph.add((link_uri, RDF.type, SR.ExternalLink))
        graph.add((link_uri, SR.linkSource, source_uri))
        graph.add((link_uri, SR.linkTarget, Literal(target_uri, datatype=XSD.anyURI)))
        graph.add((link_uri, SR.linkRelationType, Literal(relation_type, datatype=XSD.string)))
        graph.add((link_uri, SR.linkingMethod, Literal(linking_method, datatype=XSD.string)))
        graph.add((link_uri, SR.targetKnowledgeGraph, Literal(knowledge_graph, datatype=XSD.string)))
        count += 1

    for rec in _read_jsonl(path):
        github_id = rec.get("github_repository_id")
        if github_id is None:
            continue

        source_uri = URIRef(repository_uri(github_id))

        for match in rec.get("lpwc_repository_matches") or []:
            lpwc_repository = match.get("lpwc_repository_uri")
            if not lpwc_repository:
                continue

            # 1. SemRepo Repository -> LPWC Repository
            add_link(source_uri, lpwc_repository, "same repository as", LPWC_REPOSITORY_MATCH_METHOD, LPWC_KNOWLEDGE_GRAPH)

            # 2. SemRepo Repository -> LPWC Paper
            for paper in match.get("papers") or []:
                paper_uri = paper.get("lpwc_paper_uri")
                if not paper_uri or not paper_uri.startswith("https://linkedpaperswithcode.com/paper/"):
                    continue

                for relation in paper.get("repository_relations") or []:
                    relation_config = LPWC_RELATION_CONFIG.get(relation)
                    if not relation_config:
                        print(f"Warning: unsupported LPWC relation '{relation}' for {paper_uri}")
                        continue

                    add_link(source_uri, paper_uri, relation_config["relation_type"], relation_config["linking_method"], LPWC_KNOWLEDGE_GRAPH)

            # 3. SemRepo Repository -> MLSea Software
            for mlsea_uri in match.get("mlsea_software_uris") or []:
                add_link(source_uri, mlsea_uri, "same software as", MLSEA_SAME_AS_METHOD, MLSEA_KNOWLEDGE_GRAPH)

    return count

def add_lpwc_authorship(graph: Graph, path: Path) -> int:
    """Generate LPWC paper -> SemOpenAlex author relationships using dcterms:creator."""
    count = 0

    for rec in _read_jsonl(path):
        for match in rec.get("lpwc_repository_matches") or []:
            for paper in match.get("papers") or []:
                paper_uri = paper.get("lpwc_paper_uri")
                if not paper_uri or not paper_uri.startswith("https://linkedpaperswithcode.com/paper/"):
                    continue

                paper_ref = URIRef(paper_uri)

                for author in paper.get("authors") or []:
                    author_uri = author.get("lpwc_author_uri")
                    if not author_uri:
                        continue

                    triple = (paper_ref, DCTERMS.creator, URIRef(author_uri))
                    if triple not in graph:
                        graph.add(triple)
                        count += 1

    return count

def generate_rdf(input_dir: Path, output_dir: Path) -> dict:
    """Reads all JSONL files in input_dir (WP4.6/pipeline.py's output) and
    writes the five .ttl files described in the module docstring. Returns
    a dict of {file: triple_count} for the "which input/config did you
    use" note the proposal (and Michael) ask for alongside any sample."""
    output_dir.mkdir(parents=True, exist_ok=True)
    counts = {}

    core = _new_graph()
    counts["repositories"] = add_repositories(core, input_dir / "repositories.jsonl")
    counts["source_repository_links"] = add_source_repository_links(core, input_dir / "source-repository-links.jsonl")
    counts["collection_activities"] = add_collection_activities(core, input_dir / "collection-activities.jsonl")
    core.serialize(destination=output_dir / "semrepo-core.ttl", format="turtle")

    snapshots = _new_graph()
    counts["snapshots"] = add_snapshots(snapshots, input_dir / "snapshots.jsonl")
    snapshots.serialize(destination=output_dir / "semrepo-snapshots.ttl", format="turtle")

    issues = _new_graph()
    counts["issues"] = add_issues(issues, input_dir / "issues.jsonl")
    issues.serialize(destination=output_dir / "semrepo-issues.ttl", format="turtle")

    contributions = _new_graph()
    counts["contributions"] = add_contributions(contributions, input_dir / "contributions.jsonl")
    contributions.serialize(destination=output_dir / "semrepo-contributions.ttl", format="turtle")

    languages = _new_graph()
    counts["language_usage"] = add_language_usage(languages, input_dir / "language-usage.jsonl")
    languages.serialize(destination=output_dir / "semrepo-languages.ttl", format="turtle")

    # LPWC and SemOpenAlex and MLSea external linking
    lpwc_input = input_dir / "external-links.jsonl"
    external_links = _new_graph()
    external_links.bind("dcterms", DCTERMS)
    counts["external_links"] = add_external_links(external_links, lpwc_input)
    external_links.serialize(destination=output_dir / "semrepo-external-links.ttl", format="turtle")

    # LPWC paper -> SemOpenAlex author relationships
    authorship = _new_graph()
    authorship.bind("dcterms", DCTERMS)
    counts["lpwc_authorship"] = add_lpwc_authorship(authorship, lpwc_input)
    authorship.serialize(destination=output_dir / "semrepo-author-profiles-links.ttl", format="turtle")

    return counts

if __name__ == "__main__":
    import sys

    input_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/pilot")
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("data/rdf")

    counts = generate_rdf(input_dir, output_dir)
    print(f"Input: {input_dir.resolve()}")
    print(f"Output: {output_dir.resolve()}")
    for key, value in counts.items():
        print(f"  {key}: {value} records")


# ~/semrepo-pipeline$ python generate_rdf_with_linking.py data/out-jsonl/1_5000/ data/rdf/1_5000

# Input: /home/yunisusan/semrepo-pipeline/data/out-jsonl/1_5000
# Output: /home/yunisusan/semrepo-pipeline/data/rdf/1_5000
#   repositories: 2 records
#   source_repository_links: 2 records
#   collection_activities: 6 records
#   snapshots: 2 records
#   issues: 10 records
#   contributions: 8 records
#   language_usage: 1 records
#   external_links: 5 records
#   lpwc_authorship: 5 records

### Linking validation

# Query 1 — SemRepo repositories linked to LPWC papers
# PREFIX sr: <https://semrepo.org/ontology/v2#>

# SELECT ?repository ?paper ?relation ?method
# WHERE {
#     ?repository sr:hasExternalLink ?link .

#     ?link sr:linkTarget ?paper ;
#           sr:linkRelationType ?relation ;
#           sr:linkingMethod ?method .

#     FILTER(CONTAINS(STR(?paper),
#         "linkedpaperswithcode.com/paper/"))
# }

## Query 2 — LPWC papers linked to SemOpenAlex authors
# PREFIX dcterms: <http://purl.org/dc/terms/>

# SELECT ?paper ?author
# WHERE {
#     ?paper dcterms:creator ?author .
# }