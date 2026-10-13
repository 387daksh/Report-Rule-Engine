# AI-Based Cybersecurity Audit Assessment — SOTA RAG Pipeline & Evaluation Harness

State-of-the-Art (2025–2026) Deliverable for Cybersecurity Audit Assessment:
- **Multimodal Document Understanding:** IBM Docling integration (native/scanned PDFs, TableFormer structured tables, layout hierarchy)
- **Precision Hybrid Retrieval:** Dense Vector Embeddings (BGE-M3) + Lexical Sparse Search (BM25Okapi) merged via Reciprocal Rank Fusion (RRF, $k=60$)
- **High-Precision Reranking:** Cross-Encoder (`BAAI/bge-reranker-v2-m3`) second-stage filtering
- **Contextual Chunk Enrichment:** Document and section hierarchy preservation (Anthropic Contextual Retrieval pattern)
- **Corrective RAG (CRAG) & HyDE:** Automated retrieval quality verification with hypothetical document query expansion
- **Deterministic Schema-Enforced Generation:** Ollama `/api/chat` with native token-level JSON Schema constraints
- **Hallucination & Faithfulness Evaluation:** NDCG@K, evidence grounding citation validation, and CRAG quality metrics

Runs **fully offline** on local devices once weights are pulled (Sec. 6.5).

---

## 1. Setup

```bash
# Python dependencies (includes sentence-transformers, faiss-cpu, rank-bm25, docling)
pip install -r requirements.txt

# Local Ollama LLM Server — https://ollama.com
ollama pull qwen3:8b        # Recommended default
ollama pull qwen3:14b       # SOTA high-accuracy candidate
ollama pull llama3.1:8b     # Comparison candidate
ollama pull mistral:7b      # Comparison candidate
ollama serve                # Leave running in a separate terminal
```

---

## 2. Run the SOTA Pipeline on Audit Reports

```bash
cd src
python evaluation_harness.py --config ../configs/eval_config.json --out_dir ../results
```

This ingests audit reports (PDF or TXT), builds the hybrid dense+BM25 index, executes benchmark questions through CRAG-verified retrieval and schema-enforced LLM reasoning, and writes to `results/<run_id>/`:

It also accepts the supplied recursive PDF-extractor JSON format. JSON ingestion preserves field paths and nested findings/tables as searchable evidence while intentionally ignoring image/figure context. Set an audit report path to the `.json` file in the config; no image model is required.

| File | Contents |
|---|---|
| `question_level_results.json` / `.csv` | Every (report, question): retrieved chunks + scores, CRAG verdict, raw output, parsed verdict, config used |
| `retrieval_metrics.json` | Precision@K, Recall@K, Hit Rate@K, MRR, **NDCG@K** |
| `question_level_llm_metrics.json` | Accuracy, Macro-F1, per-class Precision/Recall/F1, confusion matrix |
| `sota_faithfulness_metrics.json` | Evidence Grounding Rate, CRAG Correct Retrieval Rate, Reformulation Rate |
| `audit_level_scores.json` | Positive count, benchmark score, % satisfied, PASS/FAIL decision per report |
| `run_config.json` | The exact config + chunk count for this run (reproducibility) |
| `index/` | Saved FAISS index + BM25 index + chunk metadata |

---

## 3. Run Controlled SOTA Ablation Matrices

```bash
# Compare Retrieval Architectures (Dense-only vs Hybrid BM25 vs Cross-Encoder Reranked)
python run_comparison_matrix.py --matrix retrieval \
    --base_config ../configs/eval_config.json \
    --values dense hybrid reranked

# Compare Chunking Strategies (Structure-aware vs Contextual vs Docling Hybrid)
python run_comparison_matrix.py --matrix chunking \
    --base_config ../configs/eval_config.json \
    --values structure_aware contextual docling_hybrid

# Compare Corrective RAG (CRAG Gating Enabled vs Disabled)
python run_comparison_matrix.py --matrix crag \
    --base_config ../configs/eval_config.json \
    --values enabled disabled

# Compare Candidate LLMs
python run_comparison_matrix.py --matrix llm \
    --base_config ../configs/eval_config.json \
    --values qwen3:8b qwen3:14b llama3.1:8b mistral:7b
```

Each matrix produces `results/comparison_summary.csv` containing Accuracy, Macro-F1, Recall@K, MRR, NDCG@K, Evidence Grounding Rate, and Mean Latency.

---

## 4. Module Map

```
src/
  docling_parser.py         IBM Docling multimodal parser (PDF, tables, images, DOCX)
  chunking.py               StructureAwareChunker, ContextualChunker, DoclingHybridChunker, SemanticChunker
  embed_index.py            BGE-M3 Embedder, BM25Index, HybridRetrievalIndex (RRF), CrossEncoderReranker
  crag_gate.py              Corrective RAG (CRAG) evaluation gate + HyDE query generator
  llm_client.py             Ollama client with native token-level JSON Schema enforcement
  prompts.py                v1_direct and v2_evidence_review prompt templates
  icl.py                    ZeroShot / FixedFewShot / RetrievalFewShot demonstration selector
  pipeline.py               SOTA orchestrator (HyDE -> Hybrid Retrieval -> Rerank -> CRAG -> Chat -> Grounding)
  evaluation_harness.py     Benchmark execution, NDCG@K, Faithfulness, and classification metrics
  run_comparison_matrix.py  Driver for multi-axis ablation comparisons
  test_harness_mock.py      Offline smoke test (runs 100% offline with zero model downloads)
configs/eval_config.json    Central configuration file
sample_data/                Sample audit reports, benchmark questions, and ICL example bank
results/                    Artifacts and metrics written per run
```

---

## 5. Offline Sanity Verification (Smoke Test)

```bash
cd src
python test_harness_mock.py
```

Runs the entire SOTA pipeline end-to-end with mock embeddings, hybrid retrieval, mock reranking, CRAG quality evaluation, and metric calculations in under 2 seconds.

## 6. Modern profile (weights staged separately)

`configs/modern_profile.json` enables the implemented modern path: Qwen3-Embedding, Qwen3-Reranker, adaptive exact/local/aggregate routing, parent-child context expansion, graph-assisted retrieval, and local claim verification. It intentionally does not download anything.

Run it after staging the model directories and pulling the local Ollama generator inside the approved offline process:

```bash
cd src
python evaluation_harness.py --config ../configs/modern_profile.json --out_dir ../results
```

For late interaction, set `use_late_interaction` to `true` and point `late_interaction_model_path` to a local ColBERT-compatible Transformers directory. For visual retrieval, stage a ColQwen2/ColPali model and run:

```bash
python visual_rag.py --model ../models/vidore/colqwen2-v1.0 --images pages/page-1.png pages/page-2.png --query "authenticated vulnerability scan evidence"
```

Required weight families are deliberately external to this repository: Qwen3-Embedding-0.6B, Qwen3-Reranker-0.6B, Qwen3:8b for Ollama, a ColBERT-compatible encoder if late interaction is enabled, and ColQwen2/ColPali plus `colpali-engine` for page images. Verify licenses, hashes and model security before import into the air-gapped environment.
