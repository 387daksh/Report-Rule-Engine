"""Shared fixtures.

The fakes here are deterministic and dependency-free so the suite runs with no
staged model weights and no LLM server. They are *test doubles only*: the
production code paths fail loudly when a real model cannot load, which is the
behaviour tested in ``test_failure_modes.py``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from ragaudit.generate.llm import Completion
from ragaudit.ingest.chunking import FieldAwareChunker
from ragaudit.ingest.pipeline import IngestPipeline
from ragaudit.retrieve.hybrid import HybridRetriever, RetrievalConfig
from ragaudit.store.catalog import Catalog
from ragaudit.store.vectors import NumpyVectorIndex

SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_data"


class FakeEmbedder:
    """Hash-based deterministic embeddings.

    Carries no semantics, so tests that depend on it assert on plumbing
    (dimensions, filtering, persistence), never on retrieval quality.
    """

    dimension = 64
    fingerprint = "fake:64"

    def _encode(self, texts):
        out = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            repeated = (digest * (self.dimension // len(digest) + 1))[: self.dimension]
            vector = np.frombuffer(repeated, dtype=np.uint8).astype("float32")
            vector = vector / (np.linalg.norm(vector) + 1e-9)
            out.append(vector)
        return np.stack(out).astype("float32") if out else np.zeros((0, self.dimension), "float32")

    def embed_passages(self, texts):
        return self._encode(list(texts))

    def embed_queries(self, texts):
        return self._encode(list(texts))


class FakeLLM:
    """Scriptable LLM double.

    ``script`` maps a substring of the prompt to the JSON body to return, so a
    test can drive a specific model behaviour (a fabricated citation, a
    malformed body) without a server.
    """

    model_name = "fake-model"

    def __init__(self, script: dict[str, str] | None = None, default: str | None = None):
        self.script = script or {}
        self.default = default
        self.calls: list[str] = []

    def _respond(self, prompt: str) -> str:
        self.calls.append(prompt)
        for needle, response in self.script.items():
            if needle in prompt:
                return response
        if self.default is not None:
            return self.default
        return json.dumps(
            {
                "evidence_review": "Reviewed the supplied passages.",
                "answer": "The evidence does not settle this question.",
                "citations": [],
                "answered": False,
                "missing_information": "nothing relevant retrieved",
            }
        )

    def chat(self, messages, format_schema=None, max_tokens=None):
        prompt = "\n".join(m["content"] for m in messages)
        return Completion(text=self._respond(prompt), latency_s=0.01, model=self.model_name)

    def generate(self, prompt, system=None, format_schema=None, max_tokens=None):
        return Completion(text=self._respond(prompt), latency_s=0.01, model=self.model_name)


@pytest.fixture
def sample_report_path() -> Path:
    path = SAMPLE_DIR / "2-report.json"
    if not path.exists():
        pytest.skip("sample corpus not present")
    return path


@pytest.fixture
def sample_data(sample_report_path: Path) -> dict:
    return json.loads(sample_report_path.read_text(encoding="utf-8"))


@pytest.fixture
def catalog(tmp_path: Path) -> Catalog:
    cat = Catalog(tmp_path / "catalog.sqlite3")
    yield cat
    cat.close()


@pytest.fixture
def embedder() -> FakeEmbedder:
    return FakeEmbedder()


@pytest.fixture
def index(embedder: FakeEmbedder) -> NumpyVectorIndex:
    return NumpyVectorIndex(dimension=embedder.dimension)


@pytest.fixture
def pipeline(catalog: Catalog, index: NumpyVectorIndex, embedder: FakeEmbedder) -> IngestPipeline:
    return IngestPipeline(
        catalog,
        index,
        embedder,
        chunker=FieldAwareChunker(max_tokens=420, overlap_tokens=60),
        fail_on_validation_error=False,  # sample corpus has known defects
    )


@pytest.fixture
def retriever(catalog, index, embedder) -> HybridRetriever:
    return HybridRetriever(
        catalog, index, embedder, reranker=None, config=RetrievalConfig(top_k=5, candidates_k=20)
    )
