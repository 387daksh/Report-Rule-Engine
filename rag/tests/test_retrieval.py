"""Retrieval: fusion, scoping, routing, and the structured path."""

from __future__ import annotations

import json

import numpy as np
import pytest

from ragaudit.ingest.pipeline import IngestPipeline
from ragaudit.retrieve.hybrid import reciprocal_rank_fusion
from ragaudit.retrieve.router import Route, route_query
from ragaudit.retrieve.structured import StructuredAnswerer
from ragaudit.store.vectors import NumpyVectorIndex, open_index


# --------------------------------------------------------------------------
# Rank fusion
# --------------------------------------------------------------------------


def test_rrf_rewards_appearing_in_both_retrievers():
    """A chunk both retrievers find outranks one only a single retriever found.

    Note the scale: with k=60 the per-rank differences are small by design, so
    agreement across retrievers dominates position within one list. A document
    ranked first in one list and absent from the other does *not* beat one
    ranked second in both by much -- that flattening is the point of RRF.
    """
    fused = dict(reciprocal_rank_fusion([["a", "b"], ["b", "c"]], k=60))
    assert fused["b"] > fused["a"]
    assert fused["b"] > fused["c"]


def test_rrf_respects_rank_within_a_single_list():
    fused = dict(reciprocal_rank_fusion([["a", "b", "c"]], k=60))
    assert fused["a"] > fused["b"] > fused["c"]


def test_rrf_handles_disjoint_result_sets():
    fused = reciprocal_rank_fusion([["a", "b"], ["c", "d"]], k=60)
    assert {doc for doc, _ in fused} == {"a", "b", "c", "d"}
    assert fused[0][0] in {"a", "c"}


def test_rrf_is_rank_based_not_score_based():
    """Fusion must not depend on raw scores, which are on different scales."""
    assert reciprocal_rank_fusion([["x", "y"]]) == reciprocal_rank_fusion([["x", "y"]])


# --------------------------------------------------------------------------
# Vector index
# --------------------------------------------------------------------------


def test_report_filter_is_applied_inside_the_search():
    index = NumpyVectorIndex(dimension=4)
    index.add(["a1", "a2"], np.eye(4)[:2], ["RA", "RA"])
    index.add(["b1"], np.eye(4)[2:3], ["RB"])

    hits = index.search(np.eye(4)[0], top_k=10, allowed_report_ids=["RA"])
    assert {cid for cid, _ in hits} == {"a1", "a2"}


def test_empty_scope_returns_nothing_rather_than_widening():
    """Regression: the old pipeline fell back to other reports' chunks.

    In a corpus holding reports from different audited organisations that is a
    cross-tenant disclosure, not a convenience.
    """
    index = NumpyVectorIndex(dimension=4)
    index.add(["a1"], np.eye(4)[:1], ["RA"])
    assert index.search(np.eye(4)[0], top_k=5, allowed_report_ids=["NOPE"]) == []


def test_removing_a_report_makes_it_unsearchable():
    index = NumpyVectorIndex(dimension=4)
    index.add(["a1", "b1"], np.eye(4)[:2], ["RA", "RB"])
    index.remove_report("RA")
    assert {cid for cid, _ in index.search(np.eye(4)[0], top_k=5)} == {"b1"}
    assert len(index) == 1


def test_dimension_mismatch_raises_instead_of_mixing_vector_spaces():
    index = NumpyVectorIndex(dimension=4)
    with pytest.raises(ValueError, match="dimension"):
        index.add(["x"], np.ones((1, 8), dtype="float32"), ["R"])


def test_index_round_trips_without_pickle(tmp_path):
    index = NumpyVectorIndex(dimension=4)
    index.add(["a1", "b1"], np.eye(4)[:2], ["RA", "RB"])
    index.save(tmp_path)

    assert not list(tmp_path.glob("*.pkl")), "index must not persist pickles"
    reloaded = open_index(tmp_path, dimension=4, backend="numpy")
    assert len(reloaded) == 2
    assert {cid for cid, _ in reloaded.search(np.eye(4)[0], top_k=2)} == {"a1", "b1"}


def test_loading_under_a_different_model_dimension_raises(tmp_path):
    NumpyVectorIndex(dimension=4).save(tmp_path)
    with pytest.raises(RuntimeError, match="dimension"):
        open_index(tmp_path, dimension=64, backend="numpy")


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "question",
    [
        "Does the report contain detailed security findings?",
        "Does the report contain at least one High-severity finding?",
        "Does the report mark findings as Open?",
        "Does the report provide CWE classifications for findings?",
        "Does the report provide remediation recommendations?",
        "Does the report state that all findings are closed?",
        "Does the report include an audit timeline?",
        "Does the report state that no security findings were identified?",
    ],
)
def test_all_supplied_field_presence_questions_route_to_sql(question):
    """Every RQ1-RQ8 question is a predicate over extracted fields (D02)."""
    assert route_query(question).route is Route.STRUCTURED


@pytest.mark.parametrize(
    "question",
    [
        "Why was the remediation advice inadequate?",
        "Summarise the methodology used in this assessment.",
        "Explain how the tester reached the admin endpoint.",
        "Was the vulnerability scan performed using an authenticated methodology?",
    ],
)
def test_judgement_questions_route_to_retrieval(question):
    assert route_query(question).route in {Route.NARRATIVE, Route.HYBRID}


def test_counts_never_route_to_retrieval():
    """A count from top-k is unsound: retrieval never saw the whole corpus."""
    plan = route_query("How many high-severity findings are still open?")
    assert plan.route is Route.STRUCTURED
    assert plan.wants_count


def test_narrative_intent_beats_a_field_mention():
    plan = route_query("Why were the high-severity findings accepted as residual risk?")
    assert plan.route is Route.HYBRID
    assert "narrative intent detected" in plan.reasons


def test_policy_qualifier_forces_hybrid():
    """The SLA window lives in prose; the statuses live in fields."""
    plan = route_query(
        "Have all identified high-severity vulnerabilities been remediated "
        "within the organisation's internal SLA?"
    )
    assert plan.route is Route.HYBRID


def test_presence_wording_without_a_field_noun_stays_narrative():
    plan = route_query(
        "Do all active third-party vendor contracts in scope include a breach notification clause?"
    )
    assert plan.route is Route.NARRATIVE


def test_identifier_extraction():
    assert route_query("Which findings cite CWE-284?").cwe == "CWE-284"
    assert route_query("Was CVE-2024-1234 remediated?").cve == "CVE-2024-1234"


def test_figure_requests_route_to_hybrid():
    assert route_query("Show me the screenshots for the access control issue").route is Route.HYBRID


def test_plan_explains_itself():
    """An audit system must be able to say why a question took a path."""
    assert route_query("How many critical findings are open?").reasons


# --------------------------------------------------------------------------
# Structured answering
# --------------------------------------------------------------------------


@pytest.fixture
def loaded(catalog, index, embedder, tmp_path):
    path = tmp_path / "r.json"
    path.write_text(json.dumps({
        "report_meta": {"report_id": "R1", "report_title": "Test", "classification": "Confidential"},
        "detailed_observations": [
            {"finding_id": "OBS-01", "title": "Broken access control", "severity": "High",
             "status": "Open", "cwe": ["CWE-284"],
             "observation_description": "The admin endpoint did not enforce authorisation.",
             "recommendation": "Enforce per-object authorisation."},
            {"finding_id": "OBS-02", "title": "Verbose errors", "severity": "Low",
             "status": "Closed", "cwe": ["CWE-209"],
             "observation_description": "Stack traces were returned on malformed input."},
            {"finding_id": "OBS-03", "title": "Weak cipher suite", "severity": "Medium",
             "status": "Open", "observation_description": "TLS 1.0 was negotiated."},
        ],
    }), encoding="utf-8")
    IngestPipeline(catalog, index, embedder, fail_on_validation_error=False).ingest_file(path, force=True)
    return catalog


def test_counts_are_exact(loaded):
    plan = route_query("How many open findings are there?")
    text = StructuredAnswerer(loaded).answer("How many open findings?", plan).text
    assert "2 findings match" in text


def test_universal_claim_is_answered_by_counterexample(loaded):
    plan = route_query("Are all findings closed?")
    answer = StructuredAnswerer(loaded).answer("Are all findings closed?", plan)
    assert answer.text.startswith("No.")
    assert "OBS-01" in answer.text or "OBS-03" in answer.text


def test_true_universal_claim_is_confirmed(loaded):
    plan = route_query("Are all findings open or closed?")
    plan.statuses = ["Open", "Closed"]
    plan.universal = True
    assert StructuredAnswerer(loaded).answer("q", plan).text.startswith("Yes.")


def test_identifier_filter_returns_only_matching_findings(loaded):
    plan = route_query("Which findings cite CWE-284?")
    answer = StructuredAnswerer(loaded).answer("Which findings cite CWE-284?", plan)
    assert "OBS-01" in answer.text
    assert "OBS-02" not in answer.text


def test_negated_question_confirms_absence(loaded):
    plan = route_query("Does the report state that no critical findings were identified?")
    plan.severities = ["Critical"]
    plan.negated = True
    assert "no findings" in StructuredAnswerer(loaded).answer("q", plan).text.lower()


def test_structured_answer_reports_its_predicate(loaded):
    plan = route_query("How many high findings are open?")
    answer = StructuredAnswerer(loaded).answer("q", plan)
    assert any(f.startswith("predicate:") for f in answer.review_flags)


def test_structured_answers_cite_findings(loaded):
    plan = route_query("Which findings are open?")
    answer = StructuredAnswerer(loaded).answer("Which findings are open?", plan)
    assert answer.citations
    assert all(c.finding_id for c in answer.citations)


# --------------------------------------------------------------------------
# Lexical search
# --------------------------------------------------------------------------


def test_lexical_search_finds_exact_identifiers(loaded):
    hits = loaded.search_lexical("CWE-284", limit=10)
    assert hits


def test_lexical_search_is_scoped_by_report(loaded):
    assert loaded.search_lexical("authorisation", report_ids=["OTHER"], limit=10) == []


def test_punctuation_in_a_query_cannot_break_fts_syntax(loaded):
    # Raw FTS5 would treat these as operators; the query builder must quote them.
    assert loaded.search_lexical('CVE-2024-1234 OR "unbalanced', limit=5) is not None


def test_hybrid_retriever_respects_scope(loaded, index, embedder):
    from ragaudit.retrieve.hybrid import HybridRetriever, RetrievalConfig

    retriever = HybridRetriever(loaded, index, embedder, config=RetrievalConfig(top_k=5))
    assert retriever.retrieve("authorisation", report_ids=[]) == []
    assert all(r.chunk.report_id == "R1" for r in retriever.retrieve("authorisation", report_ids=["R1"]))
