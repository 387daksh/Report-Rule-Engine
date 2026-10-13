# D12 - Final technical report and presentation/demo

The final report is `rag/RAG_Architecture_Research_and_Benchmark.md`; the submission DOCX is `rag/RAG_Architecture_Research_and_Benchmark.docx`.

Suggested 5-10 minute demo sequence:

1. State the objective and air-gapped constraint.
2. Show the B0 baseline flow and its observed metrics.
3. Explain why one report/12 questions is insufficient for a SOTA claim.
4. Show the adaptive route and citation-boundary tests.
5. Run the offline mock proof.
6. Present the controlled B1-B7 architecture matrix and expected decision rules.
7. Close with limitations, human review and next experiments.
# D12 - Final report and presentation

The final evidence package should report the baseline and real-report results together. Baseline B0 achieved 91.67% accuracy on the synthetic 12-question set. The valid Qwen3 retrieval comparison tied B0 on that small corpus. The production-parser Qwen3-8B run covered two reports and 16 questions: accuracy 81.25%, macro-F1 0.4296, grounding 100%, Recall@8 87.50%, Precision@8 14.43%, MRR 0.2781, nDCG@8 0.4212, CRAG correct retrieval 25.00%, reformulation 68.75%, and mean latency 13.66 seconds. Per-report accuracy was 75.00% and 87.50%.

The recommended submission conclusion is that the JSON-aware hybrid architecture is operational and auditable on real extracted reports, but retrieval calibration and independently reviewed benchmark labels remain the primary next work. Image context, ColPali/ColQwen, late-interaction weights, Qwen3-14B, and Llama comparison models were not part of the measured real-report run.
