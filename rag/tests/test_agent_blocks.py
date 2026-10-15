"""Block validation and reference-based render tools.

The validator is a safety gate: non-finite numbers break JSON parse in the
browser, and report-derived strings are untrusted. Render tools must pull data
by reference so the model cannot inject typed numbers.
"""

from __future__ import annotations

import json

import pytest

from ragaudit.agent.blocks import BlockError, validate_block, validate_blocks
from ragaudit.agent.evidence import EvidenceLedger
from ragaudit.agent.registry import ToolContext
from ragaudit.agent.tools import build_registry


# --------------------------------------------------------------------------
# Validator
# --------------------------------------------------------------------------


def test_valid_chart_passes():
    block = validate_block({"kind": "chart", "chart": "bar", "title": "t",
                            "x": ["High", "Low"], "series": [{"name": "c", "values": [3, 1]}]})
    assert block["x"] == ["High", "Low"]
    assert block["series"][0]["values"] == [3.0, 1.0]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_values_rejected(bad):
    """json.dumps would emit bare NaN/Infinity, invalid JSON that throws in the browser."""
    with pytest.raises(BlockError, match="non-finite"):
        validate_block({"kind": "chart", "chart": "bar", "x": ["a"],
                        "series": [{"name": "s", "values": [bad]}]})


def test_series_length_must_match_x():
    with pytest.raises(BlockError, match="values for"):
        validate_block({"kind": "chart", "chart": "bar", "x": ["a", "b"],
                        "series": [{"name": "s", "values": [1]}]})


def test_unknown_kind_rejected():
    with pytest.raises(BlockError, match="unknown block kind"):
        validate_block({"kind": "pie_of_doom"})


def test_unknown_chart_type_rejected():
    with pytest.raises(BlockError, match="unknown chart"):
        validate_block({"kind": "chart", "chart": "radar", "x": ["a"],
                        "series": [{"name": "s", "values": [1]}]})


def test_validated_blocks_are_json_safe():
    block = validate_block({"kind": "chart", "chart": "bar", "x": ["a"],
                            "series": [{"name": "s", "values": [1.5]}]})
    json.dumps(block)  # must not raise; NaN would


def test_one_bad_block_does_not_sink_the_rest():
    blocks = [
        {"kind": "chart", "chart": "bar", "x": ["a"], "series": [{"name": "s", "values": [1]}]},
        {"kind": "chart", "chart": "bar", "x": ["a"], "series": [{"name": "s", "values": [float("nan")]}]},
        {"kind": "note", "text": "fine"},
    ]
    clean, errors = validate_blocks(blocks)
    assert len(clean) == 2
    assert len(errors) == 1


def test_metric_accepts_number_or_short_string():
    assert validate_block({"kind": "metric", "label": "pct", "value": 6.25})["value"] == 6.25
    assert validate_block({"kind": "metric", "label": "verdict", "value": "PASS"})["value"] == "PASS"


def test_labels_are_capped_not_unbounded():
    block = validate_block({"kind": "note", "text": "x" * 5000})
    assert len(block["text"]) <= 1000


# --------------------------------------------------------------------------
# Render tools take references, never data
# --------------------------------------------------------------------------


@pytest.fixture
def ctx():
    c = ToolContext(catalog=None, retriever=None, settings=None, ledger=EvidenceLedger())
    c.step_results[1] = {"dimension": "severity", "counts": {"High": 3, "Low": 1}}
    c.step_results[2] = {"findings": [
        {"finding_id": "OBS-01", "severity": "High", "status": "Open", "observation_excerpt": "x"},
        {"finding_id": "OBS-02", "severity": "Low", "status": "Closed", "observation_excerpt": "y"},
    ]}
    return c


@pytest.fixture
def registry():
    return build_registry()


def test_show_chart_pulls_data_from_the_step(registry, ctx):
    result = registry.dispatch("show_chart", {"from_step": 1, "chart": "bar"}, ctx)
    assert result.ok
    block = result.blocks[0]
    assert block["x"] == ["High", "Low"]
    assert block["series"][0]["values"] == [3, 1]


def test_show_chart_without_a_step_is_a_correctable_error(registry, ctx):
    result = registry.dispatch("show_chart", {"chart": "bar"}, ctx)
    assert not result.ok
    assert "from_step" in result.error


def test_show_chart_on_a_step_with_no_chartable_data_errs(registry, ctx):
    result = registry.dispatch("show_chart", {"from_step": 2}, ctx)
    assert not result.ok  # step 2 is a row list, not {label: number}


def test_show_table_defaults_drop_excerpt_columns(registry, ctx):
    result = registry.dispatch("show_table", {"from_step": 2}, ctx)
    assert result.ok
    assert "observation_excerpt" not in result.blocks[0]["columns"]


def test_show_table_respects_requested_columns(registry, ctx):
    result = registry.dispatch("show_table", {"from_step": 2, "columns": ["finding_id", "severity"]}, ctx)
    assert result.blocks[0]["columns"] == ["finding_id", "severity"]
    assert result.blocks[0]["rows"][0] == ["OBS-01", "High"]


def test_show_note_requires_text(registry, ctx):
    assert not registry.dispatch("show_note", {}, ctx).ok
    assert registry.dispatch("show_note", {"text": "heads up"}, ctx).ok
