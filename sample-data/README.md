# SemRepo v2 — sample data

Complete input and output for a few repositories of the release: the JSONL records
collected and linked by the pipeline (`jsonl/`) and the RDF generated from them (`rdf/`).
The repositories were chosen to cover the main cases of the pipeline.
E-mail addresses are removed. Regenerate the RDF of one repository with:

```bash
python3 src/generate_rdf_with_linking.py sample-data/<folder>/jsonl <output dir>
```

| Repository | Shows | Issues + PRs | Linked papers | SHACL |
|---|---|---|---|---|
| [ZeweiChu__MQR](https://github.com/ZeweiChu/MQR) | Official implementation of a paper, linked to a SemOpenAlex work and to MLSea | 2 | 1 | conforms |
| [DerwenAI__pytextrank](https://github.com/DerwenAI/pytextrank) | Repository renamed or transferred since the paper (resolved via redirect) | 274 | 4 | conforms |
| [OpenDriveLab__ThinkTwice](https://github.com/OpenDriveLab/ThinkTwice) | Contributor matched to a SemOpenAlex author (published link) | 23 | 1 | conforms |
| [Mark12Ding__GNN-Practical-Attack](https://github.com/Mark12Ding/GNN-Practical-Attack) | Fuzzy contributor match below the RDF threshold (kept in JSONL, not published in RDF) | 3 | 2 | conforms |
| [senwu__emmental-tutorials](https://github.com/senwu/emmental-tutorials) | Issues and pull requests, including bot-authored ones | 22 | 1 | conforms |
| [Kaimaoge__IGNNK](https://github.com/Kaimaoge/IGNNK) | Several linked papers (official and referencing) | 10 | 3 | conforms |
| [imavijit__detect-it](https://github.com/imavijit/detect-it) | Linked papers with LPWC tasks and research areas | 0 | 1 | conforms |
| [facebookresearch__fairseq2](https://github.com/facebookresearch/fairseq2) | Issue cap reached (1,000 issues and pull requests) | 1,000 | 1 | conforms |
| [haochen-rye__LSTD](https://github.com/haochen-rye/LSTD) | Contributor cap reached (100 contributors) | 11 | 1 | conforms |
| [cisco-open__DeepVision](https://github.com/cisco-open/DeepVision) | No LPWC match for the resolved repository | 77 | 0 | conforms |
