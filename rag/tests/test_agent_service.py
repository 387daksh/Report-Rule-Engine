"""ChatService with an agent: finalize, shortcut, and forced abstention.

These exercise the integration the loop tests do not: the deterministic
shortcut, the schema-constrained finalize through the existing verifier, and
the agent-path rule that a free-formed claim with no verified citation must
abstain.
"""

from __future__ import annotations

import json

import pytest

from ragaudit.agent.loop import AgentConfig, AgentLoop
from ragaudit.agent.tools import build_registry
from ragaudit.chat.service import ChatService
from ragaudit.chat.session import SessionStore
from ragaudit.config import load_settings
from ragaudit.generate.llm import Completion, ToolCall
from ragaudit.ingest.pipeline import IngestPipeline
from ragaudit.retrieve.hybrid import HybridRetriever, RetrievalConfig


class ScriptedLLM:
    """Emits scripted tool-call turns, then answers the finalize call.

    A call carrying format_schema is the finalize; it returns ``finalize_json``.
    Tool-loop turns come from ``turns`` (list of (name,args) lists, or None).
    """

    model_name = "scripted"

    def __init__(self, turns, finalize_json=None):
        self._turns = list(turns)
        self._finalize = finalize_json
        self.loop_calls = 0
        self.finalize_calls = 0

    def chat(self, messages, *, tools=None, format_schema=None, max_tokens=None, timeout_s=None):
        if format_schema is not None:
            self.finalize_calls += 1
            return Completion(text=self._finalize or "{}", latency_s=0.01, model=self.model_name)
        turn = self._turns[min(self.loop_calls, len(self._turns) - 1)]
        self.loop_calls += 1
        if turn is None:
            return Completion(text="", latency_s=0.01, model=self.model_name)
        return Completion(text="", latency_s=0.01, model=self.model_name,
                          tool_calls=[ToolCall(n, a) for n, a in turn])


@pytest.fixture
def loaded(catalog, index, embedder, tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps({
        "report_meta": {"report_id": "2-REPORT", "report_title": "Tatva API Security Testing Report",
                        "classification": "Confidential"},
        "detailed_observations": [
            {"finding_id": "OBS-01", "title": "Broken Access Control", "severity": "High",
             "status": "Open", "cwe": ["CWE-284"],
             "observation_description": "The admin endpoint did not enforce authorisation checks."},
            {"finding_id": "OBS-02", "title": "Verbose errors", "severity": "Low",
             "status": "Closed", "observation_description": "Stack traces were returned."},
            {"finding_id": "OBS-03", "title": "Weak cipher", "severity": "Medium",
             "status": "Open", "observation_description": "TLS 1.0 was negotiated."},
        ],
    }), encoding="utf-8")
    IngestPipeline(catalog, index, embedder, fail_on_validation_error=False).ingest_file(path, force=True)
    return catalog


@pytest.fixture
def make_service(loaded, index, embedder):
    def _make(llm):
        retriever = HybridRetriever(loaded, index, embedder, config=RetrievalConfig(top_k=5, candidates_k=20))
        agent = AgentLoop(llm, build_registry(), AgentConfig(max_steps=6, deadline_s=30))
        return ChatService(loaded, retriever, llm, sessions=SessionStore(),
                           agent=agent, settings=load_settings(), rewrite_queries=False)
    return _make


def _finalize_json(answer, citations, answered=True, missing=""):
    return json.dumps({
        "evidence_review": "reviewed", "answer": answer,
        "citations": citations, "answered": answered, "missing_information": missing,
    })


def _chunk_id_for(catalog, finding_id):
    rows = [r for r in catalog.all_chunks() if r["finding_id"] == finding_id]
    return rows[0]["chunk_id"]


# --------------------------------------------------------------------------
# Shortcut: one structured tool, no finalize call
# --------------------------------------------------------------------------


def test_count_shortcut_is_exact_and_skips_finalize(make_service, loaded):
    llm = ScriptedLLM([[("count_findings", {"status": "Open"})], None])
    answer, _ = make_service(llm).ask("how many open findings?")
    assert "2" in answer.text  # OBS-01, OBS-03
    assert answer.route == "structured"
    assert llm.finalize_calls == 0, "shortcut must not make a finalize call"
    assert any(f.startswith("agent_shortcut") for f in answer.review_flags)


def test_aggregate_shortcut_emits_a_block(make_service):
    llm = ScriptedLLM([[("aggregate_findings", {"by": "severity"})], None])
    answer, _ = make_service(llm).ask("break down findings by severity")
    assert answer.blocks
    assert answer.blocks[0]["kind"] == "chart"
    assert llm.finalize_calls == 0


# --------------------------------------------------------------------------
# Finalize path: searches, then schema-constrained answer through the verifier
# --------------------------------------------------------------------------


def test_search_run_finalizes_with_verified_citation(make_service, loaded):
    cid = _chunk_id_for(loaded, "OBS-01")
    llm = ScriptedLLM(
        [[("search_reports", {"query": "access control authorisation"})], None],
        finalize_json=_finalize_json(
            "OBS-01 found the admin endpoint lacked authorisation.",
            [{"chunk_id": cid, "quote": "The admin endpoint did not enforce authorisation checks"}],
        ),
    )
    answer, _ = make_service(llm).ask("what access control issues were found?")
    assert llm.finalize_calls == 1
    assert len(answer.citations) == 1
    assert answer.citations[0].chunk_id == cid
    assert not answer.abstained
    assert answer.steps  # trace recorded


def test_fabricated_citation_in_finalize_is_rejected(make_service):
    """Verification still runs on the agent path."""
    llm = ScriptedLLM(
        [[("search_reports", {"query": "access control"})], None],
        finalize_json=_finalize_json(
            "Everything was fine.",
            [{"chunk_id": "totally-made-up", "quote": "all controls passed"}],
        ),
    )
    answer, _ = make_service(llm).ask("what was found?")
    assert answer.citations == []
    assert any(f.startswith("citation_not_in_evidence") for f in answer.review_flags)


def test_narrative_claim_without_citation_forces_abstention(make_service):
    """The agent-path hardening: free-formed prose with zero verified
    citations and no structured result must abstain, not just flag."""
    llm = ScriptedLLM(
        [[("search_reports", {"query": "quantum encryption"})], None],
        finalize_json=_finalize_json("The system uses military-grade quantum encryption.", []),
    )
    answer, _ = make_service(llm).ask("what encryption is used?")
    assert answer.abstained
    assert answer.abstention_reason == "no_verified_citation"
    assert "agent_forced_abstention" in answer.review_flags


def test_structured_summary_answer_is_allowed_without_chunk_citation(make_service):
    """A count-backed answer needs no chunk citation — the number is exact."""
    cid_free = "n/a"  # no citation, but a structured summary exists
    llm = ScriptedLLM(
        [[("count_findings", {"severity": "High"})],
         [("search_reports", {"query": "detail"})],  # forces non-shortcut (2 tools)
         None],
        finalize_json=_finalize_json("There is 1 high-severity finding.", []),
    )
    answer, _ = make_service(llm).ask("how many high findings and what are they about?")
    # structured_summary is present, so the forced-abstention rule does NOT fire.
    assert not answer.abstained or answer.abstention_reason != "no_verified_citation"


# --------------------------------------------------------------------------
# Effective route
# --------------------------------------------------------------------------


def test_effective_route_structured_for_single_count(make_service):
    llm = ScriptedLLM([[("count_findings", {"severity": "High"})], None])
    answer, _ = make_service(llm).ask("how many high?")
    assert answer.route == "structured"


def test_effective_route_narrative_for_search_only(make_service, loaded):
    cid = _chunk_id_for(loaded, "OBS-01")
    llm = ScriptedLLM(
        [[("search_reports", {"query": "access control"})], None],
        finalize_json=_finalize_json("Found access control issues.",
                                     [{"chunk_id": cid, "quote": "The admin endpoint did not enforce authorisation checks"}]),
    )
    answer, _ = make_service(llm).ask("what issues?")
    assert answer.route == "narrative"


# --------------------------------------------------------------------------
# Failure handling
# --------------------------------------------------------------------------


def test_llm_unavailable_keeps_gathered_results(make_service):
    from ragaudit.generate.llm import LLMUnavailable

    class PartialLLM(ScriptedLLM):
        def chat(self, messages, *, tools=None, format_schema=None, max_tokens=None, timeout_s=None):
            if self.loop_calls >= 1 and format_schema is None:
                raise LLMUnavailable("died mid-run")
            return super().chat(messages, tools=tools, format_schema=format_schema,
                                max_tokens=max_tokens, timeout_s=timeout_s)

    llm = PartialLLM([[("count_findings", {"severity": "High"})], [("count_findings", {"status": "Open"})]])
    answer, _ = make_service(llm).ask("analyse the findings")
    assert answer.abstained
    assert answer.abstention_reason == "llm_unavailable"


def test_chitchat_still_bypasses_the_agent(make_service):
    llm = ScriptedLLM([None])
    answer, _ = make_service(llm).ask("hey")
    assert answer.route == "chitchat"
    assert llm.loop_calls == 0, "greeting reached the agent loop"
    assert llm.finalize_calls == 0


# --------------------------------------------------------------------------
# Scope enforcement — report filtering is the whole point
# --------------------------------------------------------------------------


def test_named_report_scopes_the_whole_run(make_service, loaded):
    """'In the Tatva report' must not pull evidence from other reports, even
    when the small model forgets to scope its own tool calls."""
    cid = _chunk_id_for(loaded, "OBS-01")
    # The model searches WITHOUT a report_id; the default scope must apply.
    llm = ScriptedLLM(
        [[("search_reports", {"query": "access control"})], None],
        finalize_json=_finalize_json("Found access control issues.",
                                     [{"chunk_id": cid, "quote": "The admin endpoint did not enforce authorisation checks"}]),
    )
    answer, _ = make_service(llm).ask("In the Tatva report, what access control issues were found?")
    # Every retrieved chunk must be from 2-REPORT (Tatva), none from elsewhere.
    assert answer.retrieved
    assert all(r.chunk.report_id == "2-REPORT" for r in answer.retrieved)


def test_ui_scope_is_enforced_in_the_agent_path(make_service, loaded):
    cid = _chunk_id_for(loaded, "OBS-01")
    llm = ScriptedLLM(
        [[("search_reports", {"query": "anything"})], None],
        finalize_json=_finalize_json("x", [{"chunk_id": cid, "quote": "The admin endpoint did not enforce authorisation checks"}]),
    )
    answer, _ = make_service(llm).ask("what issues?", report_ids=["2-REPORT"])
    assert all(r.chunk.report_id == "2-REPORT" for r in answer.retrieved)


def test_comparison_does_not_scope_to_one_report(make_service, loaded):
    """'compare' naming one report must still see the others."""
    from ragaudit.chat.service import _default_scope
    # Unit-level: a comparison question with one named report yields no scope.
    assert _default_scope(None, {"report_ids": ["2-REPORT"]}, "compare the Tatva report with report 4") is None
    assert _default_scope(None, {"report_ids": ["2-REPORT"]}, "what is in the Tatva report") == ["2-REPORT"]
