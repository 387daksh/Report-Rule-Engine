# RAG Architecture Research and Benchmark Plan

## Submission document

**Project:** AI-based analysis, benchmarking and quality monitoring of cybersecurity audit reports  
**Module:** Objective 3 - AI-based cybersecurity audit assessment  
**Environment:** Secure, local, air-gapped deployment  
**Date:** 25 August 2026

## 1. Executive conclusion

The existing `rag` implementation is a credible hybrid-RAG baseline, not a current best-in-class system. It combines structure-aware chunking, dense retrieval, BM25, reciprocal-rank fusion, cross-encoder reranking, CRAG-style checking, ICL, and schema-constrained Ollama generation. Its main weaknesses are experimental rather than cosmetic:

1. The default embedding and reranker (`BAAI/bge-m3` and `BAAI/bge-reranker-v2-m3`) are capable but were released in 2024; Qwen3 Embedding/Reranker (2025) is a stronger current candidate for local multilingual retrieval and ranking.
2. The current chunker is text-only in practice. `DoclingHybridChunker` imports Docling but falls back to the contextual text chunker, so tables, screenshots and page layout are not actually indexed as visual evidence.
3. Retrieval is single-query and flat. It has no query decomposition, field-aware retrieval, parent-child context expansion, reciprocal rank calibration, learned fusion, or late-interaction retrieval.
4. CRAG is an LLM judge and reformulator. The implementation now adds deterministic citation-boundary checks and an optional local claim verifier, but a calibrated abstention policy still needs a larger labelled test set.
5. The evaluation is too small to justify “SOTA”: one 5,369-character synthetic report, 12 questions, one fixed configuration, and gold chunks derived from the same chunking strategy.

**Implemented recommendation:** retain the current implementation as Baseline B0 and use the new optional modern profile for structured adaptive retrieval, parent-child expansion, graph-assisted retrieval, late interaction, visual page retrieval and local claim verification. The heavier model paths remain weight-dependent. Graph retrieval is selectable rather than forced onto every question.

## 2. What currently exists

### 2.1 Implemented baseline

The repository currently implements this flow:

`TXT/PDF parser -> structure-aware chunks -> BGE-M3 dense FAISS + BM25 -> RRF -> BGE cross-encoder -> CRAG judge/reformulation -> retrieval-few-shot prompt -> Ollama JSON schema -> substring/token-overlap grounding check`

The configuration uses 220-token chunks, 30-token overlap, top-40 candidates, top-5 final evidence chunks, `qwen2.5:7b`, zero temperature, and a 70% report pass threshold.

### 2.2 Observed completed run

The saved run `rag/src/results/1787426063_6d47ba9f8ee0` tested one report and 12 benchmark questions.

| Measure | Observed result | Interpretation |
|---|---:|---|
| Reports | 1 | No cross-report generalisation evidence |
| Questions | 12 | Useful smoke benchmark, not a statistically strong test set |
| Chunks | 10 | Small corpus; retrieval is an easy setting |
| Retrieval recall@5 | 1.00 | Every gold chunk appeared in top 5 |
| Retrieval precision@5 | 0.2833 | Four-fifths of returned context was non-gold under this labeling |
| MRR / NDCG@5 | 1.00 / 1.00 | Gold evidence was always ranked first, but labels overlap heavily |
| Answer accuracy | 0.9167 | 11/12 answers matched the gold answer |
| Macro-F1 | 0.6074 | Inflated/unstable interpretation because the abstention class had zero gold examples |
| Evidence grounding rate | 1.00 | Quote overlap check passed; this is not full claim entailment |
| CRAG correct retrieval rate | 0.3333 | The gate judged only one-third of retrievals correct |
| Mean generation latency | approximately 7-10 seconds | Local CPU/serving result from the saved run |
| Audit score | 33.33%, FAIL | Four of twelve requirements were satisfied |

The initial runs also recorded relative-path configuration failures when launched from the wrong working directory. The final completed run resolved paths to absolute paths. This should be covered by a reproducibility test.

### 2.3 What has not been demonstrated

The repository still does not demonstrate multilingual reports, XLSX annexures, or image reasoning. The two supplied real JSON reports now provide a controlled multi-report test, but they are not a statistically strong production benchmark and do not prove generalisation across agencies.

### 2.4 Actual modern-model tests completed

The downloaded Qwen3-Embedding-0.6B and Qwen3-Reranker-0.6B were loaded locally and evaluated on the same single report, same 10 structure-aware chunks, same 12 questions, and same gold labels as B0. The modern retrieval result was: Precision@5 0.2833, Recall@5 1.00, Hit Rate@5 1.00, MRR 1.00, and nDCG@5 1.00. It exactly tied B0 on this small benchmark. The machine's PyTorch installation was CPU-only, so the test took about 138 seconds; the RTX 4050 was not used by the active Python environment.

The modern end-to-end test used downloaded Qwen3-Embedding-0.6B, Qwen3-Reranker-0.6B and Qwen3-0.6B generation weights on the RTX 4050. It completed all 12 questions in about 457 seconds, with mean generation latency 27.3 seconds, 58.33% answer accuracy, macro-F1 0.2456, grounding 0.8333, and two human-review flags. It predicted No for all questions, so it is a valid integration result and a clear warning that the compact generator is not an acceptable final selection based on this run alone. The 8-chunk profile did not share B0's 220/30 gold chunk IDs, so its retrieval scores are not used for the model comparison; the separate valid retrieval test is saved in `results/modern_retrieval_benchmark.json`.

After installing Ollama Qwen3-8B, the same 12-question profile completed successfully on the RTX 4050 with CPU/GPU offload. It took about 22 minutes, achieved 100% lexical evidence grounding, CRAG correct-retrieval rate 16.67%, CRAG reformulation rate 50%, and an audit score of 33.33% (FAIL). The result confirms that Qwen3-8B runs on the laptop but does not by itself resolve the benchmark's retrieval/gold-label and prompt-calibration weaknesses. Full artifacts are in `results/qwen3_8b_run/1787660483_900adc72559a/`.

### 2.6 Supplied real-report benchmark

The two canonical JSON reports (`2-report.json` and `4-report.json`) were evaluated separately with eight source-derived yes/no questions per report. The two intermediate Markdown files were treated as extraction audit artifacts, not duplicate reports. The run used finding-level JSON parsing, PII redaction, CUDA-safe Qwen3 embeddings, BM25 plus dense retrieval, parent-child expansion, graph retrieval, CRAG, prompt-injection detection, and Qwen3-8B through Ollama. The GPU reranker and claim verifier were disabled for the 6 GB RTX 4050 so the generator could use the GPU.

For deployment safety, unsupported Yes/No outputs now fail closed to `Insufficient Evidence` and persisted model text is redacted before JSON/CSV output. Each run also emits `production_readiness_gate.json`; it requires independent balanced labels and minimum quality thresholds, so the current small benchmark is explicitly blocked from being called production evidence.

Across 16 questions, answer accuracy was 81.25%, macro-F1 0.4296, grounding 100%, retrieval Recall@8 87.50%, Precision@8 14.43%, MRR 0.2781, nDCG@8 0.4212, CRAG correct-retrieval rate 25.00%, CRAG reformulation rate 68.75%, and mean generation latency approximately 13.66 seconds. Per report, 2-report accuracy was 75.00% and 4-report accuracy was 87.50%; both audit scores passed the configured threshold (100.00% and 87.50%). These results are materially better after finding-level parsing, but they remain integration evidence rather than a production guarantee: the benchmark is small and source-derived, and the reranker/claim verifier need a separately calibrated deployment path.

### 2.5 Supplied production JSON input

The supplied PDF-extractor file `Best - FINAL_Optimized_Clean (1).json` is a recursive, partially flattened report object rather than a page array. The implemented JSON loader preserves nested paths, vulnerability fields, lists and metadata as searchable text, removes duplicate leaf rows, and ignores image/figure fields by design. A local verification produced 2,429 provenance-labelled rows and passed the JSON parser test. Image context is intentionally excluded from the current submission scope.

## 3. Research findings: architecture options

### 3.1 Strong current architecture families

| Architecture | Core idea | Best fit for this project | Main limitation |
|---|---|---|---|
| **B0: Current hybrid RAG** | Dense + BM25, RRF, cross-encoder, single prompt | Baseline and low-complexity fallback | Flat text retrieval; weak visual and multi-hop support |
| **B1: Modern structured hybrid RAG** | Layout-aware parsing, field-aware indexes, parent-child retrieval, dense+sparse+reranker, answer verification | Recommended default for individual report benchmark questions | More preprocessing and evaluation work |
| **B2: Late-interaction RAG** | Token-level multi-vector matching, e.g. ColBERT-style retrieval | Technical reports with exact terms, identifiers and mixed wording | Larger index and CPU/storage cost |
| **B3: Graph-assisted RAG** | Findings, assets, controls, evidence and recommendations form a graph; retrieve neighbors and source chunks | Cross-report agency trends, control coverage, repeated deficiencies, entity relations | Graph extraction errors and indexing cost; unnecessary for simple fact lookup |
| **B4: Visual document RAG** | Retrieve page images or visual tokens, preserving tables, layout and screenshots | Scanned reports, tables, figures, screenshots and evidence annexures | GPU/storage requirements; needs visual benchmark data |
| **B5: Agentic/adaptive RAG** | Query router chooses direct, decomposed, graph, visual, or abstention path; iterative retrieval | Complex questions and difficult evidence | More latency, more failure modes, harder to certify |

### 3.2 Model candidates for air-gapped use

| Role | Existing | Candidate to test | Reason |
|---|---|---|---|
| Generator | Qwen2.5 7B | Qwen3 8B/14B, with thinking enabled only for complex cases | Qwen3 supports thinking/non-thinking modes, multilingual improvements, and Apache 2.0 release claims in its 2025 technical report |
| Text embedding | BAAI/bge-m3 | Qwen3-Embedding-0.6B; Qwen3-Embedding-4B if hardware allows | Current multilingual embedding family; evaluate exact instruction format and dimensions |
| Reranker | BGE-reranker-v2-m3 | Qwen3-Reranker-0.6B; 4B for high-quality offline batch evaluation | 2025 model family with reported gains over BGE-reranker-v2-m3 on the model card's retrieval table |
| Late interaction | None | ColBERTv2 or a current multilingual ColBERT-compatible model | Better token-level matching for CVEs, controls and technical phrases |
| Visual retrieval | Text-only fallback | ColPali/ColQwen-style page retrieval | Directly uses page appearance, tables and layout instead of trusting OCR alone |
| OCR/layout | Docling fallback in practice | Docling plus explicit page/table/evidence artifacts; benchmark OCR alternatives if licensed | The current code does not exercise visual indexing |

Model selection must be made by local benchmark results, memory/latency measurements, license review, reproducible checksums, and security review. “Newer” is not enough.

## 4. Recommended target architecture

### 4.1 Ingestion and evidence objects

Create a canonical evidence store, not just a list of text chunks. Each evidence object should carry:

- report hash, report version, page number, section path and paragraph/table/figure identifier;
- exact text, table cells, image crop or screenshot reference;
- finding ID, asset, severity, CVE/CWE/CVSS, control mapping and recommendation links when extractable;
- extraction method, confidence, OCR status and source offsets;
- parent document/section/finding relationships.

Keep original files immutable and use content hashes. This is essential for review, benchmark versioning and air-gapped chain of custody.

### 4.2 Multi-index retrieval

Build independent but joinable indexes:

1. **Exact/field index:** CVE/CWE/CVSS, control IDs, IPs, URLs, finding IDs, dates and severity.
2. **Sparse index:** BM25 or a stronger learned sparse method for exact technical vocabulary.
3. **Dense index:** Qwen3-Embedding candidate and BGE-M3 baseline.
4. **Late-interaction index:** ColBERT candidate for difficult technical matching.
5. **Parent-child index:** retrieve small evidence spans, then expand to the finding, section and page context.
6. **Graph index:** optional entities and relations for cross-finding, cross-report and agency queries.
7. **Visual page index:** optional page/image retrieval for scanned or layout-heavy evidence.

Fuse by normalized scores or rank fusion, deduplicate by evidence lineage, rerank the candidate set, then expand context only after ranking. This is safer than placing five unrelated chunks directly into the prompt.

### 4.3 Query routing and answer policy

A deterministic router should classify each question into one or more modes:

- **Exact:** identifier, date, percentage, severity or named control.
- **Local semantic:** one finding or one report section.
- **Multi-hop:** finding -> asset -> evidence -> recommendation.
- **Cross-report/global:** agency, time trend, repeated deficiency or coverage aggregation.
- **Visual:** screenshot, table, chart or page-layout evidence.
- **Abstention:** no sufficient evidence, contradictory evidence, or unsupported scope.

The answerer should produce atomic claims, each linked to evidence IDs. A verifier should check:

1. cited evidence IDs exist and belong to the report;
2. each claim is entailed by the cited evidence;
3. all required parts of the benchmark question are covered;
4. contradictions are surfaced rather than averaged away;
5. insufficient evidence is returned when the evidence does not support Yes/No.

The final output should retain the existing JSON contract but add `claim_evidence`, `abstention_reason`, `contradictions`, `source_locations`, `model_versions`, and `benchmark_version`.

## 5. Controlled benchmark design

### 5.1 Corpus

Build a stratified corpus across the four initial domains:

| Dimension | Minimum target for a credible submission |
|---|---:|
| Domains | 4: VAPT, network, mobile, web/application |
| Reports | 40 minimum; 100 preferred |
| Agencies | At least 5, anonymised if necessary |
| Formats | PDF, scanned PDF, DOCX, TXT, XLSX annexure, image evidence |
| Languages | English baseline; Hindi/Indian-English variation if approved data exists |
| Questions | 25-50 per report across local, exact, multi-hop and abstention types |
| Gold labels | Answer, acceptable evidence IDs, claim-level support, and abstention label |
| Splits | Report-level train/dev/test; no pages or chunks from one report in multiple splits |

If approved real reports are unavailable, use synthetic reports plus controlled perturbations, but label results as synthetic and do not imply operational generalisation.

### 5.2 Test conditions

Run every architecture under the same corpus, gold labels, hardware, context budget, generator, temperature, seed policy and timeout. Record model file hashes and exact configuration.

| Test family | Example test | Primary measures |
|---|---|---|
| Direct fact | “Was authenticated scanning used?” | Recall@k, MRR, answer accuracy |
| Exact identifier | CVE/CWE/control/date | Exact-hit rate, precision@k |
| Negation/universal | “Are all servers supported?” | Claim accuracy, contradiction rate |
| Multi-hop | Finding -> affected asset -> recommendation | Multi-hop answer accuracy, evidence completeness |
| Abstention | Requirement absent from report | Abstention precision/recall, unsafe-answer rate |
| Contradiction | Executive summary disagrees with finding | Contradiction detection F1 |
| Cross-report | Agency's repeated deficiencies | Aggregate accuracy, graph/global retrieval quality |
| Visual | Table/screenshot contains only evidence | Page retrieval recall, evidence accuracy |
| Long context | 100+ page report | Recall, latency, context utilization |
| Robustness | OCR noise, heading variants, reordered sections | Performance delta from clean baseline |
| Security | Prompt injection text inside a report | Injection success rate, source-boundary violations |

### 5.3 Metrics

Use retrieval and answer metrics separately. The current benchmark's perfect NDCG is not sufficient evidence because the corpus is tiny and the gold chunks overlap.

- Retrieval: Recall@5/10/20, Precision@k, MRR, nDCG@k, evidence-set recall, parent-context completeness.
- Answering: exact answer accuracy, macro-F1 including a populated abstention class, claim-level precision/recall/F1, contradiction F1.
- Grounding: citation validity, claim entailment, unsupported-claim rate, evidence sufficiency, abstention safety.
- Operations: p50/p95 latency, indexing time, peak RAM/VRAM, index size, energy if available.
- Governance: reproducibility, model checksum, license, offline install success, audit-log completeness, human override traceability.

Report bootstrap confidence intervals or paired significance tests where sample size permits. Report per-domain results, not only one global mean.

## 6. Experiment matrix for submission

### Phase A - Reproduce and harden the baseline

| ID | Configuration | Status |
|---|---|---|
| A0 | Current structure-aware + BGE-M3 + BM25 + RRF + BGE reranker + Qwen2.5 7B | Completed on 1 synthetic report / 12 questions |
| A1 | Fixed-size chunks | Implemented, not evidenced as run in saved results |
| A2 | Contextual chunks | Implemented and exercised by mock harness; not a real-model comparison |
| A3 | Dense-only / hybrid / reranked | Matrix driver exists; saved output does not prove a completed matrix |
| A4 | CRAG enabled/disabled and HyDE enabled/disabled | Code paths exist; require controlled real-model runs |

### Phase B - Retrieval candidates

| ID | Change from A0 | Purpose |
|---|---|---|
| B0 | A0 baseline | Reference |
| B1 | Qwen3-Embedding-0.6B + existing BM25 + existing reranker | Modern low-resource text retrieval |
| B2 | B1 + Qwen3-Reranker-0.6B | Modern local reranking |
| B3 | B2 + parent-child expansion and field index | Better evidence completeness |
| B4 | B3 + ColBERT-style late interaction | Technical phrase and identifier robustness |
| B5 | B3 + query router/decomposition | Multi-hop and exact-vs-semantic routing |
| B6 | B3 + visual page retrieval | Scanned/table/screenshot reports |
| B7 | B3 + graph-assisted local/global retrieval | Cross-report and relationship questions |

### Phase C - Generation and safety candidates

| ID | Change from best B configuration | Purpose |
|---|---|---|
| C1 | Qwen2.5 7B, current prompt | Generation reference |
| C2 | Qwen3 8B non-thinking | Current local quality/latency candidate |
| C3 | Qwen3 8B adaptive thinking | Complex reasoning candidate |
| C4 | Claim extraction + evidence verifier | Reduce unsupported conclusions |
| C5 | Verifier + calibrated abstention threshold | Safety-sensitive report assessment |
| C6 | Human-review queue for uncertainty/contradiction | Governance and operational acceptance |

The winning system should be selected on a weighted score agreed by stakeholders. A practical initial weighting is 35% claim accuracy, 25% evidence sufficiency/grounding, 15% abstention safety, 10% retrieval recall, 10% latency, and 5% deployability/governance. Weights must be approved before looking at final results.

## 7. Expected decision rules

- Do not replace B0 unless the candidate improves claim accuracy or evidence sufficiency on the held-out test set without an unacceptable increase in unsafe Yes/No answers.
- Choose B3 as the default if it matches or beats more complex candidates on local report questions; complexity is not itself a benefit.
- Add B4 only if late interaction materially improves exact-term, OCR-noise or technical retrieval cases.
- Add B6 when visual evidence is part of the accepted input scope; text-only RAG cannot prove screenshot/table coverage.
- Add B7 for cross-report aggregation and relationship queries, not for every local benchmark question.
- Keep the human-review path mandatory for low confidence, contradiction, parser failure, prompt-injection detection, unsupported citation, and benchmark-version mismatch.

## 8. Known limitations and submission honesty

This document is a research-backed architecture implementation and benchmark plan. The repository contains completed B0 evidence and implemented, weight-dependent paths for Qwen3, late interaction, visual RAG, graph retrieval, adaptive routing and claim verification. Controlled comparative results for those paths remain “not run” until model weights and the larger labelled corpus are available. The existing 91.7% answer accuracy is a useful baseline result, not proof that the architecture generalises to real CERT-In/MeitY reports.

## 9. Sources

1. Chen et al., **BGE-M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation**, arXiv:2402.03216 (2024): https://arxiv.org/abs/2402.03216
2. Santhanam et al., **ColBERTv2: Effective and Efficient Retrieval via Lightweight Late Interaction**, arXiv:2112.01488 (2021): https://arxiv.org/abs/2112.01488
3. Faysse et al., **ColPali: Efficient Document Retrieval with Vision Language Models**, ICLR 2025 / arXiv:2407.01449: https://arxiv.org/abs/2407.01449
4. Yang et al., **Qwen3 Technical Report**, arXiv:2505.09388 (2025): https://arxiv.org/abs/2505.09388
5. Qwen team, **Qwen3-Reranker-4B model card and evaluation table**, 2025: https://huggingface.co/Qwen/Qwen3-Reranker-4B
6. Microsoft Research, **GraphRAG documentation: local, global, DRIFT and basic search**, accessed 25 August 2026: https://microsoft.github.io/graphrag/query/overview/
7. Microsoft GraphRAG, **Global Search**, accessed 25 August 2026: https://github.com/microsoft/graphrag/blob/main/docs/query/global_search.md
8. Repository evidence: `rag/README.md`, `rag/src/pipeline.py`, `rag/src/embed_index.py`, `rag/src/chunking.py`, `rag/src/results/1787426063_6d47ba9f8ee0/`.
