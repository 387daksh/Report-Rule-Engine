# D5 - Retrieval evaluation and representative cases

Observed B0 run: one synthetic report, 10 chunks, 12 questions, Recall@5=1.00, Precision@5=0.2833, MRR=1.00 and NDCG@5=1.00. The perfect rank metrics are not generalisation evidence because the corpus is small and gold chunks overlap.

The downloaded Qwen3-Embedding-0.6B plus Qwen3-Reranker-0.6B, tested with identical 220/30 chunking and labels, produced the same metrics and therefore tied B0. The saved artifact is `src/results/modern_retrieval_benchmark.json`.

Successful cases include scope inclusion, authenticated scanning, log retention and explicit vulnerability findings. Difficult cases include universal statements, negation, cross-finding context and questions where the answer depends on a phrase split across overlapping chunks. The full benchmark plan adds OCR noise, contradiction, missing evidence, visual evidence, multi-hop and cross-report cases.
