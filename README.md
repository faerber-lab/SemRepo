# SemRepo

[**SemRepo**](https://semrepo.org/) is an RDF knowledge graph with over 81 million triples on nearly 200,000 GitHub repositories linked to scientific research. SemRepo captures fine-grained repository-level metadata (e.g., contributors, issues, dependencies, programming languages) and interlinks this information with external scholarly knowledge graphs: repositories are connected to publications in [LinkedPapersWithCode (LPWC)](https://linkedpaperswithcode.com/), repository authors are linked to their profiles in [SemOpenAlex](https://semopenalex.org/), and research artifacts (e.g., datasets, experiments) are linked via [MLSea KG](https://dtai-kg.github.io/MLSea-KGC/). SemRepo provides an important infrastructure for large-scale analysis of software within the broader scientific research ecosystem.

We release SemRepo as an open resource, with services and documentation available at: **[https://semrepo.org](https://semrepo.org/)**:

1. **Data Access**: RDF data dumps are available via [Zenodo](https://zenodo.org/records/15399468). The dataset is periodically updated (approx. twice per year).

2. **Query Services**: The dataset is hosted in a public triple store with a SPARQL endpoint at https://semrepo.org/sparql.

3. **Open-source Pipeline**: We release full source code for the knowledge graph construction and automatic interlinking, enabling future extensions of the dataset. See "SemRepo Construction Pipeline" below.

## Ontology and Design

Adhering to Linked Open Data best practices, we publish the [full ontology in OWL](./ontologies/SemRepo-ontology.owl), along with a [VoID description](./ontologies/VoID.ttl) that documents dataset statistics and interlinks.

![Knowledge Graph Schema](https://raw.githubusercontent.com/faerber-lab/SemRepo/main/assets/kg-schema.png)

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

### Installation

Clone the repository and install the required dependencies:

```bash
git clone https://github.com/faerber-lab/SemRepo.git
cd SemRepo
pip install -r requirements.txt
```
Ensure you are using Python 3.10 or higher. The pipeline then follows the following steps:

- **Repository and Metadata Harvesting**  
  We collect repository data and metadata using dedicated [scripts](./crawling-gitHub-metadata). An overview of the crawled dataset is available in [JSON format](./assets/khuangaf_awesome-chart-understanding.json).  
  To extract libraries and dependencies used in the code, we utilize [scripts](./extract-libraries-from-code) that clone each repository and parse source files to identify imported packages.

- **RDF Knowledge Graph Construction and Linking**  
  We construct the RDF knowledge graph and interlink it with external scholarly knowledge graphs using the provided [scripts](./making-repo-metadata-kg).

## Usage

We demonstrate and evaluate the utility of SemRepo through:

- [Reproducibility and Sustainability Analysis Use Case](./usecase)  
  We conduct a empirical reproducibility-auditing study on a sample of 20,000 repositories from SemRepo that are linked to scientific publications. All resources for this use case is available in [usecase](./usecase). 

- [Competency Questions (CQs)](./CQs)  
We formulate competency questions to demonstrate SemRepo’s analytical capabilities for non-trivial analyses. SemRepo integration within broader scholarly ecosystems enables tasks that are difficult to perform with existing resources in isolation, e.g., research provenance reconstruction across repositories and publications. All SPARQL queries used for the CQs are available in [CQs](./CQs).


## Sustainability, Accessibility, and Ethical Considerations

SemRepo is designed as a sustainable and openly accessible dataset resource to support long-term reuse, reproducibility, and extension by the research community. All data, ontology definitions, and construction pipelines are released under open licenses to facilitate transparent and durable scientific use.

Accessibility is ensured through multiple access modalities, including downloadable RDF dumps and a public SPARQL endpoint, enabling both lightweight querying and full-scale local deployment. This design lowers barriers to entry for users without extensive computational resources or infrastructure.

From an ethical perspective, SemRepo is built on publicly available software and scholarly metadata sources. However, we acknowledge that the dataset inherits structural biases and coverage limitations from upstream platforms i.e., GitHub and the linked scholarly knowledge graphs. These include uneven representation across programming languages, geographic regions and languages, and research communities. We therefore emphasize transparent provenance, versioned releases, and periodic updates (**approximately twice per year***) to support responsible interpretation and use of the data.

_*Subject to upstream data availability_

#### 📧 Contact: michael.faerber@tu-dresden.de
