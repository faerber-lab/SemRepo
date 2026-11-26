# SemRepo

## Overview
[**SemRepo**](https://semrepo.org/) is a large-scale RDF knowledge graph of GitHub repositories linked to scientific research. SemRepo captures fine-grained repository-level metadata (e.g., _contributors, issues, dependencies, programming languages_) and interlinks this information with external scholarly knowledge graphs: repositories are connected to publications in [LPWC](https://linkedpaperswithcode.com/), repository authors are linked to their profiles in [SemOpenAlex](https://semopenalex.org/), and research artifacts (e.g., _datasets, experiments_) are linked via [MLSea KG](https://dtai-kg.github.io/MLSea-KGC/). SemRepo provides an important infrastructure for large-scale analysis of software within the broader scientific research ecosystem.

1. **Data Access**: RDF data dumps are available via Zenodo [DOI:10.5281/zenodo.15399467](https://doi.org/10.5281/zenodo.15399467) and are periodically updated (see [Maintenance](#maintenance)).

2. **Query Services**: SemRepo is hosted in a public triple store with a SPARQL endpoint: [https://semrepo.org/sparql](https://semrepo.org/sparql). Please note that the endpoint is **currently under maintenance** and may not return the latest data.

3. **Open-source Pipeline**: Full source code for SemRepo construction and interlinking, supporting future extensions of SemRepo.

🌐 Website: **[https://semrepo.org](https://semrepo.org/)**

## Contents

- [Ontology and Metadata Descriptions](#ontology-and-metadata-descriptions)
- [Key Statistics](#key-statistics)
- [Construction and Validation Pipeline](#construction-and-validation-pipeline)
- [Example Usage: CQs, Use Cases, Queries](#example-usage)
- [Repository Structure](#repository-structure)
- [License](#license)
- [FAIR, Sustainability, and Ethical Compliance](#fair-sustainability-and-ethical-compliance)
- [Citation](#citation)
- [Maintenance](#maintenance)

---


## Ontology and Metadata Descriptions

Following Linked Open Data and FAIR best practices, SemRepo provides machine-readable ontology and dataset metadata descriptions:

- [SemRepo Ontology (OWL)](./ontologies/semrepo-v2.ttl)
- [DCAT + VoID + PROV-O Description](./data/semrepov2-dcat-void-prov.ttl) — A DCAT + VoID dataset metadata file with PROV-O provenance and full ETL pipeline documentation

![Knowledge Graph Schema](https://raw.githubusercontent.com/faerber-lab/SemRepo/main/assets/kg-schema.png)

## Key Statistics

The following statistics are reported as of November 2026. 

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

## Construction and Validation Pipeline

See the detailed construction pipeline in [/src](./src).

### RDF Triple Store Setup

To explore the knowledge graph and query the data using SPARQL, the RDF data needs to be loaded into an RDF triple store. After downloading the full RDF dumps, extract the archive and load the RDF data into an RDF triple store. We provide setup examples for loading the graph into [Openlink Virtuoso RDF triple store](https://virtuoso.openlinksw.com/), see the detailed setup in [virtuoso](./virtuoso).

### Data Validation

_to be updated._ To validate the syntactistructural consistency of the knowledge graph, run the queries here: [src/evaluation/](./src/evaluation/). These checks targeted various aspects of structural consistency, such as missing required properties, invalid or unexpected datatypes, and inconsistent class assignments. 

Additionally, the coverage and validity was evaluated using [N] competency questions (CQs) defined by expert to assess the graph's core retrieval and relational capabilities. For each CQ, a SPARQL query was executed, and the results were manually compared with the expected answers. See the CQs and their SPARQL queries here: [cqs-queries](./cqs-queries)

## Query and Usage Examples

We provide SPARQL query examples for exploring the knowledge graph; refer to [cqs-queries](./cqs-queries).

## Repository Structure

- `/assets` — figures and other materials
- `/cqs-queries` — competency questions and query examples
- `/ontologies` — Ontology and machine-readable data description files 
- `/src-v1` — Source code for previous version of SemRepo
- sample-data
- `/src` — Complete implementation source code and documentation
- `/assets` — figures and other materials
- `/usecase-examples` — figures and other materials
- `/virtuoso` – Docker settings for the Virtuoso triple store.
- requirements.txt

## License

- **Dataset**: [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/)
- **Ontology**: [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/)
- **Source Code**: [MIT License](https://opensource.org/licenses/MIT)

SemRepo-V2 is released under the CC0 license to maximize reuse and interoperability; users are nevertheless encouraged to cite the associated publication and dataset, see [Citation](#citation)).

## FAIR, Sustainability, and Ethical Compliance

SemRepo follows the FAIR data principles to support long-term usability, reproducibility, and integration within the scholarly data ecosystem. The dataset is publicly available via Zenodo, GitHub, and the project website through RDF dumps and a public SPARQL endpoint. Interoperability is ensured through open standards (RDF, OWL, SPARQL, VoID) and interlinking with external scholarly knowledge graphs, while reusability is supported through open licensing and the release of the full construction pipeline.

SemRepo provides versioned releases with periodic updates (annually or semi-annualy), accompanied by dissemination of each release via Github and website. SemRepo is constructed exclusively from publicly available software and scholarly metadata. We acknowledge that inherited biases and coverage limitations from upstream sources (e.g., GitHub and linked scholarly knowledge graphs) may affect representation across research communities and regions.

See details: [Open Science & Compliance Overview](https://semrepo.org/index.php/open-science/)

## Citation

_to be added_

## Maintenance

SemRepo-V2 follows a versioned release cycle with periodic updates (anually, subject on resource availability), with each release announced via project website and Github. 

SemRepo is maintained by the [Faerber Lab Research Group](https://faerber-lab.github.io/) at ScaDS.AI, TU Dresden.  
📧 Contact: [michael.faerber@tu-dresden.de](mailto:michael.faerber@tu-dresden.de)
