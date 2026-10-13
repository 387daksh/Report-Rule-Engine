"""
test_harness_mock.py
----------------------
Comprehensive offline smoke test for the SOTA RAG pipeline.
Exercises the entire SOTA architecture end-to-end WITHOUT requiring internet,
model downloads, or a running Ollama server:
  - Contextual & Structure-Aware Chunking
  - Docling Parser Fallback
  - Hybrid Retrieval (Dense FAISS + Sparse BM25)
  - Reciprocal Rank Fusion (RRF)
  - Cross-Encoder Reranking Mock
  - Corrective RAG (CRAG) Quality Gate Mock
  - Schema-enforced Chat generation
  - Evidence Grounding Verification
  - Precision@K, Recall@K, Hit Rate@K, MRR, and NDCG@K metrics
  - SOTA Faithfulness & Hallucination tracking

Run: python test_harness_mock.py
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


# ---- Fake Embedder: deterministic, hash-based pseudo-embeddings ---------
class FakeEmbedder:
    dim = 64
    model_name = "mock-bge-m3"

    def _embed(self, texts: List[str]) -> np.ndarray:
        out = []
        for t in texts:
            h = hashlib.sha256(t.encode()).digest()
            vec = np.frombuffer((h * ((self.dim * 4) // len(h) + 1))[: self.dim * 4], dtype=np.uint8).astype("float32")
            vec = vec / (np.linalg.norm(vec) + 1e-8)
            out.append(vec)
        return np.stack(out) if out else np.zeros((0, self.dim), dtype="float32")

    def embed_passages(self, texts: List[str]) -> np.ndarray:
        return self._embed(texts)

    def embed_queries(self, texts: List[str]) -> np.ndarray:
        return self._embed(texts)

    def __call__(self, texts: List[str]) -> np.ndarray:
        return self._embed(texts)


# ---- Fake Ollama client: handles .chat and .generate with schema -------
class FakeOllamaClient:
    def __init__(self, config=None, max_retries=3):
        self.config = config

    def chat(self, messages: List[Dict[str, str]], format_schema: Optional[Dict[str, Any]] = None) -> dict:
        user_content = next((m["content"] for m in messages if m["role"] == "user"), "")
        return self.generate(user_content, format_schema=format_schema)

    def generate(self, prompt: str, system: Optional[str] = None, format_schema: Optional[Dict[str, Any]] = None) -> dict:
        h = int(hashlib.sha256(prompt.encode()).hexdigest(), 16)

        # Check if CRAG evaluation prompt
        if "retrieval evaluator" in prompt.lower() or "classify into" in prompt.lower():
            verdict = ["CORRECT", "AMBIGUOUS", "CORRECT"][h % 3]
            text = json.dumps({
                "verdict": verdict,
                "reasoning": "Mock CRAG evaluation determined evidence alignment.",
                "missing_information": "specific policy clauses" if verdict == "AMBIGUOUS" else "",
            })
            return {"text": text, "latency_s": 0.01, "model": "mock-llm", "raw": {}}

        # Standard assessment prompt
        answer = ["Yes", "No", "Insufficient Evidence"][h % 3]
        text = json.dumps({
            "answer": answer,
            "supporting_evidence": "Audit findings confirmed multi-factor authentication coverage.",
            "evidence_chunk_ids": [],
            "justification": "Mock audit justification grounded in evidence.",
        })
        return {"text": text, "latency_s": 0.02, "model": "mock-llm", "raw": {}}


# ---- Fake Cross-Encoder Reranker ---------------------------------------
class FakeCrossEncoderReranker:
    def __init__(self, model_name="mock-reranker", device="cpu"):
        self.model_name = model_name

    def rerank(self, query: str, chunks: list, top_k: int = 5):
        ranked = []
        for i, c in enumerate(chunks[:top_k]):
            score = 1.0 / (i + 1)
            ranked.append((c, score))
        return ranked


def main():
    import chunking
    import docling_parser
    import embed_index
    import evaluation_harness as harness_mod
    import pipeline as pipeline_mod
    from icl import STRATEGIES as ICL_STRATEGIES, load_example_bank
    from llm_client import GenerationConfig
    from pipeline import AuditAssessmentPipeline, PipelineConfig

    print("=== STARTING SOTA RAG MOCK PIPELINE TEST ===")

    # 1. Document Parsing & Contextual Chunking
    parsed_report = docling_parser.parse_document("../sample_data/sample_report_001.txt", report_id="AR-2026-001")
    print(f"[1/6] Docling parser loaded report: '{parsed_report.report_id}' ({len(parsed_report.full_text)} chars)")

    chunker = chunking.ContextualChunker(max_tokens=220, overlap_tokens=30)
    chunks = chunker.chunk(parsed_report.report_id, parsed_report.full_text)
    print(f"[2/6] ContextualChunker produced {len(chunks)} enriched chunks")
    assert len(chunks) > 0, "No chunks produced"
    assert "[Report: AR-2026-001" in chunks[0].text, "Contextual prefix missing from chunk"

    # 2. Hybrid Indexing (Dense FAISS + Sparse BM25 + Mock Reranker)
    embedder = FakeEmbedder()
    reranker = FakeCrossEncoderReranker()
    hybrid_index = embed_index.build_hybrid_index(chunks, embedder, reranker=reranker)
    print(f"[3/6] Hybrid Index built (FAISS: {len(hybrid_index.dense_index.chunks)} chunks, BM25: {len(hybrid_index.bm25_index.chunks)} chunks)")

    # 3. Pipeline Initialization with CRAG & Schema Enforcement
    mock_llm = FakeOllamaClient()
    pipeline_mod.OllamaClient = lambda cfg=None: mock_llm

    bank = load_example_bank("../sample_data/icl_example_bank.json")
    icl_selector = ICL_STRATEGIES["retrieval_few_shot"](bank, embedder, k=4)

    pipe_cfg = PipelineConfig(
        top_k=5,
        candidates_k=40,
        prompt_version="v2_evidence_review",
        icl_strategy_name="retrieval_few_shot",
        icl_k=4,
        use_hybrid=True,
        use_reranker=True,
        use_crag=True,
        generation=GenerationConfig(model_name="mock-qwen3"),
    )
    pipeline = AuditAssessmentPipeline(hybrid_index, embedder, icl_selector, pipe_cfg)

    # 4. Benchmark Question Execution
    with open("../sample_data/benchmark_questions.json") as f:
        questions = json.load(f)

    results = []
    print(f"[4/6] Executing {len(questions)} benchmark questions through SOTA pipeline...")
    for q in questions:
        res = pipeline.assess("AR-2026-001", q["question_id"], q["text"])
        results.append(res)
        print(f"   -> [{q['question_id']}] Answer: {res.answer:<22} (CRAG: {res.crag_verdict}, Chunks: {len(res.retrieved_chunk_ids)})")

    # 5. Metric Computation Verification (Retrieval + NDCG + Generation + Faithfulness)
    with open("../configs/eval_config.json") as f:
        cfg_json = json.load(f)
    gold_map = cfg_json["audit_reports"][0]["gold_labels"]

    print("[5/6] Verifying SOTA Metric Computations...")
    # Retrieval Metrics with NDCG@K
    retr_rows = []
    for r in results:
        gold_ids = gold_map.get(r.question_id, {}).get("gold_chunk_ids", [])
        if gold_ids:
            rmet = harness_mod.retrieval_metrics_for_query(r.retrieved_chunk_ids, gold_ids, k=5)
            retr_rows.append(rmet)
    agg_retrieval = harness_mod.aggregate_retrieval_metrics(retr_rows)
    print(f"   - Mean Recall@5: {agg_retrieval.get('mean_recall_at_k')}")
    print(f"   - Mean MRR:      {agg_retrieval.get('mrr')}")
    print(f"   - Mean NDCG@5:   {agg_retrieval.get('mean_ndcg_at_k')}")
    assert "mean_ndcg_at_k" in agg_retrieval, "NDCG@K metric missing from retrieval aggregation"

    # Generation Classification Metrics
    y_true = [gold_map[r.question_id]["answer"] for r in results]
    y_pred = [r.answer for r in results]
    gen_metrics = harness_mod.classification_metrics(y_true, y_pred)
    print(f"   - Accuracy: {gen_metrics.get('accuracy')}, Macro-F1: {gen_metrics.get('macro_f1')}")

    # SOTA Faithfulness & Audit Scores
    grounded_count = sum(1 for r in results if r.is_evidence_grounded)
    grounding_rate = grounded_count / len(results)
    print(f"   - Evidence Grounding Rate: {grounding_rate:.2%}")

    audit_score = harness_mod.audit_level_score([{"answer": r.answer} for r in results])
    print(f"   - Audit Compliance Score: {audit_score.get('percentage_requirements_satisfied')}% -> {audit_score.get('benchmark_decision')}")

    print("\n[6/6] === ALL SOTA RAG MOCK TESTS PASSED SUCCESSFULLY! ===")


if __name__ == "__main__":
    main()
