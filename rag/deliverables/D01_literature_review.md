# D1 - Brief literature and technology review

The current system is a valid hybrid-RAG baseline: structure-aware chunking, BGE-M3 dense retrieval, BM25, reciprocal-rank fusion, cross-encoder reranking, CRAG/HyDE, ICL, and schema-constrained local generation.

The researched candidates are: modern Qwen3 text embedding/reranking, ColBERT-style late interaction, page-level visual retrieval such as ColPali, graph-assisted local/global retrieval, and adaptive query routing. The recommended design is modular: structured hybrid retrieval as the default, visual retrieval only when the source needs it, and graph retrieval for cross-report aggregation.

Primary sources are listed in the parent research report: BGE-M3 (2024), ColBERTv2, ColPali (ICLR 2025), Qwen3 (2025), Qwen3-Reranker, and Microsoft GraphRAG documentation.
