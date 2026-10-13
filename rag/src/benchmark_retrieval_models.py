"""Compare real local retrieval models without spending time on generation."""

from __future__ import annotations

import json
from pathlib import Path

from chunking import StructureAwareChunker
from docling_parser import parse_document
from embed_index import CrossEncoderReranker, Embedder, build_hybrid_index
from evaluation_harness import retrieval_metrics_for_query, aggregate_retrieval_metrics


def main():
    root = Path(__file__).resolve().parents[1]
    report_id = "AR-2026-001"
    with open(root / "sample_data/benchmark_questions.json", encoding="utf-8") as f:
        questions = json.load(f)
    with open(root / "configs/eval_config.json", encoding="utf-8") as f:
        gold = json.load(f)["audit_reports"][0]["gold_labels"]
    text = parse_document(str(root / "sample_data/sample_report_001.txt"), report_id=report_id).full_text
    chunks = StructureAwareChunker(max_tokens=220, overlap_tokens=30, min_tokens=40).chunk(report_id, text)
    models = {
        "qwen3": (root / "models/Qwen3-Embedding-0.6B", root / "models/Qwen3-Reranker-0.6B"),
    }
    output = {}
    for name, (embed_path, rerank_path) in models.items():
        embedder = Embedder(str(embed_path), device="cpu")
        reranker = CrossEncoderReranker(str(rerank_path), device="cpu")
        index = build_hybrid_index(chunks, embedder, reranker=reranker)
        rows = []
        for q in questions:
            query = q["text"]
            hits = index.search(embedder.embed_queries([query])[0], query, top_k=5, candidates_k=40, use_reranker=True)
            rows.append(retrieval_metrics_for_query([c.chunk_id for c, _ in hits], gold[q["question_id"]]["gold_chunk_ids"], 5))
        output[name] = {"model": name, "n_chunks": len(chunks), "summary": aggregate_retrieval_metrics(rows)}
    out_path = root / "results/modern_retrieval_benchmark.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
