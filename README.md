# SemRepo

[**SemRepo**](https://semrepo.org/) is an RDF knowledge graph with over 81 million triples on nearly 200,000 GitHub repositories linked to scientific research. SemRepo captures fine-grained repository-level metadata (e.g., contributors, issues, dependencies, programming languages) and interlinks this information with external scholarly knowledge graphs: repositories are connected to publications in [LPWC](https://linkedpaperswithcode.com/), repository authors are linked to their profiles in [SemOpenAlex](https://semopenalex.org/), and research artifacts (e.g., datasets, experiments) are linked via [MLSea KG](https://dtai-kg.github.io/MLSea-KGC/). SemRepo provides an important infrastructure for large-scale analysis of software within the broader scientific research ecosystem.

SemRepo’s services and documentation are available at: **[https://semrepo.org](https://semrepo.org/)**:

1. **Data Access**: RDF data dumps are available via [Zenodo (https://doi.org/10.5281/zenodo.15399468)](https://zenodo.org/records/15399468), and periodically updated (approx. twice per year).

2. **Query Services**: The dataset is hosted in a public triple store with SPARQL endpoint at https://semrepo.org/sparql.

3. **Open-source Pipeline**: We release the full source code for the knowledge graph construction and automatic interlinking, enabling future extensions of SemRepo.
4. **URI resolution** of the SemRepo Knowledge Graph within the Linked Open Data Cloud.

## Ontology Modeling

Adhering to Linked Open Data best practices, we publish the [full ontology in OWL](./ontologies/SemRepo-ontology.owl). Machine-readable metadata descriptions, including the dataset statistics and interlinks, are provided in [VoID](./ontologies/VoID.ttl) formats.

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

_*core classes only_

## Construction Pipeline

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

## Example Usage

We demonstrate and evaluate the utility of SemRepo through:
- [Competency Questions (CQs)](./CQs)  
We formulate competency questions to demonstrate SemRepo’s analytical capabilities for non-trivial analyses. SemRepo integration within broader scholarly ecosystems enables tasks that are difficult to perform with existing resources in isolation, e.g., research provenance reconstruction across repositories and publications. All SPARQL queries used for the CQs are available in [CQs](./CQs).

- [Reproducibility and Sustainability Analysis Use Case](./usecase)  
  We conduct a empirical reproducibility-auditing study on a sample of 20,000 repositories from SemRepo that are linked to scientific publications. All resources for this use case is available in [usecase](./usecase).

- [Additional examples of SPARQL queries](./CQs/example-sparql-queries.pdf) 

## License

- Dataset: CC0
- Ontology: CC0
- Source code: MIT License


## Repository Structure

- `/usecase` — SemRepo use cases i.e., reproducibility analysis
- `/ontologies` — OWL ontology and VoID files
- `/CQs` — competency questions
- `/crawling-gitHub-metadata` — github crawling 
- `/extract-libraries-from-code` — code dependencies and libraries harvesting
- `/making-repo-metadata-kg` — kg construction and interlinking
- `/assets` — figures 
- requirements.txt

## FAIR, Sustainability, and Ethical Compliance

SemRepo follows the FAIR data principles to support long-term usability, reproducibility, and integration within the scholarly data ecosystem. The dataset is publicly available via Zenodo, GitHub, and the project website through RDF dumps and a public SPARQL endpoint. Interoperability is ensured through open standards (RDF, OWL, SPARQL, VoID) and interlinking with external scholarly knowledge graphs, while reusability is supported through open licensing and the release of the full construction pipeline.

SemRepo provides versioned releases with periodic updates (approximately twice per year), supporting reproducibility and long-term sustainability.

The resource is constructed exclusively from publicly available software and scholarly metadata. We acknowledge that inherited biases and coverage limitations from upstream sources (e.g., GitHub and linked scholarly knowledge graphs) may affect representation across research communities and regions.

See details: [Open Science & Compliance Overview](https://semrepo.org/index.php/open-science/)

## Citation

If you use SemRepo, please cite:

```bibtex
@inproceedings{semrepo,
  title={SemRepo: A Knowledge Graph for Research Software and Its Scholarly Ecosystem.},
  author={Rafay, A., Lamprecht, D., Susanti, Y., & Färber, M.},
  year={2026}
}
```

## Maintenance

SemRepo is maintained by the [Faerber Lab Research Group](https://faerber-lab.github.io/team/) at TU Dresden.  
📧 Contact: [michael.faerber@tu-dresden.de](mailto:michael.faerber@tu-dresden.de)
