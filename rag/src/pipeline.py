"""
pipeline.py
-----------
SOTA Integrated RAG Audit Assessment Pipeline.

Features:
  1. Pre-Retrieval: HyDE (Hypothetical Document Embeddings) query expansion
  2. Hybrid Retrieval: Dense Vector Search (FAISS) + Sparse BM25 via Reciprocal Rank Fusion (RRF)
  3. Re-ranking: Cross-Encoder (BGE-Reranker-v2-m3)
  4. Retrieval Quality Gate: CRAG (Corrective RAG) verification & adaptive reformulation
  5. Deterministic Generation: Token-level JSON Schema enforcement
  6. Grounding & Faithfulness Verification: Evidence quote citation checking
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

from chunking import Chunk
from crag_gate import CRAGDecision, CRAGGate
from embed_index import Embedder, HybridRetrievalIndex, RetrievalIndex
from icl import Demonstration
from llm_client import AUDIT_ASSESSMENT_SCHEMA, GenerationConfig, LocalTransformersClient, OllamaClient
from prompts import PROMPT_BUILDERS, SYSTEM_PROMPT
from adaptive_rag import contains_prompt_injection, evidence_supports, route_query, valid_citations
from advanced_retrieval import GraphEvidenceIndex, LateInteractionIndex, ParentChildRetriever
from claim_verifier import ClaimVerifier
from pii_redaction import redact_if_enabled

logger = logging.getLogger("audit_rag.pipeline")


@dataclass
class PipelineConfig:
    top_k: int = 5
    candidates_k: int = 40
    prompt_version: str = "v2_evidence_review"
    icl_strategy_name: str = "retrieval_few_shot"
    icl_k: int = 4
    use_hybrid: bool = True
    use_reranker: bool = True
    use_crag: bool = True
    use_hyde: bool = False
    generation: GenerationConfig = field(default_factory=GenerationConfig)
    min_retrieval_score: float = 0.40
    require_evidence_for_yes_no: bool = True
    use_parent_child: bool = False
    use_graph_retrieval: bool = False
    graph_index: Optional[GraphEvidenceIndex] = None
    parent_child: Optional[ParentChildRetriever] = None
    late_interaction: Optional[LateInteractionIndex] = None
    use_claim_verifier: bool = False
    fail_closed_on_unsupported: bool = True
    redact_persisted_output: bool = True


@dataclass
class AssessmentResult:
    report_id: str
    question_id: str
    question_text: str
    retrieved_chunk_ids: List[str]
    retrieved_scores: List[float]
    raw_llm_output: str
    answer: str                  # "Yes" | "No" | "Insufficient Evidence" | "ParseError" | "Error"
    supporting_evidence: str
    cited_chunk_ids: List[str]
    justification: str
    latency_s: float
    config: dict
    crag_verdict: str = "CORRECT"
    crag_reformulated: bool = False
    is_evidence_grounded: bool = True
    requires_human_review: bool = False
    review_reasons: List[str] = field(default_factory=list)


class AuditAssessmentPipeline:
    def __init__(
        self,
        index: Union[HybridRetrievalIndex, RetrievalIndex],
        embedder: Embedder,
        icl_selector,
        config: Optional[PipelineConfig] = None,
    ):
        self.index = index
        self.embedder = embedder
        self.icl_selector = icl_selector
        self.config = config or PipelineConfig()
        self.llm = (LocalTransformersClient(self.config.generation)
                    if self.config.generation.backend == "transformers"
                    else OllamaClient(self.config.generation))
        self.crag = CRAGGate(self.llm, enabled=self.config.use_crag)
        self.claim_verifier = ClaimVerifier(self.llm) if self.config.use_claim_verifier else None

    def _retrieve_chunks(self, report_id: str, query_text: str) -> List[Tuple[Chunk, float]]:
        q_emb = self.embedder.embed_queries([query_text])[0]

        if isinstance(self.index, HybridRetrievalIndex) and self.config.use_hybrid:
            hits = self.index.search(
                query_emb=q_emb,
                query_text=query_text,
                top_k=self.config.top_k,
                candidates_k=self.config.candidates_k,
                use_reranker=self.config.use_reranker,
            )
        else:
            # Dense-only fallback
            hits = self.index.search(q_emb, top_k=self.config.top_k)

        # Restrict to target report if index covers multiple reports
        filtered = [(c, s) for c, s in hits if c.report_id == report_id]
        return filtered or hits

    def _parse_response(self, raw_text: str) -> dict:
        # If schema-enforced, raw_text is valid JSON; otherwise extract safely
        cleaned = raw_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned.split("```json", 1)[1].split("```", 1)[0].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            obj = json.loads(cleaned)
        except Exception:
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                try:
                    obj = json.loads(match.group(0))
                except Exception:
                    obj = {}
            else:
                obj = {}

        obj.setdefault("answer", "ParseError")
        obj.setdefault("supporting_evidence", "")
        obj.setdefault("evidence_chunk_ids", [])
        obj.setdefault("justification", "")
        return obj

    def _check_evidence_grounding(self, supporting_evidence: str, retrieved_chunks: List[Chunk]) -> bool:
        return bool(not supporting_evidence.strip() or evidence_supports(
            supporting_evidence, [c.text for c in retrieved_chunks]
        ))

    def assess(self, report_id: str, question_id: str, question_text: str) -> AssessmentResult:
        # Step 1: Pre-retrieval / HyDE transformation
        route = route_query(question_text)
        search_query = route.queries[0]
        if self.config.use_hyde:
            search_query = self.crag.generate_hyde_query(question_text)

        # Step 2: Retrieval
        hits = self._retrieve_chunks(report_id, search_query)
        if self.config.use_graph_retrieval and self.config.graph_index:
            graph_hits = self.config.graph_index.search(question_text, top_k=self.config.candidates_k)
            seen = {c.chunk_id for c, _ in hits}
            hits.extend((c, s) for c, s in graph_hits if c.report_id == report_id and c.chunk_id not in seen)
        if self.config.late_interaction:
            late_hits = self.config.late_interaction.search(question_text, top_k=self.config.candidates_k)
            seen = {c.chunk_id for c, _ in hits}
            hits.extend((c, s) for c, s in late_hits if c.report_id == report_id and c.chunk_id not in seen)
        if self.config.use_parent_child and self.config.parent_child:
            hits = self.config.parent_child.expand(hits, self.config.top_k)
        if len(route.queries) > 1:
            seen = {c.chunk_id for c, _ in hits}
            for query in route.queries[1:]:
                for c, score in self._retrieve_chunks(report_id, query):
                    if c.chunk_id not in seen:
                        hits.append((c, score))
                        seen.add(c.chunk_id)
            hits = sorted(hits, key=lambda item: item[1], reverse=True)[: self.config.top_k]
        retrieved_chunks = [c for c, _ in hits]
        retrieved_scores = [s for _, s in hits]

        # Step 3: Corrective RAG (CRAG) Gate
        crag_decision = self.crag.evaluate_retrieval(question_text, retrieved_chunks)
        was_reformulated = False

        if crag_decision.verdict == "AMBIGUOUS" and not was_reformulated:
            logger.info("CRAG flagged ambiguous evidence for %s. Re-retrieving with focused query.", question_id)
            refined_query = self.crag.generate_hyde_query(question_text, missing_info=crag_decision.missing_information)
            refined_hits = self._retrieve_chunks(report_id, refined_query)
            if refined_hits:
                # Merge unique chunks
                seen_ids = {c.chunk_id for c in retrieved_chunks}
                for c, s in refined_hits:
                    if c.chunk_id not in seen_ids:
                        retrieved_chunks.append(c)
                        retrieved_scores.append(s)
                        seen_ids.add(c.chunk_id)
                retrieved_chunks = retrieved_chunks[: self.config.top_k]
                retrieved_scores = retrieved_scores[: self.config.top_k]
                was_reformulated = True

        evidence_chunks_payload = [
            {"chunk_id": c.chunk_id, "report_id": c.report_id, "section": c.section, "text": c.text}
            for c in retrieved_chunks
        ]

        # Step 4: Select In-Context Demonstrations
        demos: List[Demonstration] = self.icl_selector.select(question_text, k=self.config.icl_k)

        # Step 5: Build Prompt
        prompt_builder = PROMPT_BUILDERS[self.config.prompt_version]
        user_prompt = prompt_builder(question_text, evidence_chunks_payload, demos)

        # Step 6: Generate with Schema Enforcement
        if self.config.generation.use_chat_api:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
            gen = self.llm.chat(messages, format_schema=AUDIT_ASSESSMENT_SCHEMA)
        else:
            gen = self.llm.generate(user_prompt, system=SYSTEM_PROMPT, format_schema=AUDIT_ASSESSMENT_SCHEMA)

        # Step 7: Parse Response
        parsed = self._parse_response(gen["text"])

        # Step 8: Evidence Grounding Verification
        is_grounded = self._check_evidence_grounding(parsed["supporting_evidence"], retrieved_chunks)
        cited_ids = parsed.get("evidence_chunk_ids", [])
        if not valid_citations(cited_ids, [c.chunk_id for c in retrieved_chunks]):
            is_grounded = False
        verification = None
        if self.claim_verifier and parsed["answer"] in ("Yes", "No"):
            verification = self.claim_verifier.verify(question_text, parsed["answer"], parsed["supporting_evidence"], retrieved_chunks)
            is_grounded = is_grounded and verification.supported and not verification.contradiction

        # Step 9: Quality & Safety Review Flags
        review_reasons: List[str] = []
        top_score = retrieved_scores[0] if retrieved_scores else 0.0

        if not retrieved_chunks:
            review_reasons.append("no_evidence_retrieved")
        elif top_score < self.config.min_retrieval_score:
            review_reasons.append(f"low_retrieval_confidence(score={top_score:.2f})")
        if parsed["answer"] == "ParseError":
            review_reasons.append("llm_output_failed_json_parse")
        if (
            self.config.require_evidence_for_yes_no
            and parsed["answer"] in ("Yes", "No")
            and not parsed["supporting_evidence"].strip()
        ):
            review_reasons.append("yes_no_verdict_without_supporting_evidence")
        if not is_grounded and parsed["answer"] in ("Yes", "No"):
            review_reasons.append("unsupported_evidence_citation_hallucination")
            if self.config.fail_closed_on_unsupported:
                parsed["answer"] = "Insufficient Evidence"
        if verification and verification.contradiction:
            review_reasons.append("evidence_contradicts_verdict")
        if contains_prompt_injection("\n".join(c.text for c in retrieved_chunks)):
            review_reasons.append("prompt_injection_like_report_text")

        persist = lambda value: redact_if_enabled(value, self.config.redact_persisted_output)

        return AssessmentResult(
            report_id=report_id,
            question_id=question_id,
            question_text=question_text,
            retrieved_chunk_ids=[c.chunk_id for c in retrieved_chunks],
            retrieved_scores=retrieved_scores,
            raw_llm_output=persist(gen["text"]),
            answer=parsed["answer"],
            supporting_evidence=persist(parsed["supporting_evidence"]),
            cited_chunk_ids=parsed.get("evidence_chunk_ids", []),
            justification=persist(parsed["justification"]),
            latency_s=gen["latency_s"],
            config={
                "model": self.config.generation.model_name,
                "top_k": self.config.top_k,
                "hybrid": self.config.use_hybrid,
                "reranker": self.config.use_reranker,
                "crag": self.config.use_crag,
                "hyde": self.config.use_hyde,
                "prompt_version": self.config.prompt_version,
                "icl_strategy": self.config.icl_strategy_name,
                "icl_k": self.config.icl_k,
                "temperature": self.config.generation.temperature,
                "seed": self.config.generation.seed,
                "query_route": route.mode,
                "claim_verifier": bool(self.claim_verifier),
                "fail_closed_on_unsupported": self.config.fail_closed_on_unsupported,
                "redact_persisted_output": self.config.redact_persisted_output,
            },
            crag_verdict=crag_decision.verdict,
            crag_reformulated=was_reformulated,
            is_evidence_grounded=is_grounded,
            requires_human_review=bool(review_reasons),
            review_reasons=review_reasons,
        )
