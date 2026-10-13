# D01 — Problem definition and scope

**Status:** baseline for all later deliverables
**Supersedes:** the D01–D12 set under `rag/deliverables/`, which describes a
different system (see §5).

---

## 1. What the system is

A conversational assistant that answers questions about cybersecurity audit
reports, grounded in the reports themselves and citing the passage behind
every claim.

From the official brief:

> design an intelligent chatbot that leverages the In-Context Learning
> capabilities of LLMs. This chatbot will specifically process audit reports
> and respond to user queries about the contents of these reports […] users
> input a query regarding an audit report, and the chatbot should intelligently
> analyze the report content and provide accurate and insightful responses.

Four requirements follow directly from that wording, and each one is load-bearing:

| Requirement | Source in the brief | Consequence |
|---|---|---|
| Open-ended answers | "respond to user queries", "insightful responses" | The answer is prose. A fixed verdict vocabulary cannot express "what were the high-severity findings?" |
| Multi-turn | "chatbot" | Session state and reference resolution are required, not optional |
| In-Context Learning | named explicitly | ICL is a product capability, with demonstrations that teach the behaviour wanted |
| Report contents | "contents of these reports" | Scope is a report, or a stated set of them. Not general security advice |

## 2. What the system is not

Stated because the previous implementation drifted into each of these.

- **Not a compliance classifier.** It does not emit Yes / No / Insufficient
  Evidence as its primary output. A structured compliance surface exists
  (`/findings`), but it is a separate, narrower endpoint.
- **Not a security oracle.** It answers from what a report says. "Is this
  organisation secure?" is outside what the evidence supports; "what did this
  audit find about MFA?" is inside it.
- **Not a report-quality grader.** Conformance scoring against a required
  heading set is `rule_engine`'s job. This system consumes its own extraction
  validation, which is a different and narrower check (D04).

## 3. Operating constraints

| Constraint | Effect on the design |
|---|---|
| Air-gapped | No hosted embeddings, rerankers or LLMs. All weights staged by hand; the code never downloads. Rules out most published component comparisons |
| GPU server available | Qwen3-Embedding at 4B becomes viable; full-corpus ingest is feasible in days rather than weeks |
| ~3,000 reports × ~300 pages | ≈450M tokens. Retrieval is genuinely required. Flat indexes and whole-corpus rebuilds are not viable |
| Multi-organisation corpus | Reports carry `classification: Confidential` and come from different audited entities. Scope leakage is a disclosure incident, not a quality bug |
| Audit traceability | Every claim dereferences to a span in a source report. Determinism is a product requirement, so reproducibility outranks peak accuracy |

## 4. Corpus characteristics

Measured on the two supplied reports, not assumed.

| Property | `2-report.json` | `4-report.json` |
|---|---|---|
| Findings | 7 | 15 |
| Narrative share of JSON | 31% by character | similar |
| Figure placeholders | 15 | 135 |
| Image assets staged | 0 | 0 |
| Passes extraction validation | No (column misalignment) | No (header row as data, phase names as findings) |

Two consequences drive the architecture:

1. **69% of the content is structured fields.** Severity, status, CWE, CVE,
   affected assets and finding ids are already recovered by the extractor.
   Querying them is exact; embedding them and asking a model to recover the
   structure statistically is not (D02).
2. **Extraction is unreliable and fails silently.** Both supplied reports are
   defective in ways no count-based check detects. At 3,000 reports nobody
   reviews this by eye, so validation is a pipeline stage, not a one-off
   exercise (D04).

## 5. Relationship to the previous implementation

The code under `rag/src/` was a compliance-classification pipeline with a
batch evaluation harness. It is retained for reference. The new system under
`rag/ragaudit/` replaces it.

Carried forward, because it was sound:

- deterministic chunk ids keyed to content
- source SHA-256 recorded per report
- fail-closed behaviour on unsupported claims
- prompt-injection flagging of report text
- a release gate a proof-of-concept corpus cannot pass
- the ablation discipline in `results/final_validation/VALIDATION_SUMMARY.md`

Replaced, with reasons recorded in the deliverable named:

| Previous behaviour | Why replaced | Where |
|---|---|---|
| Yes/No/Insufficient answer schema | Cannot express the product the brief describes | D06 |
| Flattening structured JSON into text before embedding | Discards recovered structure, then pays a model to guess it back | D02 |
| Silent fallbacks in embedder, reranker, CRAG gate, chunker | A broken run was indistinguishable from a healthy one | D03 |
| `return filtered or hits` on an empty report filter | Cross-organisation evidence leak at corpus scale | D05 |
| Single `min_retrieval_score` across four score scales | The threshold could be meaningful for at most one of them | D05 |
| Few-shot demos emitting `"evidence_chunk_ids": []` | Taught the model the exact behaviour being penalised | D06 |
| `str.find`-recovered character offsets | Mislocates on any repeated phrase; breaks the citation guarantee | D04 |
| Figure tokens stripped "by policy" | Figures are in scope for a chatbot about report contents | D07 |
| Whole-corpus rebuild per run, index written per run | Unworkable at 3,000 reports | D03 |
| Accuracy to 2 d.p. on n=16 | Most reported gaps are inside the noise floor | D09 |

## 6. Open question

**What is the real question mix?** All eight questions in
`real_reports_benchmark_questions.json` are field predicates; the twelve in
`benchmark_questions.json` are control-compliance questions written against a
synthetic text report. Neither set reflects what users will actually ask.

Until a representative question set exists, the structured/narrative split in
D02 is based on the evidence available, and the router reports its reasoning
on every answer so misroutes are visible rather than silent.
