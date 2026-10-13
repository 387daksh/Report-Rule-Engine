"""
crag_gate.py
------------
Corrective Retrieval-Augmented Generation (CRAG) & Adaptive Querying.
Paper: Yan et al., 'Corrective Retrieval Augmented Generation' (arXiv:2401.15884, 2024).

Adds an intelligent evaluation and corrective routing layer between Retrieval
and LLM Generation to prevent hallucinations from noisy or off-topic retrieved chunks:
  1. Evaluates retrieved evidence quality: 'CORRECT', 'AMBIGUOUS', or 'INCORRECT'
  2. If AMBIGUOUS: executes HyDE (Hypothetical Document Embeddings) query expansion
     and re-retrieves focused context.
  3. If INCORRECT: routes to fallback or signals 'Insufficient Evidence' early.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from chunking import Chunk
from llm_client import CRAG_EVALUATION_SCHEMA, OllamaClient

logger = logging.getLogger("audit_rag.crag_gate")


@dataclass
class CRAGDecision:
    verdict: str                  # "CORRECT" | "AMBIGUOUS" | "INCORRECT"
    reasoning: str
    missing_information: str
    refined_query: Optional[str] = None
    was_reformulated: bool = False


class CRAGGate:
    """Corrective RAG verification gate for audit compliance questions."""

    def __init__(self, llm_client: OllamaClient, enabled: bool = True):
        self.llm = llm_client
        self.enabled = enabled

    def evaluate_retrieval(
        self,
        question: str,
        retrieved_chunks: List[Chunk],
    ) -> CRAGDecision:
        """Evaluates whether the retrieved evidence chunks can answer the question."""
        if not self.enabled or not retrieved_chunks:
            return CRAGDecision(
                verdict="CORRECT" if retrieved_chunks else "INCORRECT",
                reasoning="CRAG gate bypassed or no chunks retrieved.",
                missing_information="",
            )

        evidence_snippets = "\n\n".join(
            f"[Chunk {c.chunk_id} | Section {c.section}]:\n{c.text[:300]}"
            for c in retrieved_chunks[:5]
        )

        prompt = (
            f"You are a retrieval evaluator for cybersecurity audit compliance.\n"
            f"Determine if the retrieved evidence contains sufficient information to determine "
            f"whether the audit report satisfies the benchmark question.\n\n"
            f"Benchmark Question: {question}\n\n"
            f"Retrieved Evidence Snippets:\n{evidence_snippets}\n\n"
            f"Classify into:\n"
            f"- 'CORRECT': Evidence clearly covers the question (whether the answer is Yes or No).\n"
            f"- 'AMBIGUOUS': Evidence is partially related but missing specific parameters (e.g. version, dates, scope).\n"
            f"- 'INCORRECT': Evidence is completely irrelevant to the question."
        )

        try:
            res = self.llm.generate(
                prompt,
                system="You are an objective retrieval quality judge.",
                format_schema=CRAG_EVALUATION_SCHEMA,
            )
            raw = res.get("text", "")
            data = json.loads(raw)
            return CRAGDecision(
                verdict=data.get("verdict", "CORRECT"),
                reasoning=data.get("reasoning", ""),
                missing_information=data.get("missing_information", ""),
            )
        except Exception as e:
            logger.warning("CRAG evaluation parsing failed: %s. Defaulting to CORRECT.", e)
            return CRAGDecision(verdict="CORRECT", reasoning=f"Parse error: {e}", missing_information="")

    def generate_hyde_query(self, question: str, missing_info: str = "") -> str:
        """Hypothetical Document Embeddings (HyDE): generates a hypothetical
        passage that would answer the benchmark question to improve semantic retrieval."""
        prompt = (
            f"Write a short, realistic excerpt (1-2 sentences) from a formal cybersecurity "
            f"audit report that specifically documents:\n"
            f"Topic: {question}\n"
            f"{f'Focusing on: {missing_info}' if missing_info else ''}\n"
            f"Output ONLY the hypothetical audit excerpt with standard audit terminology."
        )
        try:
            res = self.llm.generate(
                prompt,
                system="You are a cybersecurity auditor generating standard audit phrasing.",
                format_schema=None,
            )
            return res.get("text", question).strip()
        except Exception as e:
            logger.warning("HyDE generation failed (%s), using original question.", e)
            return question
