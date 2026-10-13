"""
embed_index.py
---------------
SOTA Embedding generation, BM25 sparse indexing, Hybrid Retrieval (RRF),
and Cross-Encoder Reranking for cybersecurity audit reports.

Supported Models:
  - Dense Embedding: BAAI/bge-m3 (default SOTA) or BAAI/bge-large-en-v1.5
  - Sparse Indexing: BM25Okapi (lexical matching for CVEs, ISO controls, IDs)
  - Reranker: BAAI/bge-reranker-v2-m3 or cross-encoder/ms-marco-MiniLM-L-6-v2

Architecture:
  1. Dense Retrieval (FAISS flat inner-product on normalized vectors)
  2. Sparse Retrieval (BM25 token-level exact matching)
  3. Reciprocal Rank Fusion (RRF, default k=60) combining Dense + Sparse into Top-N
  4. Cross-Encoder Reranking refining Top-N candidates to the final Top-K
"""

from __future__ import annotations

import json
import logging
import pickle
import re
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

from chunking import Chunk

logger = logging.getLogger("audit_rag.embed_index")

DEFAULT_EMBED_MODEL = "BAAI/bge-m3"
FALLBACK_EMBED_MODEL = "BAAI/bge-large-en-v1.5"
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


def _tokenize_for_bm25(text: str) -> List[str]:
    """Tokenize text for BM25 indexing. Preserves technical tokens like
    'A.9.2.1', 'CVE-2024-1234', 'ISO-27001', etc."""
    cleaned = re.sub(r"[^\w\.\-\/]", " ", text.lower())
    return [token for token in cleaned.split() if len(token) > 1]


class Embedder:
    """Wrapper for sentence-transformers embedding models with auto-detection
    for query instruction prefixes and support for BGE-M3."""

    def __init__(self, model_name: str = DEFAULT_EMBED_MODEL, device: str = "cpu", query_instruction: str = ""):
        from sentence_transformers import SentenceTransformer
        self.model_name = model_name
        self.device = device
        self.query_instruction = query_instruction or "Given a cybersecurity audit benchmark question, retrieve the audit evidence that answers it"
        self._is_qwen = "qwen3-embedding" in model_name.lower()
        if self._is_qwen:
            from transformers import AutoModel, AutoTokenizer
            import torch
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, local_files_only=True)
            self.model = AutoModel.from_pretrained(model_name, local_files_only=True, torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32).to(device).eval()
            return
        try:
            self.model = SentenceTransformer(model_name, device=device)
        except Exception as e:
            logger.warning(
                "Could not load '%s' (%s). Falling back to '%s'...",
                model_name, e, FALLBACK_EMBED_MODEL,
            )
            self.model_name = FALLBACK_EMBED_MODEL
            self.model = SentenceTransformer(FALLBACK_EMBED_MODEL, device=device)

        self._needs_prefix = "bge-large" in self.model_name.lower() or "bge-base" in self.model_name.lower()

    def embed_passages(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros((0, 1024), dtype="float32")
        if self._is_qwen:
            return self._encode_qwen(texts)
        vecs = self.model.encode(
            texts, normalize_embeddings=True, batch_size=32, show_progress_bar=False,
        )
        return np.asarray(vecs, dtype="float32")

    def embed_queries(self, queries: List[str]) -> np.ndarray:
        if not queries:
            return np.zeros((0, 1024), dtype="float32")
        if self._is_qwen:
            queries = [f"Instruct: {self.query_instruction}\nQuery: {q}" for q in queries]
            return self._encode_qwen(queries)
        if self._needs_prefix:
            queries = [BGE_QUERY_PREFIX + q for q in queries]
        elif self._is_qwen:
            queries = [f"Instruct: {self.query_instruction}\nQuery: {q}" for q in queries]
        vecs = self.model.encode(
            queries, normalize_embeddings=True, batch_size=32, show_progress_bar=False,
        )
        return np.asarray(vecs, dtype="float32")

    def _encode_qwen(self, texts: List[str]) -> np.ndarray:
        import torch
        outputs = []
        # 420-token audit chunks do not need the model's full context window.
        # ponytail: small batches avoid 6 GB laptop VRAM exhaustion; raise only with larger GPUs.
        for start in range(0, len(texts), 2):
            batch = self.tokenizer(texts[start:start + 2], padding=True, truncation=True, max_length=2048, return_tensors="pt").to(self.device)
            with torch.inference_mode():
                hidden = self.model(**batch).last_hidden_state
            positions = batch["attention_mask"].sum(dim=1) - 1
            pooled = hidden[torch.arange(hidden.size(0), device=hidden.device), positions]
            outputs.append(torch.nn.functional.normalize(pooled, p=2, dim=1).cpu().numpy())
        return np.concatenate(outputs, axis=0).astype("float32")

    def __call__(self, texts: List[str]) -> np.ndarray:
        return self.embed_passages(texts)


class BM25Index:
    """Lexical sparse search index using BM25Okapi to guarantee exact keyword
    retrieval for cybersecurity audit identifiers, CVE codes, and control numbers."""

    def __init__(self, chunks: Optional[List[Chunk]] = None):
        self.chunks: List[Chunk] = chunks or []
        self.corpus_tokens: List[List[str]] = [_tokenize_for_bm25(c.text) for c in self.chunks]
        self._build_bm25()

    def _build_bm25(self):
        if self.corpus_tokens:
            from rank_bm25 import BM25Okapi
            self.bm25 = BM25Okapi(self.corpus_tokens)
        else:
            self.bm25 = None

    def search(self, query: str, top_k: int = 50) -> List[Tuple[Chunk, float]]:
        if not self.bm25 or not self.chunks:
            return []
        q_tokens = _tokenize_for_bm25(query)
        if not q_tokens:
            return []
        scores = self.bm25.get_scores(q_tokens)
        top_indices = np.argsort(scores)[::-1][:top_k]
        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score > 0.0:
                results.append((self.chunks[idx], score))
        return results


class CrossEncoderReranker:
    """Second-pass cross-encoder reranker for high-precision query-passage scoring."""

    def __init__(self, model_name: str = DEFAULT_RERANKER_MODEL, device: str = "cpu"):
        self.model_name = model_name
        self.device = device
        self.model = None
        self._load_model()

    def _load_model(self):
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(self.model_name, device=self.device)
            logger.info("Loaded CrossEncoder reranker: %s", self.model_name)
        except Exception as e:
            logger.warning("Could not load CrossEncoder '%s': %s. Reranking will pass-through.", self.model_name, e)
            self.model = None

    def rerank(self, query: str, chunks: List[Chunk], top_k: int = 5) -> List[Tuple[Chunk, float]]:
        if not chunks:
            return []
        if self.model is None:
            # Fallback pass-through
            return [(c, 1.0 / (i + 1)) for i, c in enumerate(chunks[:top_k])]

        pairs = [(query, c.text) for c in chunks]
        scores = self.model.predict(pairs, batch_size=32, show_progress_bar=False)
        ranked = sorted(zip(chunks, [float(s) for s in scores]), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


class RetrievalIndex:
    """FAISS flat cosine-similarity index over dense embeddings."""

    def __init__(self, dim: int):
        import faiss
        self.index = faiss.IndexFlatIP(dim)
        self.chunks: List[Chunk] = []

    def add(self, chunks: List[Chunk], embeddings: np.ndarray):
        assert len(chunks) == embeddings.shape[0]
        self.index.add(embeddings)
        self.chunks.extend(chunks)

    def search(self, query_emb: np.ndarray, top_k: int = 5) -> List[Tuple[Chunk, float]]:
        scores, idxs = self.index.search(query_emb.reshape(1, -1), top_k)
        results = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx == -1:
                continue
            results.append((self.chunks[idx], float(score)))
        return results

    def save(self, out_dir: str):
        import faiss
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(out / "index.faiss"))
        with open(out / "chunks.pkl", "wb") as f:
            pickle.dump(self.chunks, f)
        meta = [asdict(c) for c in self.chunks]
        with open(out / "chunks_metadata.json", "w") as f:
            json.dump(meta, f, indent=2)

    @classmethod
    def load(cls, in_dir: str) -> "RetrievalIndex":
        import faiss
        in_path = Path(in_dir)
        index = faiss.read_index(str(in_path / "index.faiss"))
        obj = cls.__new__(cls)
        obj.index = index
        with open(in_path / "chunks.pkl", "rb") as f:
            obj.chunks = pickle.load(f)
        return obj


class HybridRetrievalIndex:
    """Production SOTA Hybrid Index combining Dense FAISS + Sparse BM25 with
    Reciprocal Rank Fusion (RRF) and optional Cross-Encoder Reranking."""

    def __init__(self, dense_index: RetrievalIndex, bm25_index: BM25Index, reranker: Optional[CrossEncoderReranker] = None):
        self.dense_index = dense_index
        self.bm25_index = bm25_index
        self.reranker = reranker
        self.chunks = dense_index.chunks

    def search(
        self,
        query_emb: np.ndarray,
        query_text: str,
        top_k: int = 5,
        candidates_k: int = 40,
        rrf_k: int = 60,
        use_reranker: bool = True,
    ) -> List[Tuple[Chunk, float]]:
        """Executes Hybrid Search:
        1. Dense Top-N retrieval
        2. Sparse Top-N BM25 retrieval
        3. Reciprocal Rank Fusion (RRF)
        4. Optional Cross-Encoder reranking
        """
        dense_hits = self.dense_index.search(query_emb, top_k=candidates_k)
        sparse_hits = self.bm25_index.search(query_text, top_k=candidates_k)

        # Reciprocal Rank Fusion (RRF)
        chunk_map = {c.chunk_id: c for c in self.chunks}
        rrf_scores: dict[str, float] = {}

        for rank, (chunk, _) in enumerate(dense_hits):
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + (1.0 / (rrf_k + rank + 1))

        for rank, (chunk, _) in enumerate(sparse_hits):
            rrf_scores[chunk.chunk_id] = rrf_scores.get(chunk.chunk_id, 0.0) + (1.0 / (rrf_k + rank + 1))

        # Sort by fused score
        fused_sorted = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        candidate_chunks = [chunk_map[cid] for cid, _ in fused_sorted[:candidates_k]]

        if not candidate_chunks:
            # Fallback to dense if sparse was completely empty and dense had no hits
            return []

        # Step 4: Reranking
        if use_reranker and self.reranker:
            return self.reranker.rerank(query_text, candidate_chunks, top_k=top_k)

        # Otherwise return top-k with RRF scores
        return [(chunk_map[cid], score) for cid, score in fused_sorted[:top_k]]

    def save(self, out_dir: str):
        out = Path(out_dir)
        self.dense_index.save(str(out / "dense"))
        with open(out / "bm25_corpus.pkl", "wb") as f:
            pickle.dump(self.bm25_index.corpus_tokens, f)

    @classmethod
    def load(cls, in_dir: str, reranker: Optional[CrossEncoderReranker] = None) -> "HybridRetrievalIndex":
        in_path = Path(in_dir)
        dense_idx = RetrievalIndex.load(str(in_path / "dense"))
        bm25_idx = BM25Index(dense_idx.chunks)
        return cls(dense_idx, bm25_idx, reranker=reranker)


def build_index(chunks: List[Chunk], embedder: Embedder) -> RetrievalIndex:
    texts = [c.text for c in chunks]
    embs = embedder.embed_passages(texts)
    idx = RetrievalIndex(dim=embs.shape[1])
    idx.add(chunks, embs)
    return idx


def build_hybrid_index(
    chunks: List[Chunk],
    embedder: Embedder,
    reranker: Optional[CrossEncoderReranker] = None,
) -> HybridRetrievalIndex:
    dense_idx = build_index(chunks, embedder)
    bm25_idx = BM25Index(chunks)
    return HybridRetrievalIndex(dense_idx, bm25_idx, reranker=reranker)
