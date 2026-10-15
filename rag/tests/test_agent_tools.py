"""Tool-layer tests: each tool against a real in-memory catalogue.

Covers the three things the registry promises — JSON-safe output, correctable
errors (not exceptions) for bad arguments, and that only the search group
registers evidence. Uses a tiny real corpus so entity resolution and SQL are
exercised, not mocked.
"""

from __future__ import annotations

import json

import pytest

from ragaudit.agent.evidence import EvidenceLedger
from ragaudit.agent.registry import ToolContext, ToolGroup
from ragaudit.agent.tools import build_registry
from ragaudit.ingest.pipeline import IngestPipeline


@pytest.fixture
def loaded(catalog, index, embedder, tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps({
        "report_meta": {"report_id": "2-REPORT", "report_title": "Tatva API Security Testing Report",
                        "classification": "Confidential"},
        "detailed_observations": [
            {"finding_id": "OBS-01", "title": "Broken Access Control", "severity": "High",
             "status": "Open", "cwe": ["CWE-284"],
             "observation_description": "The admin endpoint did not enforce authorisation checks on token transitions.",
             "recommendation": "Enforce per-object authorisation."},
            {"finding_id": "OBS-02", "title": "Verbose errors", "severity": "Low",
             "status": "Closed", "cwe": ["CWE-209"],
             "observation_description": "Stack traces were returned on malformed input."},
            {"finding_id": "OBS-03", "title": "Weak cipher", "severity": "Medium",
             "status": "Open", "observation_description": "TLS 1.0 was negotiated."},
        ],
    }), encoding="utf-8")
    IngestPipeline(catalog, index, embedder, fail_on_validation_error=False).ingest_file(path, force=True)
    return catalog


@pytest.fixture
def ctx(loaded, index, embedder):
    from ragaudit.retrieve.hybrid import HybridRetriever, RetrievalConfig
    from ragaudit.config import load_settings
    retriever = HybridRetriever(loaded, index, embedder, config=RetrievalConfig(top_k=5, candidates_k=20))
    return ToolContext(catalog=loaded, retriever=retriever, settings=load_settings(),
                       ledger=EvidenceLedger(), current_step=1)


@pytest.fixture
def registry():
    return build_registry()


def _run(registry, ctx, name, **args):
    return registry.dispatch(name, args, ctx)


def _json_safe(obj) -> bool:
    try:
        json.dumps(obj)
        return True
    except (TypeError, ValueError):
        return False


# --------------------------------------------------------------------------
# Registry contract
# --------------------------------------------------------------------------


def test_all_tools_have_valid_schemas(registry):
    for name in registry.names():
        schema = registry.get(name).schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == name
        assert "parameters" in schema["function"]


def test_schemas_filter_by_group(registry):
    nav = registry.schemas({ToolGroup.NAVIGATE})
    names = {s["function"]["name"] for s in nav}
    assert "list_reports" in names
    assert "search_reports" not in names


def test_unknown_tool_is_a_correctable_error_not_a_crash(registry, ctx):
    result = registry.dispatch("nonexistent_tool", {}, ctx)
    assert not result.ok
    assert "unknown tool" in result.error


def test_every_tool_result_is_json_safe(registry, ctx):
    for name, args in [
        ("list_reports", {}), ("corpus_stats", {}), ("describe_schema", {}),
        ("find_report", {"query": "Tatva"}),
        ("query_findings", {"severity": "High"}),
        ("count_findings", {"status": "Open"}),
        ("aggregate_findings", {"by": "severity"}),
        ("aggregate_findings", {"by": "severity", "then_by": "status"}),
        ("distinct_values", {"field": "severity"}),
        ("top_values", {"field": "cwe"}),
        ("get_finding", {"finding_id": "OBS-01"}),
        ("search_reports", {"query": "access control"}),
        ("keyword_search", {"query": "CWE-284"}),
        ("get_finding_text", {"finding_id": "OBS-01"}),
    ]:
        result = _run(registry, ctx, name, **args)
        assert result.ok, f"{name} failed: {result.error}"
        assert _json_safe(result.content), f"{name} returned non-JSON-safe content"
        assert _json_safe(result.blocks)


# --------------------------------------------------------------------------
# Entity resolution — the gap this closes
# --------------------------------------------------------------------------


def test_find_report_resolves_a_name_to_an_id(registry, ctx):
    result = _run(registry, ctx, "find_report", query="Tatva")
    assert result.content["report_id"] == "2-REPORT"


def test_bare_number_resolves_to_full_report_id(registry, ctx):
    result = _run(registry, ctx, "query_findings", report_id="2", severity="High")
    assert result.ok
    assert all(f["report_id"] == "2-REPORT" for f in result.content["findings"])


def test_unknown_report_is_a_correctable_error(registry, ctx):
    result = _run(registry, ctx, "find_report", query="Nonexistent Corp")
    assert not result.ok
    assert "no report matches" in result.error.lower() or "known reports" in result.error.lower()


def test_bad_severity_names_the_valid_options(registry, ctx):
    result = _run(registry, ctx, "query_findings", severity="supercritical")
    assert not result.ok
    assert "High" in result.error


# --------------------------------------------------------------------------
# Exactness
# --------------------------------------------------------------------------


def test_count_is_exact_and_separate_from_the_page(registry, ctx):
    result = _run(registry, ctx, "count_findings", status="Open")
    assert result.content["count"] == 2  # OBS-01, OBS-03


def test_query_carries_true_total_even_when_paged(registry, ctx):
    result = _run(registry, ctx, "query_findings", limit=1)
    assert result.content["returned"] == 1
    assert result.content["total"] == 3
    assert result.content["truncated"] is True


def test_two_dimensional_aggregate_cross_tabs(registry, ctx):
    result = _run(registry, ctx, "aggregate_findings", by="severity", then_by="status")
    cross = result.content["cross_tab"]
    assert cross["High"]["Open"] == 1
    assert result.blocks and result.blocks[0]["chart"] == "stacked_bar"


# --------------------------------------------------------------------------
# Evidence discipline — the integrity-critical part
# --------------------------------------------------------------------------


def test_structured_tools_register_no_evidence(registry, ctx):
    """query_findings/get_finding surface excerpts, not citable text."""
    _run(registry, ctx, "query_findings", severity="High")
    _run(registry, ctx, "get_finding", finding_id="OBS-01")
    _run(registry, ctx, "count_findings", status="Open")
    _run(registry, ctx, "aggregate_findings", by="severity")
    assert len(ctx.ledger) == 0, "a structured tool registered evidence it should not have"


def test_search_registers_evidence(registry, ctx):
    _run(registry, ctx, "search_reports", query="access control authorisation")
    assert len(ctx.ledger) > 0


def test_registered_text_matches_what_was_returned(registry, ctx):
    """The ledger must hold exactly the shown slice, for verification to be sound."""
    result = _run(registry, ctx, "search_reports", query="authorisation")
    for passage in result.content["passages"]:
        shown = ctx.ledger.shown_text(passage["chunk_id"])
        assert shown == passage["text"], "ledger text diverged from what the model was shown"


def test_get_finding_text_makes_finding_prose_citable(registry, ctx):
    result = _run(registry, ctx, "get_finding_text", finding_id="OBS-01")
    assert result.content["passages"]
    cid = result.content["passages"][0]["chunk_id"]
    assert cid in ctx.ledger


def test_excerpts_are_marked_non_quotable(registry, ctx):
    result = _run(registry, ctx, "get_finding", finding_id="OBS-01")
    assert "not quotable" in result.content["finding"]["note"].lower()


# --------------------------------------------------------------------------
# describe_schema — self-knowledge
# --------------------------------------------------------------------------


def test_describe_schema_reports_population(registry, ctx):
    result = _run(registry, ctx, "describe_schema")
    # organisation is empty on this report; the tool must say so, not hide it.
    assert result.content["report_fields"]["organisation"]["populated"] == 0
    assert result.content["finding_fields"]["severity"]["populated"] == 3


# --------------------------------------------------------------------------
# "all" sentinel — the agent reaches for it constantly
# --------------------------------------------------------------------------


def test_all_means_no_scope_not_a_report_to_resolve(registry, ctx):
    """Regression: the model passes report_id='all' to mean every report.
    It must aggregate across all, not error on an unresolvable 'all'."""
    result = _run(registry, ctx, "aggregate_findings", by="severity", report_id="all")
    assert result.ok, result.error
    assert result.content["total"] > 0


def test_all_reports_sentinel_on_count(registry, ctx):
    result = _run(registry, ctx, "count_findings", severity="High", report_id="all reports")
    assert result.ok
    assert result.content["count"] >= 1
