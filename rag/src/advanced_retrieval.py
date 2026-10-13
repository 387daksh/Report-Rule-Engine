"""Optional retrieval extensions for the modern profile.

All heavy model loading is lazy. The repository remains installable without
weights; selecting a model path gives a clear error until that model exists.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from chunking import Chunk


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9][a-z0-9._/-]+", text.lower()))


class ParentChildRetriever:
    """Expands a precise child hit with its same-section parent context."""

    def __init__(self, chunks: Sequence[Chunk], max_siblings: int = 2):
        self.max_siblings = max_siblings
        self.by_section: Dict[Tuple[str, str], List[Chunk]] = defaultdict(list)
        for chunk in chunks:
            self.by_section[(chunk.report_id, chunk.section)].append(chunk)

    def expand(self, hits: List[Tuple[Chunk, float]], top_k: int) -> List[Tuple[Chunk, float]]:
        out: List[Tuple[Chunk, float]] = []
        seen = set()
        for chunk, score in hits:
            for candidate in self.by_section[(chunk.report_id, chunk.section)][: self.max_siblings + 1]:
                if candidate.chunk_id not in seen:
                    out.append((candidate, score if candidate is chunk else score * 0.95))
                    seen.add(candidate.chunk_id)
            if len(out) >= top_k:
                break
        return sorted(out, key=lambda x: x[1], reverse=True)[:top_k]


class GraphEvidenceIndex:
    """Dependency-free entity graph for local cross-finding retrieval."""

    def __init__(self, chunks: Sequence[Chunk]):
        self.chunks = list(chunks)
        self.entity_to_chunks: Dict[str, set[str]] = defaultdict(set)
        self.chunk_by_id = {c.chunk_id: c for c in self.chunks}
        for chunk in self.chunks:
            for entity in self.entities(chunk.text):
                self.entity_to_chunks[entity].add(chunk.chunk_id)

    @staticmethod
    def entities(text: str) -> set[str]:
        patterns = [r"CVE-\d{4}-\d+", r"CWE-\d+", r"\b(?:ISO|NIST)[-/ ]?[A-Z0-9.:-]+", r"\b(?:Finding|Q)\s*\d+\b"]
        return {m.group(0).lower().replace(" ", "") for p in patterns for m in re.finditer(p, text, re.I)}

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Chunk, float]]:
        query_entities = self.entities(query)
        ids = set().union(*(self.entity_to_chunks.get(e, set()) for e in query_entities)) if query_entities else set()
        scored = [(self.chunk_by_id[cid], 1.0 + len(query_entities & self.entities(self.chunk_by_id[cid].text))) for cid in ids]
        return sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]


class LateInteractionIndex:
    """Optional ColBERT-style max-sim index using a local Transformers model."""

    def __init__(self, model_path: str, device: str = "cpu"):
        from transformers import AutoModel, AutoTokenizer
        self.model_path = model_path
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = AutoModel.from_pretrained(model_path, local_files_only=True).to(device).eval()
        self.rows: List[Tuple[Chunk, object]] = []

    def _encode(self, texts: Sequence[str]):
        import torch
        batch = self.tokenizer(list(texts), padding=True, truncation=True, return_tensors="pt").to(self.device)
        with torch.no_grad():
            hidden = self.model(**batch).last_hidden_state
        return hidden / hidden.norm(dim=-1, keepdim=True).clamp_min(1e-8)

    def add(self, chunks: Sequence[Chunk]):
        for start in range(0, len(chunks), 16):
            self.rows.extend(zip(chunks[start:start + 16], self._encode([c.text for c in chunks[start:start + 16]]).cpu()))

    def search(self, query: str, top_k: int = 5) -> List[Tuple[Chunk, float]]:
        q = self._encode([query])[0]
        scored = []
        for chunk, doc in self.rows:
            score = (q @ doc.T).max(dim=1).values.mean().item()
            scored.append((chunk, float(score)))
        return sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]


class VisualPageIndex:
    """Optional page-image retrieval adapter for ColPali/ColQwen-compatible models.

    The adapter intentionally does not assume one vendor API. A local model
    object exposing `process_images` and `process_queries` can be injected.
    """

    def __init__(self, model, processor):
        self.model = model
        self.processor = processor
        self.pages: List[Tuple[str, object]] = []

    def add(self, page_paths: Iterable[str]):
        for path in page_paths:
            image = self.processor.open_image(path) if hasattr(self.processor, "open_image") else path
            self.pages.append((str(path), self.model.process_images([image])[0]))

    def search(self, query: str, top_k: int = 5):
        q = self.model.process_queries([query])[0]
        scored = [(path, float(self.model.score(q, page))) for path, page in self.pages]
        return sorted(scored, key=lambda x: x[1], reverse=True)[:top_k]


class ColQwenPageIndex(VisualPageIndex):
    """Concrete ColQwen2 adapter. Requires locally staged model weights."""

    @classmethod
    def from_local(cls, model_path: str, device: str = "cuda:0"):
        path = require_local_path(model_path)
        from colpali_engine.models import ColQwen2, ColQwen2Processor
        import torch
        model = ColQwen2.from_pretrained(path, torch_dtype=torch.bfloat16, device_map=device).eval()
        processor = ColQwen2Processor.from_pretrained(path)
        return cls(model, processor)

    def add(self, page_paths: Iterable[str]):
        from PIL import Image
        for path in page_paths:
            image = Image.open(path).convert("RGB")
            batch = self.processor.process_images([image]).to(self.model.device)
            with __import__("torch").inference_mode():
                self.pages.append((str(path), self.model(**batch)[0]))

    def search(self, query: str, top_k: int = 5):
        batch = self.processor.process_queries([query]).to(self.model.device)
        with __import__("torch").inference_mode():
            q = self.model(**batch)
        scores = self.processor.score_multi_vector(q, [p for _, p in self.pages])[0]
        return sorted(zip((path for path, _ in self.pages), map(float, scores)), key=lambda x: x[1], reverse=True)[:top_k]


def require_local_path(path: str) -> str:
    resolved = str(Path(path).expanduser())
    if not Path(resolved).exists():
        raise FileNotFoundError(f"Local model weights not found: {resolved}. Download/import them inside the approved air-gapped process first.")
    return resolved
