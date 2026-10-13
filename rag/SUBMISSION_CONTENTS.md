# Objective 3 RAG submission contents

This folder is intentionally limited to the final review package and the
artifacts needed to inspect or reproduce its claims.

## Final submission material

- `deliverables/pdf/`: the twelve final PDF reports.
- `deliverables/README.md`: deliverable index and evidence map.
- `Task Intern (1).docx`: original assignment brief.
- `README.md`: project setup and local execution notes.

## Reproducible implementation

- `src/`: parser, retrieval, prompting, ICL, pipeline, evaluation harness and focused tests.
- `configs/`: executable evaluation configurations.
- `sample_data/`: supplied JSON reports, questions and local ICL example bank.
- `requirements.txt`: Python dependency declaration.

## Evidence retained for review

- `results/final_validation/`: complete controlled-comparison runs cited as E10.
- `results/production_real_reports/1787846335_de0ded86a7db/`: two-report Qwen3 run and score trace (E4-E5).
- `results/qwen3_8b_run/1787660483_900adc72559a/`: earlier Qwen3 comparison evidence (E3).
- `results/modern_retrieval_benchmark.json`: retrieval comparison evidence (E2).
- `src/results/1787426063_6d47ba9f8ee0/`: baseline saved run (E1).

## Deliberately excluded

- Downloaded local model weights: reproducibly obtained separately and too large for a review ZIP.
- PDF-generation code and editable report sources: unnecessary because the final PDFs are included.
- Superseded research drafts, partial experiment directories, caches, old short Markdown drafts and duplicate Word drafts.

The submission is an evaluated proof of concept. It is not presented as a
production-validated decision system.
