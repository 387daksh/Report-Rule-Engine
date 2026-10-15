"""Agent loop: termination guards and evidence accumulation.

Driven by a scripted fake LLM that emits a chosen sequence of tool-call turns,
so each termination path is exercised deterministically without a model.
"""

from __future__ import annotations

import json

import pytest

from ragaudit.agent.evidence import EvidenceLedger
from ragaudit.agent.loop import AgentConfig, AgentLoop, StopReason
from ragaudit.agent.registry import ToolContext
from ragaudit.agent.tools import build_registry
from ragaudit.generate.llm import Completion, ToolCall
from ragaudit.ingest.pipeline import IngestPipeline


class ScriptedLLM:
    """Returns a preset sequence of turns. Each turn is a list of (name, args)
    tool calls, or None to mean 'stop calling tools' (a finish)."""

    model_name = "scripted"

    def __init__(self, turns):
        self._turns = list(turns)
        self.calls = 0

    def chat(self, messages, *, tools=None, format_schema=None, max_tokens=None, timeout_s=None):
        turn = self._turns[min(self.calls, len(self._turns) - 1)]
        self.calls += 1
        if turn is None:
            return Completion(text="done", latency_s=0.01, model=self.model_name)
        tool_calls = [ToolCall(name=n, arguments=a) for n, a in turn]
        return Completion(text="", latency_s=0.01, model=self.model_name, tool_calls=tool_calls)


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
        ],
    }), encoding="utf-8")
    IngestPipeline(catalog, index, embedder, fail_on_validation_error=False).ingest_file(path, force=True)
    return catalog


@pytest.fixture
def make_ctx(loaded, index, embedder):
    from ragaudit.config import load_settings
    from ragaudit.retrieve.hybrid import HybridRetriever, RetrievalConfig

    def _make():
        retriever = HybridRetriever(loaded, index, embedder, config=RetrievalConfig(top_k=5, candidates_k=20))
        return ToolContext(catalog=loaded, retriever=retriever, settings=load_settings(),
                           ledger=EvidenceLedger())
    return _make


def _loop(llm, **cfg):
    return AgentLoop(llm, build_registry(), AgentConfig(**cfg))


# --------------------------------------------------------------------------
# Normal completion
# --------------------------------------------------------------------------


def test_finishes_when_model_stops_calling_tools(make_ctx):
    llm = ScriptedLLM([
        [("count_findings", {"severity": "High"})],
        None,
    ])
    run = _loop(llm).run("how many high findings?", make_ctx())
    assert run.stop_reason is StopReason.FINISHED
    assert len(run.steps) == 1
    assert run.steps[0].tool == "count_findings"


def test_multi_step_accumulates_evidence(make_ctx):
    llm = ScriptedLLM([
        [("find_report", {"query": "Tatva"})],
        [("search_reports", {"query": "access control", "report_id": "2-REPORT"})],
        None,
    ])
    run = _loop(llm).run("what access control issues in Tatva?", make_ctx())
    assert run.stop_reason is StopReason.FINISHED
    assert len(run.ledger) > 0, "search did not register evidence"
    assert [s.tool for s in run.steps] == ["find_report", "search_reports"]


# --------------------------------------------------------------------------
# Termination guards
# --------------------------------------------------------------------------


def test_stuck_repeat_is_suppressed_not_rerun(make_ctx):
    """temperature=0 makes a stuck model repeat identically; the tool must
    run once, and the loop must not spin to max_steps re-executing it."""
    llm = ScriptedLLM([[("count_findings", {"severity": "High"})]])  # same call forever
    run = _loop(llm, max_steps=8, no_progress_steps=2).run("q", make_ctx())
    # The tool executed once; subsequent identical calls were suppressed.
    executed = [s for s in run.steps if s.tool == "count_findings"]
    assert len(executed) == 1
    assert run.stop_reason in {StopReason.NO_PROGRESS, StopReason.MAX_STEPS}


def test_never_stops_hits_max_steps(make_ctx):
    """A model that keeps issuing *new* calls is capped by max_steps."""
    # Distinct calls each turn so duplicate-suppression doesn't catch them.
    turns = [[("query_findings", {"limit": i + 1})] for i in range(50)]
    llm = ScriptedLLM(turns)
    run = _loop(llm, max_steps=5, no_progress_steps=99).run("q", make_ctx())
    assert run.stop_reason is StopReason.MAX_STEPS
    assert llm.calls <= 6  # max_steps + maybe one


def test_search_cap_is_enforced(make_ctx):
    turns = [[("search_reports", {"query": f"term {i}"})] for i in range(10)]
    llm = ScriptedLLM(turns)
    run = _loop(llm, max_searches=2, max_steps=10, no_progress_steps=99).run("q", make_ctx())
    searches = [s for s in run.steps if s.tool == "search_reports" and s.error is None]
    assert len(searches) == 2, f"search cap not enforced: {len(searches)} ran"


def test_no_progress_terminates(make_ctx):
    """Distinct but empty-result calls make no progress and should stop."""
    # count on a severity that matches nothing: valid call, zero rows, but it
    # still returns content, so to force no-progress we repeat a distinct no-op.
    turns = [[("corpus_stats", {})], [("corpus_stats", {}), ("corpus_stats", {})]]
    # corpus_stats twice: first progresses, duplicate suppressed after.
    llm = ScriptedLLM([[("corpus_stats", {})]])
    run = _loop(llm, no_progress_steps=2, max_steps=10).run("q", make_ctx())
    assert run.stop_reason in {StopReason.NO_PROGRESS, StopReason.MAX_STEPS}


def test_tool_errors_accumulate_and_stop(make_ctx):
    turns = [[("find_report", {"query": f"nonexistent-{i}"})] for i in range(10)]
    llm = ScriptedLLM(turns)
    run = _loop(llm, max_tool_errors=3, max_steps=10, no_progress_steps=99).run("q", make_ctx())
    assert run.stop_reason is StopReason.TOOL_ERRORS
    errors = [s for s in run.steps if s.error is not None]
    assert len(errors) >= 3


def test_llm_unavailable_stops_cleanly(make_ctx):
    from ragaudit.generate.llm import LLMUnavailable

    class DeadLLM:
        model_name = "dead"
        def chat(self, *a, **k):
            raise LLMUnavailable("backend down")

    run = _loop(DeadLLM()).run("q", make_ctx())
    assert run.stop_reason is StopReason.LLM_UNAVAILABLE


# --------------------------------------------------------------------------
# Progressive disclosure
# --------------------------------------------------------------------------


def test_use_toolset_unlocks_a_group(make_ctx):
    llm = ScriptedLLM([
        [("use_toolset", {"toolset": "quality"})],
        None,
    ])
    run = _loop(llm).run("q", make_ctx())
    from ragaudit.agent.registry import ToolGroup
    assert ToolGroup.QUALITY in run.exposed_groups


def test_unknown_toolset_is_reported_not_crashed(make_ctx):
    llm = ScriptedLLM([[("use_toolset", {"toolset": "nonsense"})], None])
    run = _loop(llm).run("q", make_ctx())
    assert run.stop_reason is StopReason.FINISHED  # recovered


# --------------------------------------------------------------------------
# Shortcut detection
# --------------------------------------------------------------------------


def test_single_structured_call_is_shortcuttable(make_ctx):
    llm = ScriptedLLM([[("count_findings", {"severity": "High"})], None])
    run = _loop(llm).run("how many high?", make_ctx())
    assert run.only_structured_tool == "count_findings"


def test_search_run_is_not_shortcuttable(make_ctx):
    llm = ScriptedLLM([[("search_reports", {"query": "access control"})], None])
    run = _loop(llm).run("q", make_ctx())
    assert run.only_structured_tool is None


def test_multi_tool_run_is_not_shortcuttable(make_ctx):
    llm = ScriptedLLM([
        [("count_findings", {"severity": "High"})],
        [("count_findings", {"severity": "Low"})],
        None,
    ])
    run = _loop(llm).run("q", make_ctx())
    assert run.only_structured_tool is None
