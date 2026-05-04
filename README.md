## SemRepo

### Overview

[**SemRepo**](https://semrepo.org/) is a fine-grained RDF knowledge graph with over 81 million triples on nearly 200,000 GitHub repositories linked to scientific research. It captures repository-level metadata (e.g., contributors, issues, dependencies, programming languages) and interlinks this information with external scholarly knowledge graphs: repository authors are linked to their profiles in [SemOpenAlex](https://semopenalex.org/), repositories are connected to publications in [LinkedPapersWithCode(LPWC)](https://linkedpaperswithcode.com/), and research artifacts (e.g., datasets, experiments) are linked via [MLSea KG](https://dtai-kg.github.io/MLSea-KGC/). Overall, SemRepo provides an important infrastructure for large-scale analysis of software within the broader scientific research ecosystem.

We release **SemRepo** as an open resource at  [https://semrepo.org](https://semrepo.org/), including data, code, and query services:

1. **Data Access**  
   RDF data dumps are available via [Zenodo](https://zenodo.org/records/15399468). The dataset is periodically updated (approx. twice per year), subject to upstream data availability.

2. **Query Services**  
   The dataset is hosted in a public triple store with a SPARQL endpoint at https://semrepo.org/sparql.

3. **Open-source Pipeline**  
   We provide an open-source pipeline for automated knowledge graph construction and cross-source entity alignment, supporting reproducibility and future extensions. See "SemRepo Construction Pipeline" below.

### Ontology and Design

Adhering to Linked Open Data best practices, we publish the full ontology in OWL, along with a VoID description that documents dataset statistics and interlinks, available in [ontologies](./ontologies).

![Knowledge Graph Schema](https://raw.githubusercontent.com/faerber-lab/SemRepo/main/assets/kg-schema.png)
  
### Competency Questions and Use Cases

We demonstrate and evaluate the utility of SemRepo through:

- [Competency Questions (CQs)](./CQs)  
We formulate competency questions to demonstrate SemRepo’s analytical capabilities for non-trivial analyses. Its integration within broader scholarly ecosystems enables tasks that are difficult to perform with existing resources in isolation, such as research provenance reconstruction across repositories and publications, and systematic identification of risks to research reproducibility. All SPARQL queries used for the CQs are available in [CQs](./CQs).

- [Reproducibility and Sustainability Analysis](./usecase)  
  We conduct a empirical reproducibility-auditing study on a sample of 20,000 repositories from SemRepo that are linked to scientific publications. All resources for this use case is available in [usecase](./usecase). This use case demonstrates how SemRepo supports large-scale empirical analyses of research reproducibility, highlighting systemic challenges in maintaining reproducible research ecosystems.

### SemRepo Construction Pipeline

- **Repository and Metadata Harvesting**  
  We collect repository data and metadata using dedicated [Python scripts](./crawling-gitHub-metadata). An overview of the crawled dataset is available in [JSON format](./assets/khuangaf_awesome-chart-understanding.json).  
  To extract libraries and dependencies used in the code, we utilize [scripts](./extract-libraries-from-code) that clone each repository and parse source files to identify imported packages.

- **RDF Knowledge Graph Construction and Linking**  
  We construct and interlink the repository metadata as an RDF knowledge graph using the provided [scripts](./making-repo-metadata-kg).
