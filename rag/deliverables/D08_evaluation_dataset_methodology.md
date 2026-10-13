# D8 - Evaluation dataset and methodology

The original proof dataset is `sample_data/sample_report_001.txt` with 12 questions. The real-report evaluation adds `sample_data/2-report.json` and `sample_data/4-report.json`, eight source-derived questions per report in `sample_data/real_reports_benchmark_questions.json`, and per-report gold answers/chunk references in `configs/real_reports_qwen3_8b.json`. The two intermediate Markdown transcripts are retained as extraction audit artifacts and are not indexed as duplicate reports.

The real benchmark is intentionally small and factual: it tests findings, severity, status, CWE classification, remediation, timeline, and negative statements directly supported by each JSON report. The final run covered 16 labelled pairs; it is suitable for integration and error analysis, not statistical claims about unseen audit domains. A production gate still requires independent annotation and a larger balanced set with an Insufficient Evidence class.

This is a proof of concept. A credible validation set should contain at least 40 reports across VAPT, network, mobile and web/application domains, multiple agencies, multiple formats, populated abstention examples, contradiction cases and report-level train/dev/test separation. Gold labels must include acceptable evidence spans and claim-level support.
