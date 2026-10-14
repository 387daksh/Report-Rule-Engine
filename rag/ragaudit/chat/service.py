"""The chatbot.

Orchestrates: resolve the question against conversation history, route it,
answer it from the structured store or from retrieved narrative, verify every
citation against the evidence actually supplied, and attach any figures bound
to the findings involved.

Citation verification is the part that matters (D06). A model that cites a
chunk_id it was never shown, or quotes text that does not appear in the
evidence, has fabricated its grounding. Both are checked here, and a failed
check downgrades the answer rather than being logged and ignored.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
import time
import uuid
from collections.abc import Sequence

from ragaudit.chat.session import Session, SessionStore, Turn
from ragaudit.domain.models import Answer, Citation, FigureRef, RetrievedChunk
from ragaudit.generate.llm import LLMError, LLMUnavailable, OllamaClient
from ragaudit.generate.prompts import (
    ANSWER_SCHEMA,
    REWRITE_SYSTEM,
    SYSTEM_PROMPT,
    build_chat_prompt,
    build_rewrite_prompt,
    estimate_tokens,
    fit_evidence_to_budget,
)
from ragaudit.retrieve.hybrid import HybridRetriever
from ragaudit.retrieve.router import Route, route_query
from ragaudit.retrieve.structured import StructuredAnswerer
from ragaudit.store.catalog import Catalog

logger = logging.getLogger("ragaudit.chat")

ORDINALS = {
    "first": 0, "1st": 0, "second": 1, "2nd": 1, "third": 2, "3rd": 2,
    "fourth": 3, "4th": 3, "fifth": 4, "5th": 4, "last": -1,
}
ORDINAL_RE = re.compile(
    r"\b(" + "|".join(ORDINALS) + r")\s+(?:one|finding|observation|issue|item)\b", re.I
)
FOLLOWUP_RE = re.compile(
    r"\b(it|its|that|those|them|they|this|the (?:same|above|previous))\b", re.I
)

#: A quote counts as grounded at or above this similarity to the best-matching
#: window of evidence text. Set high: the model is asked to copy, so anything
#: much below an exact match means it reworded, and a reworded quote presented
#: as a quotation is a provenance failure.
QUOTE_MATCH_THRESHOLD = 0.82


class ChatService:
    def __init__(
        self,
        catalog: Catalog,
        retriever: HybridRetriever,
        llm: OllamaClient,
        *,
        sessions: SessionStore | None = None,
        selector=None,
        max_history_turns: int = 8,
        rewrite_queries: bool = True,
        icl_k: int = 3,
        generation_k: int = 8,
    ) -> None:
        self.catalog = catalog
        self.retriever = retriever
        self.llm = llm
        self.sessions = sessions or SessionStore()
        self.structured = StructuredAnswerer(catalog)
        self.selector = selector
        self.max_history_turns = max_history_turns
        self.rewrite_queries = rewrite_queries
        self.icl_k = icl_k
        self.generation_k = generation_k

    # -- public ----------------------------------------------------------

    def ask(
        self,
        question: str,
        *,
        session_id: str | None = None,
        report_ids: Sequence[str] | None = None,
    ) -> tuple[Answer, Session]:
        started = time.monotonic()
        trace_id = uuid.uuid4().hex[:12]
        session = self.sessions.get_or_create(
            session_id, list(report_ids) if report_ids else None
        )
        scope = list(report_ids) if report_ids is not None else session.report_scope

        search_query = self._resolve_query(question, session)
        plan = route_query(search_query)

        logger.info(
            "question routed",
            extra={
                "trace_id": trace_id,
                "route": plan.route.value,
                "reasons": plan.reasons,
                "rewritten": search_query != question,
            },
        )

        if plan.route is Route.STRUCTURED:
            answer = self.structured.answer(search_query, plan, report_ids=scope)
        else:
            answer = self._narrative_answer(question, search_query, plan, session, scope, trace_id)
            if plan.route is Route.HYBRID:
                answer = self._merge_structured(answer, search_query, plan, scope)

        answer.trace_id = trace_id
        answer.latency_s = time.monotonic() - started
        answer.route = plan.route.value
        self.sessions.append(session, Turn(question=question, answer=answer))
        return answer, session

    # -- query resolution ------------------------------------------------

    def _resolve_query(self, question: str, session: Session) -> str:
        """Turn a follow-up into a standalone search query."""
        if not session.turns:
            return question

        # Ordinal references resolve from session state, with no model call.
        # Deterministic and free, where a rewrite would be neither.
        if match := ORDINAL_RE.search(question):
            ids = session.last_finding_ids()
            position = ORDINALS[match.group(1).lower()]
            if ids and -len(ids) <= position < len(ids):
                return f"{question} (referring to finding {ids[position]})"

        if not self.rewrite_queries or not FOLLOWUP_RE.search(question):
            return question

        try:
            completion = self.llm.generate(
                build_rewrite_prompt(question, session.history_pairs(self.max_history_turns)),
                system=REWRITE_SYSTEM,
                max_tokens=128,
            )
            rewritten = completion.text.strip().strip('"')
            # A rewrite that collapses or explodes the question is a model
            # failure; fall back rather than search on nonsense.
            if rewritten and 3 <= len(rewritten) <= 400:
                return rewritten
        except (LLMError, LLMUnavailable) as exc:
            logger.warning("query rewrite failed, using original question: %s", exc)
        return question

    # -- narrative path --------------------------------------------------

    def _narrative_answer(
        self,
        question: str,
        search_query: str,
        plan,
        session: Session,
        scope: Sequence[str] | None,
        trace_id: str,
    ) -> Answer:
        retrieved = self.retriever.retrieve(search_query, report_ids=scope)
        if not retrieved:
            return Answer(
                text=(
                    "I could not find anything in the indexed reports that addresses that. "
                    "This may mean the reports do not cover it, or that the relevant report "
                    "is not in the current scope."
                ),
                abstained=True,
                abstention_reason="no_evidence_retrieved",
                review_flags=["no_evidence_retrieved"],
                route=plan.route.value,
            )

        demos = self.selector.select(search_query, self.icl_k) if self.selector else []
        history = session.history_pairs(self.max_history_turns)

        # Retrieval ran wide for recall; generation sees only the reranked head.
        # The full list stays on the answer for evaluation, so retrieval quality
        # is still measured at top_k even though the model reads fewer passages.
        for_generation = retrieved[: self.generation_k]

        # Fit the evidence to the model's context before sending. Without
        # this the server truncates the tail of the prompt -- which is where
        # the response-format instruction lives -- and returns malformed
        # output with no error anywhere (D03).
        budget = getattr(self.llm, "prompt_budget_tokens", 8192)
        fixed_cost = estimate_tokens(
            SYSTEM_PROMPT + question + "".join(d.render(0) for d in demos)
            + "".join(t for _, t in history)
        )
        for_generation, dropped = fit_evidence_to_budget(for_generation, budget, reserve=fixed_cost)
        if not for_generation:
            logger.error(
                "prompt budget exhausted before any evidence fit",
                extra={"trace_id": trace_id, "budget": budget, "fixed_cost": fixed_cost},
            )
            return Answer(
                text=(
                    "The evidence for that question does not fit in the model's context window. "
                    "Narrow the question, or configure a model with a larger context."
                ),
                abstained=True,
                abstention_reason="prompt_budget_exhausted",
                review_flags=["prompt_budget_exhausted"],
                route=plan.route.value,
            )

        prompt = build_chat_prompt(question, for_generation, demos, history)

        try:
            completion = self.llm.chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                format_schema=ANSWER_SCHEMA,
            )
        except LLMUnavailable as exc:
            logger.error("llm unavailable: %s", exc, extra={"trace_id": trace_id})
            return Answer(
                text="The language model backend is unavailable, so I cannot answer right now.",
                abstained=True,
                abstention_reason="llm_unavailable",
                review_flags=["llm_unavailable"],
                retrieved=retrieved,
                route=plan.route.value,
            )
        except LLMError as exc:
            logger.error("llm error: %s", exc, extra={"trace_id": trace_id})
            return Answer(
                text="I hit an error generating an answer from the retrieved evidence.",
                abstained=True,
                abstention_reason="llm_error",
                review_flags=["llm_error"],
                retrieved=retrieved,
                route=plan.route.value,
            )

        # Citations are verified against what the model was actually shown.
        # Validating against the wider retrieved list would accept a citation
        # to a passage the model never saw, which is the fabrication this
        # check exists to catch.
        answer = self._build_answer(completion, for_generation, plan)
        # The full retrieved list is reported for evaluation, so retrieval
        # recall is still measured at top_k.
        answer.retrieved = retrieved
        if dropped:
            answer.review_flags.append(f"evidence_trimmed_to_context:{dropped}")
        return answer

    def _build_answer(self, completion, retrieved: list[RetrievedChunk], plan) -> Answer:
        parsed = _parse_json(completion.text)
        flags: list[str] = []

        if parsed is None:
            # Distinguish "ran out of room" from "produced nonsense". The first
            # is a configuration problem with an obvious fix; reporting both as
            # a parse failure hides that.
            truncated = getattr(completion, "truncated", False)
            reason = "truncated_generation" if truncated else "unparseable_model_output"
            text = (
                "The answer was cut off before it finished. Raise generation.max_tokens, "
                "or ask a narrower question."
                if truncated
                else "I could not produce a well-formed answer from the retrieved evidence."
            )
            logger.warning(
                "model output could not be parsed",
                extra={"reason": reason, "completion_tokens": completion.completion_tokens},
            )
            return Answer(
                text=text,
                abstained=True,
                abstention_reason=reason,
                review_flags=[reason],
                retrieved=retrieved,
                model=completion.model,
                route=plan.route.value,
            )

        answered = bool(parsed.get("answered", True))
        text = str(parsed.get("answer", "")).strip()
        if not text:
            answered = False
            text = "The evidence retrieved does not answer that question."
            flags.append("empty_answer_text")

        citations, citation_flags = self._verify_citations(parsed.get("citations", []), retrieved)
        flags.extend(citation_flags)

        # An answer asserting something with no verified citation behind it is
        # not grounded. Downgrade rather than present it as evidenced.
        if answered and not citations:
            flags.append("no_verified_citation")

        if _contains_injection(retrieved):
            flags.append("prompt_injection_like_text_in_evidence")

        figures = self._figures_for(retrieved, citations)

        return Answer(
            text=text,
            citations=citations,
            figures=figures,
            retrieved=retrieved,
            abstained=not answered,
            abstention_reason=str(parsed.get("missing_information", "")) if not answered else "",
            review_flags=flags,
            model=completion.model,
            route=plan.route.value,
        )

    # -- verification ----------------------------------------------------

    def _verify_citations(
        self, raw_citations, retrieved: list[RetrievedChunk]
    ) -> tuple[list[Citation], list[str]]:
        """Keep only citations that point at supplied evidence and quote it.

        Two independent failures are caught: a chunk_id the model was never
        shown (fabricated reference), and a quote that does not appear in the
        chunk it names (fabricated wording).
        """
        by_id = {item.chunk.chunk_id: item.chunk for item in retrieved}
        verified: list[Citation] = []
        flags: list[str] = []

        for entry in raw_citations or []:
            if not isinstance(entry, dict):
                continue
            chunk_id = str(entry.get("chunk_id", "")).strip()
            quote = str(entry.get("quote", "")).strip()
            if not chunk_id:
                continue

            chunk = by_id.get(chunk_id)
            if chunk is None:
                flags.append(f"citation_not_in_evidence:{chunk_id}")
                continue
            if quote and not _quote_supported(quote, chunk.quotable_text):
                flags.append(f"quote_not_in_chunk:{chunk_id}")
                continue

            verified.append(
                Citation(
                    chunk_id=chunk_id,
                    report_id=chunk.report_id,
                    field_path=chunk.field_path,
                    quote=quote,
                    start_char=chunk.start_char,
                    end_char=chunk.end_char,
                    finding_id=chunk.finding_id,
                )
            )
        return verified, flags

    def _figures_for(
        self, retrieved: list[RetrievedChunk], citations: list[Citation]
    ) -> list[FigureRef]:
        """Attach figures bound to the findings actually cited.

        This is a join on ``finding_id``, not a visual search. The extractor
        already binds each image to its finding, so retrieving the finding and
        following the link is exact and costs nothing (D07).
        """
        cited_findings = {c.finding_id for c in citations if c.finding_id}
        if not cited_findings:
            cited_findings = {
                item.chunk.finding_id for item in retrieved[:3] if item.chunk.finding_id
            }
        report_ids = {item.chunk.report_id for item in retrieved}

        figures: list[FigureRef] = []
        for report_id in report_ids:
            for finding_id in sorted(f for f in cited_findings if f):
                for row in self.catalog.figures_for_finding(report_id, finding_id):
                    figures.append(
                        FigureRef(
                            token=row["token"],
                            page=row["page"],
                            index=row["idx"],
                            report_id=row["report_id"],
                            asset_path=row["asset_path"],
                        )
                    )
        return figures

    # -- hybrid merge ----------------------------------------------------

    def _merge_structured(self, answer: Answer, question: str, plan, scope) -> Answer:
        """Prepend exact field results to a narrative answer.

        Where a question has both a field predicate and a judgement component,
        the counts come from SQL and the interpretation from the model, so the
        numbers are never the model's to invent.

        Only runs when there is an actual predicate to evaluate. A figure
        request routes hybrid without one, and merging there would prepend an
        unfiltered dump of every finding to an otherwise focused answer.
        """
        has_predicate = bool(
            plan.severities or plan.statuses or plan.cwe or plan.cve or plan.wants_count
        )
        if not has_predicate:
            return answer

        try:
            structured = self.structured.answer(question, plan, report_ids=scope)
        except Exception as exc:
            logger.warning("structured half of hybrid answer failed: %s", exc)
            return answer
        answer.text = f"{structured.text}\n\n{answer.text}"
        answer.citations = structured.citations + answer.citations
        answer.review_flags.extend(structured.review_flags)
        return answer


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

_INJECTION_PATTERNS = (
    r"ignore (?:all )?(?:previous|prior|above) instructions",
    r"disregard (?:the )?(?:system|previous)",
    r"you are now",
    r"system prompt",
    r"reveal (?:the )?(?:prompt|instructions)",
    r"<\s*/?\s*(?:system|assistant|tool)\s*>",
)


def _contains_injection(retrieved: Sequence[RetrievedChunk]) -> bool:
    blob = "\n".join(item.chunk.quotable_text for item in retrieved)
    return any(re.search(p, blob, re.I) for p in _INJECTION_PATTERNS)


def _parse_json(text: str) -> dict | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None
    return None


#: Characters that separate fields in a rendered chunk header. A model that
#: copies "[OBS-02] Discovery | Severity: High" back as "Discovery, Severity:
#: High" has quoted faithfully; only the punctuation differs. Comparing at
#: character level treats that as a rewrite, so separators are flattened
#: before comparison.
_SEPARATORS = str.maketrans({c: " " for c in "|,;:[]()\"'`*_-–—/\\"})


def _normalise_ws(text: str) -> str:
    return " ".join(text.lower().split())


def _tokens(text: str) -> list[str]:
    return _normalise_ws(text.translate(_SEPARATORS)).split()


def _quote_supported(quote: str, source: str) -> bool:
    """Is ``quote`` actually present in ``source``?

    Compared as word sequences with separators flattened, so a faithful copy
    that differs only in punctuation passes while a quote lifted from a
    *different* chunk still fails. That distinction is the whole point: the
    common model failure here is not rewording, it is attributing one chunk's
    text to another chunk's id.
    """
    q_tokens = _tokens(quote)
    s_tokens = _tokens(source)
    if not q_tokens or not s_tokens:
        return False

    # Contiguous run of the same words, punctuation ignored.
    if _is_sublist(q_tokens, s_tokens):
        return True

    # Otherwise require most of the quote's words to align in order against
    # the source. Operating on tokens rather than characters means a changed
    # separator costs nothing while a substituted clause still fails.
    matcher = difflib.SequenceMatcher(None, q_tokens, s_tokens, autojunk=False)
    return matcher.ratio() * (len(q_tokens) + len(s_tokens)) / (2 * len(q_tokens)) >= (
        QUOTE_MATCH_THRESHOLD
    )


def _is_sublist(needle: list[str], haystack: list[str]) -> bool:
    if len(needle) > len(haystack):
        return False
    first = needle[0]
    for start in range(len(haystack) - len(needle) + 1):
        if haystack[start] == first and haystack[start : start + len(needle)] == needle:
            return True
    return False
