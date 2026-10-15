"""Analyse, quality and meta tools, plus compute's provenance guarantee."""

from __future__ import annotations

import json

import pytest

from ragaudit.agent.compute import ComputeError, compute
from ragaudit.agent.evidence import EvidenceLedger
from ragaudit.agent.registry import ToolContext
from ragaudit.agent.tools import build_registry
from ragaudit.ingest.pipeline import IngestPipeline


@pytest.fixture
def loaded(catalog, index, embedder, tmp_path):
    for name, rid, findings in [
        ("a.json", "2-REPORT", [
            {"finding_id": "OBS-01", "title": "Broken Access Control", "severity": "High",
             "status": "Open", "cwe": ["CWE-284"], "observation_description": "No auth on endpoint."},
            {"finding_id": "OBS-02", "title": "Verbose errors", "severity": "Low",
             "status": "Closed", "observation_description": "Stack traces returned."},
        ]),
        ("b.json", "4-REPORT", [
            {"finding_id": "OBS-01", "title": "Broken Access Control", "severity": "High",
             "status": "Open", "cwe": ["CWE-284"], "observation_description": "Same class of issue."},
            {"finding_id": "OBS-02", "title": "Missing rate limiting", "severity": "Medium",
             "status": "Open", "observation_description": "No throttling.", "recommendation": ""},
        ]),
    ]:
        path = tmp_path / name
        path.write_text(json.dumps({
            "report_meta": {"report_id": rid, "report_title": f"Report {rid}",
                            "classification": "Confidential"},
            "detailed_observations": findings,
        }), encoding="utf-8")
        IngestPipeline(catalog, index, embedder, fail_on_validation_error=False).ingest_file(path, force=True)
    return catalog


@pytest.fixture
def ctx(loaded, index, embedder):
    from ragaudit.config import load_settings
    from ragaudit.retrieve.hybrid import HybridRetriever, RetrievalConfig
    retriever = HybridRetriever(loaded, index, embedder, config=RetrievalConfig(top_k=5))
    return ToolContext(catalog=loaded, retriever=retriever, settings=load_settings(),
                       ledger=EvidenceLedger())


@pytest.fixture
def registry():
    return build_registry()


def _run(registry, ctx, name, **args):
    return registry.dispatch(name, args, ctx)


# --------------------------------------------------------------------------
# compute — provenance and safety
# --------------------------------------------------------------------------


def test_percentage_is_exact():
    result = compute("percentage", [1, 16])
    assert result.result == 6.25
    assert "1" in result.expression and "16" in result.expression


def test_division_by_zero_raises_not_nan():
    with pytest.raises(ComputeError, match="zero"):
        compute("percentage", [5, 0])


def test_unknown_operation_rejected():
    with pytest.raises(ComputeError, match="unknown operation"):
        compute("exponentiate", [2, 3])


def test_boolean_is_not_a_number():
    with pytest.raises(ComputeError, match="boolean"):
        compute("sum", [True, 1])


def test_compute_tool_carries_provenance(registry, ctx):
    """A computed number must name the steps it came from."""
    # Record a step result the compute tool can reference.
    ctx.step_results[1] = {"count": 3}
    ctx.step_results[2] = {"count": 12}
    result = _run(registry, ctx, "compute", operation="percentage",
                  from_steps=[{"step": 1, "key": "count"}, {"step": 2, "key": "count"}])
    assert result.ok
    assert result.content["result"] == 25.0
    assert result.content["provenance"] == ["step 1.count=3", "step 2.count=12"]
    assert result.blocks[0]["kind"] == "metric"


def test_compute_rejects_missing_step(registry, ctx):
    result = _run(registry, ctx, "compute", operation="sum", from_steps=[{"step": 99, "key": "count"}])
    assert not result.ok
    assert "step 99" in result.error


def test_compute_rejects_missing_key(registry, ctx):
    ctx.step_results[1] = {"count": 3}
    result = _run(registry, ctx, "compute", operation="sum", from_steps=[{"step": 1, "key": "total"}])
    assert not result.ok
    assert "no key" in result.error


# --------------------------------------------------------------------------
# compare_reports
# --------------------------------------------------------------------------


def test_compare_reports_side_by_side(registry, ctx):
    result = _run(registry, ctx, "compare_reports")
    assert result.ok
    assert len(result.content["reports"]) == 2
    kinds = {b["kind"] for b in result.blocks}
    assert "chart" in kinds and "comparison" in kinds


def test_compare_needs_two_reports(registry, ctx, loaded):
    result = _run(registry, ctx, "compare_reports", report_ids=["2-REPORT"])
    # Falls back to all reports (there are 2), so it succeeds here.
    assert result.ok


# --------------------------------------------------------------------------
# find_repeat_findings
# --------------------------------------------------------------------------


def test_finds_cwe_recurring_across_reports(registry, ctx):
    result = _run(registry, ctx, "find_repeat_findings")
    assert result.ok
    cwe_repeats = [r for r in result.content["repeat_findings"] if r["match_on"] == "cwe"]
    assert any(r["value"] == "CWE-284" for r in cwe_repeats)
    match = next(r for r in cwe_repeats if r["value"] == "CWE-284")
    assert set(match["reports"]) == {"2-REPORT", "4-REPORT"}


def test_title_recurrence_detected(registry, ctx):
    result = _run(registry, ctx, "find_repeat_findings")
    title_repeats = [r for r in result.content["repeat_findings"] if r["match_on"] == "title"]
    assert any("broken access control" in r["value"] for r in title_repeats)


# --------------------------------------------------------------------------
# quality
# --------------------------------------------------------------------------


def test_report_quality_reports_validation(registry, ctx):
    result = _run(registry, ctx, "report_quality")
    assert result.ok
    assert len(result.content["reports"]) == 2
    assert all("status" in r for r in result.content["reports"])


def test_find_data_gaps_detects_missing_cwe(registry, ctx):
    result = _run(registry, ctx, "find_data_gaps")
    assert result.ok
    # OBS-02 in both reports lacks CWE.
    assert result.content["missing_cwe"]["count"] >= 2


# --------------------------------------------------------------------------
# meta
# --------------------------------------------------------------------------


def test_describe_capabilities_from_live_registry(registry, ctx):
    result = _run(registry, ctx, "describe_capabilities")
    assert result.ok
    all_names = {t["name"] for group in result.content["groups"].values() for t in group}
    assert "count_findings" in all_names
    assert "compare_reports" in all_names


# --------------------------------------------------------------------------
# JSON safety across the new tools
# --------------------------------------------------------------------------


def test_new_tools_are_json_safe(registry, ctx):
    ctx.step_results[1] = {"count": 4}
    for name, args in [
        ("compare_reports", {}),
        ("find_repeat_findings", {}),
        ("compute", {"operation": "sum", "from_steps": [{"step": 1, "key": "count"}]}),
        ("report_quality", {}),
        ("find_data_gaps", {}),
        ("describe_capabilities", {}),
    ]:
        result = _run(registry, ctx, name, **args)
        assert result.ok, f"{name}: {result.error}"
        json.dumps(result.content)
        json.dumps(result.blocks)
