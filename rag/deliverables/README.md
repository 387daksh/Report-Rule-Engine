# Objective 3 submission package

The submission deliverables are 12 black-and-white, three-page final-review PDF reports in [`pdf/`](pdf/). Each report is organised around its own required purpose: review (D1), model decision (D2), ICL design (D3), ingestion/chunking (D4), retrieval evaluation (D5), prompt design (D6), prototype (D7), methodology (D8), reproducibility (D9), error analysis (D10), POC (D11), and final submission/demo (D12). Each now contains a deliverable-specific review exhibit: actual comparison, trace, response contract, score record, or error case, rather than generic boilerplate.

The completed controlled-comparison ledger is [`../results/final_validation/VALIDATION_SUMMARY.md`](../results/final_validation/VALIDATION_SUMMARY.md). It is cited as evidence `[E10]` in every PDF.

| Deliverable | Final PDF | Evidence status |
|---|---|---|
| D1 | `pdf/D01_Literature_and_Technology_Review.pdf` | Technology review and application implications |
| D2 | `pdf/D02_LLM_Selection_and_Justification.pdf` | Provisional selection backed by saved runs |
| D3 | `pdf/D03_Zero_Shot_and_ICL_Design.pdf` | Implemented strategies; live ablation clearly pending |
| D4 | `pdf/D04_Preprocessing_Chunking_and_Retrieval.pdf` | Implemented text/JSON retrieval path |
| D5 | `pdf/D05_Retrieval_Evaluation_and_Cases.pdf` | Saved per-query retrieval evidence |
| D6 | `pdf/D06_Prompt_Design_and_Justification.pdf` | Evidence-first prompt contract |
| D7 | `pdf/D07_Integrated_RAG_Chatbot_Prototype.pdf` | Functional local proof of concept |
| D8 | `pdf/D08_Evaluation_Dataset_and_Methodology.pdf` | Source-derived dataset and constraints |
| D9 | `pdf/D09_Automated_Evaluation_Harness.pdf` | Reproducible outputs and release gate |
| D10 | `pdf/D10_Results_and_Error_Analysis.pdf` | Quantitative results and failure modes |
| D11 | `pdf/D11_Integrated_Proof_of_Concept.pdf` | Two-report end-to-end demonstration |
| D12 | `pdf/D12_Final_Technical_Report_and_Demo.pdf` | Consolidated conclusion and demo plan |

`build_deliverable_pdfs.py` is the reproducible generator. `pdf_source_docx/` holds editable source documents; the older short Markdown files are retained only as earlier working notes and are not the submission artifacts.

## Run the proof

```text
cd rag/src
python -m unittest test_adaptive_rag.py
python test_harness_mock.py
```

The first command is the modern adaptive-RAG safety check. The second is the full offline mock path. Real-model runs require locally installed weights and Ollama; they must not be run with project data outside the approved air-gapped environment.

The full architecture comparison and benchmark design is in [`../RAG_ARCHITECTURE_RESEARCH_AND_BENCHMARK.md`](../RAG_ARCHITECTURE_RESEARCH_AND_BENCHMARK.md).
