# SemRepo

[**SemRepo**](https://semrepo.org/) is an RDF knowledge graph with over 81 million triples on nearly 200,000 GitHub repositories linked to scientific research. SemRepo captures fine-grained repository-level metadata (e.g., contributors, issues, dependencies, programming languages) and interlinks this information with external scholarly knowledge graphs: repositories are connected to publications in [LinkedPapersWithCode (LPWC)](https://linkedpaperswithcode.com/), repository authors are linked to their profiles in [SemOpenAlex](https://semopenalex.org/), and research artifacts (e.g., datasets, experiments) are linked via [MLSea KG](https://dtai-kg.github.io/MLSea-KGC/). SemRepo provides an important infrastructure for large-scale analysis of software within the broader scientific research ecosystem.

We release **SemRepo** as an open resource at  [https://semrepo.org](https://semrepo.org/):

1. **Data Access**: RDF data dumps are available via [Zenodo](https://zenodo.org/records/15399468). The dataset is periodically updated (approx. twice per year), subject to upstream data availability.

2. **Query Services**: The dataset is hosted in a public triple store with a SPARQL endpoint at https://semrepo.org/sparql.

3. **Open-source Pipeline**: We provide an open-source pipeline for automated knowledge graph construction and cross-source entity alignment, supporting reproducibility and future extensions. See "SemRepo Construction Pipeline" below.

## Ontology and Design

Adhering to Linked Open Data best practices, we publish the [full ontology in OWL](./ontologies/SemRepo-ontology.owl), along with a [VoID description](./ontologies/VoID.ttl) that documents dataset statistics and interlinks.

![Knowledge Graph Schema](https://raw.githubusercontent.com/faerber-lab/SemRepo/main/assets/kg-schema.png)

## Competency Questions and Use Cases

We demonstrate and evaluate the utility of SemRepo through:

- [Reproducibility and Sustainability Analysis Use Case](./usecase)  
  We conduct a empirical reproducibility-auditing study on a sample of 20,000 repositories from SemRepo that are linked to scientific publications. All resources for this use case is available in [usecase](./usecase). 

- [Competency Questions (CQs)](./CQs)  
We formulate competency questions to demonstrate SemRepo’s analytical capabilities for non-trivial analyses. SemRepo integration within broader scholarly ecosystems enables tasks that are difficult to perform with existing resources in isolation, e.g., research provenance reconstruction across repositories and publications. All SPARQL queries used for the CQs are available in [CQs](./CQs).


## Key Statistics* (as of April 2026)
- **Repository**: 197,566  
- **Issues**: 2,609,510  
- **Organization**: 12,879  
- **Package**: 95,505  
- **Forked Repository**: 2,468,660  
- **Person**: 2,916,508  
- **Topic**: 272,378  
- **Programming Language**: 387,284
- **Linkage to LPWC**: 197,566
- **Linkage to SemOpenAlex**: 11,867
- **Linkage to MLSea**: 148,185.... (and more)

_*main class_
  
## SemRepo Construction Pipeline

- **Repository and Metadata Harvesting**  
  We collect repository data and metadata using dedicated [scripts](./crawling-gitHub-metadata). An overview of the crawled dataset is available in [JSON format](./assets/khuangaf_awesome-chart-understanding.json).  
  To extract libraries and dependencies used in the code, we utilize [scripts](./extract-libraries-from-code) that clone each repository and parse source files to identify imported packages.

- **RDF Knowledge Graph Construction and Linking**  
  We construct the RDF knowledge graph and interlink it with external scholarly knowledge graphs using the provided [scripts](./making-repo-metadata-kg).

#### 📧 Contact: michael.faerber@tu-dresden.de
