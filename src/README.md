## SemRepo Construction Pipeline

### Prerequisites

Install the required dependencies:

```bash
pip install -r requirements.txt
```

Ensure you are using Python 3.10 or higher. The pipeline then follows the following steps:

### Data Harvesting
Harvest repository metadata from GitHub using the provided repository URL collections:

```bash
python harvest_github_metadata.py data/github_urls/ data/out-test

# 2026-11-07 15:19:22,134 INFO Found 1 .pkl files
# 2026-11-07 15:19:22,135 INFO Processing collection: 1_5000.pkl
# 2026-11-07 15:19:22,141 INFO Loaded 20 repository URLs
# 2026-11-07 15:19:26,113 INFO Completed collection: 1_5000.pkl
# ....
# 2026-11-07 15:19:26,114 INFO Output written to: /home/yunisusan/semrepo-pipeline/data/out-test/1_5000
# 2026-11-07 15:19:26,114 INFO All collections processed.
```
Examples of the harvested JSON data are available in [data/out-test](./data/out-test).

### Linking to external KGs 
Connect to external knowledge graphs to generate linking data. This process also performs name-based alignment:
   
  ```bash
  python linking.py data/out-test/1_5000/

  # Linked repository 790680512: 0 contributor matches
  # Linked repository 741251289: 0 contributor matches
  # Linked repository 823210233: 0 contributor matches
  # Linked repository 408447491: 1 contributor matches
  # Linked repository 645270986: 2 contributor matches
  # Linked repository 705126352: 1 contributor matches
  # Linked repository 450564762: 0 contributor matches
  # Results written to: data/out-test/1_5000/external-links.jsonl
  # Match reviews written to: data/out-test/1_5000/github-soa-match-review.jsonl
  ```

This process generates two files, _external-links.jsonl_ and _github-soa-match-review.jsonl_, which are saved in the harvested JSON metadata directory. An example of the generated linking results is available in: [external-links.jsonl](./data/out-test/1_5000/external-links.jsonl). Fuzzy name-based matches are recorded separately for manual review, example in: [github-soa-match-review.jsonl](./data/out-test/1_5000/github-soa-match-review.jsonl). Please note that exact matches are not included in this review file.

### RDF Construction with Linking 
Generate RDF data for all the entities and relationships from the harvested metadata and link them to external knowledge graphs:
   
  ```bash
  python generate_rdf_with_linking.py data/out-test/1_5000/ data/rdf-test/1_5000

  # Input: /home/yunisusan/semrepo-pipeline/data/out-test/1_5000
  # Output: /home/yunisusan/semrepo-pipeline/data/rdf-test/1_5000
     # repositories: 7 records
     # source_repository_links: 20 records
     # collection_activities: 21 records
     # snapshots: 7 records
     # issues: 40 records
     # contributions: 25 records
     # language_usage: 9 records
     # external_links: 19 records
     # github_soa_author_links: 4 records
     # lpwc_authorship: 33 records
  ```
Examples of the generated RDF (.ttl) files are available in [data/rdf-test](./data/rdf-test).

### Validation (SemRepo-v1 version -- need to be updated to follow the new ontology model)
To validate the structural consistency of the knowledge graph, run the queries here: [missing properties checks](./tests/val-missingprop.sparql) and [datatypes checks](./tests/val-datatypes.sparql). These checks targeted various aspects of structural consistency, i.e., missing required properties, invalid or unexpected datatypes.
  
### Directory

- `/config` — # Configuration files
- `/data` — # Sample input data and generated outputs
- `/docs` — # Documentation and development notes
- `/semrepo` — # Main pipeline source code
- `/tests` — # Tests and validation queries
- requirements.txt — # Python dependencies
