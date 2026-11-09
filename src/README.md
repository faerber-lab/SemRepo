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
python harvest_github_metadata.py data/github_urls/ data/out-jsonl

# 2026-11-07 15:19:22,134 INFO Found 1 .pkl files
# 2026-11-07 15:19:22,135 INFO Processing collection: 1_5000.pkl
# 2026-11-07 15:19:22,141 INFO Loaded 2 repository URLs
# 2026-11-07 15:19:26,113 INFO Completed collection: 1_5000.pkl
# 2026-11-07 15:19:26,113 INFO Resolution outcomes: {'Resolved': 2}
# 2026-11-07 15:19:26,113 INFO Records collected: {'issues': 10, 'contributions': 8, 'languages': 1}
# 2026-11-07 15:19:26,114 INFO Output written to: /home/yunisusan/semrepo-pipeline/data/out-test/1_5000
# 2026-11-07 15:19:26,114 INFO All collections processed.
```
Examples of the harvested JSON data are available in [/src/data/out-jsonl](./src/data/out-jsonl).

### RDF Construction and Linking 
Generate RDF data for all the entities and relationships from the harvested metadata and link them to external knowledge graphs:
   
  ```bash
  python generate_rdf_with_linking.py data/out-jsonl/1_5000/ data/rdf/1_5000

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
  ```
Examples of the generated RDF (.ttl) files are available in [/src/data/rdf](./src/data/rdf).

### Validation
To validate the structural consistency of the knowledge graph, run the queries here: [missing properties checks](./tests/val-missingprop.sparql) and [datatypes checks](./tests/val-datatypes.sparql). These checks targeted various aspects of structural consistency, i.e., missing required properties, invalid or unexpected datatypes.
  
### Directory

- `/config` — # Configuration files
- `/data` — # Sample input data and generated outputs
- `/docs` — # Documentation and development notes
- `/semrepo` — # Main pipeline source code
- `/tests` — # Tests and validation queries
- requirements.txt — # Python dependencies
