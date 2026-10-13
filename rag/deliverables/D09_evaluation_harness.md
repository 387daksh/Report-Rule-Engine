# D9 - Automated evaluation harness

Final production-parser run: 16 report-question pairs across two JSON reports. It produced question-level JSON/CSV, retrieval and classification metrics, grounding and CRAG metrics, human-review output, audit scores, provenance/configuration metadata, and the reproducible artifact `results/production_real_reports/1787846335_de0ded86a7db/`. The measured results were 81.25% accuracy, 0.4296 macro-F1, 87.50% Recall@8, 100% grounding, and 13.66 seconds mean latency.

The harness now also writes `production_readiness_gate.json`. It fails closed unless the configured minimum report count, independently labelled question count, balanced answer classes (including Insufficient Evidence), retrieval recall, grounding, and macro-F1 thresholds are all met. The current two-report dataset is therefore correctly marked `BLOCKED`; this is a data-evidence limitation, not a pipeline crash.

The completed real-report run evaluated 16 report-question pairs across two JSON reports. It produced question-level JSON/CSV outputs, retrieval Precision/Recall/Hit Rate/MRR/nDCG, classification accuracy and macro-F1, grounding and CRAG metrics, human-review queue, audit-level scores, and the exact run configuration. The reproducible artifact is `results/real_reports_qwen3_8b_clean/1787845127_277397767a88/`.

Entry point: `src/evaluation_harness.py`.

It records question-level retrieval and generation results, configuration, raw model output, evidence IDs, CRAG state, grounding, latency, gold labels and review flags. It produces JSON/CSV results, retrieval metrics, classification metrics, faithfulness metrics, audit-level score and run configuration. `src/run_comparison_matrix.py` supports controlled LLM, ICL, chunking, retrieval and CRAG axes.

Reproducibility requires the same source hashes, model files, prompt version, parameters, seed and hardware profile.
