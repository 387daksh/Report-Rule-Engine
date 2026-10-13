# D4 - Preprocessing, chunking and retrieval index

The production input can be the recursive JSON emitted by the PDF extractor. The implemented loader flattens nested objects and lists into provenance-labelled rows, deduplicates repeated leaf rows, retains metadata, and ignores image/figure context because image reasoning is out of scope for this submission.

The prototype supports text fallback parsing, Docling integration points, deterministic source offsets, stable chunk IDs, fixed-size, structure-aware, semantic, contextual and Docling-hybrid strategy names. Retrieval supports FAISS inner-product dense search, BM25, RRF, candidate retrieval and cross-encoder reranking.

The modern path adds `src/adaptive_rag.py`: exact questions remain identifier-focused, local questions use direct semantic retrieval, and aggregate questions receive a second evidence-oriented query. Unknown citation IDs are rejected before an answer is considered grounded.

The modern optional implementation includes parent-child expansion, graph-assisted retrieval, generic ColBERT-style late interaction, and a concrete ColQwen2/ColPali page-index CLI. Visual page retrieval is deliberately separate because page rendering and model weights are deployment inputs; the text harness remains runnable without them.
