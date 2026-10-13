"""Evaluation metrics, including the statistics the previous harness lacked."""

from __future__ import annotations

from dataclasses import dataclass, field

from ragaudit.eval.metrics import (
    FAILURE_CLASS,
    bootstrap_mean,
    classification_report,
    grounding_report,
    hit_rate_at_k,
    mcnemar,
    minimum_detectable_difference,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)


# --------------------------------------------------------------------------
# Retrieval metrics
# --------------------------------------------------------------------------


def test_precision_and_recall():
    assert precision_at_k(["a", "b", "c", "d"], ["a", "c"], 4) == 0.5
    assert recall_at_k(["a", "b"], ["a", "c"], 2) == 0.5


def test_recall_is_undefined_without_gold_labels():
    """Undefined, not zero: averaging zeros here silently deflates the mean."""
    assert recall_at_k(["a"], [], 1) is None


def test_hit_rate_and_mrr():
    assert hit_rate_at_k(["x", "a"], ["a"], 2) == 1.0
    assert hit_rate_at_k(["x", "y"], ["a"], 2) == 0.0
    assert reciprocal_rank(["x", "a"], ["a"]) == 0.5
    assert reciprocal_rank(["x", "y"], ["a"]) == 0.0


def test_ndcg_rewards_ranking_relevant_items_higher():
    assert ndcg_at_k(["a", "x", "y"], ["a"], 3) > ndcg_at_k(["x", "y", "a"], ["a"], 3)
    assert ndcg_at_k(["a", "b"], ["a", "b"], 2) == 1.0


# --------------------------------------------------------------------------
# Uncertainty
# --------------------------------------------------------------------------


def test_bootstrap_interval_brackets_the_point_estimate():
    interval = bootstrap_mean([1.0] * 13 + [0.0] * 3)
    assert abs(interval.point - 0.8125) < 1e-9
    assert interval.low < interval.point < interval.high


def test_small_samples_produce_wide_intervals():
    """The headline 81.25% was computed on n=16."""
    narrow = bootstrap_mean([1.0] * 130 + [0.0] * 30)
    wide = bootstrap_mean([1.0] * 13 + [0.0] * 3)
    assert wide.width > narrow.width
    assert wide.width > 0.15, "an n=16 interval should be visibly wide"


def test_bootstrap_is_reproducible():
    values = [1.0, 0.0, 1.0, 1.0, 0.0]
    assert bootstrap_mean(values, seed=7) == bootstrap_mean(values, seed=7)


def test_minimum_detectable_difference_shrinks_with_n():
    assert minimum_detectable_difference(16) > minimum_detectable_difference(400)
    # At n=16 nothing below roughly 20 points is resolvable.
    assert minimum_detectable_difference(16) > 0.15


# --------------------------------------------------------------------------
# Paired comparison
# --------------------------------------------------------------------------


def test_mcnemar_finds_no_significance_in_a_small_gap():
    """The 62.5% vs 75% ICL gap on n=16 is two discordant items."""
    a = [True] * 10 + [False] * 6
    b = [True] * 12 + [False] * 4
    result = mcnemar(a, b)
    assert not result.significant
    assert "within what chance produces" in result.verdict("zero-shot", "few-shot")


def test_mcnemar_detects_a_consistent_difference():
    a = [True] * 40 + [False] * 10
    b = [False] * 50
    assert mcnemar(a, b).significant


def test_mcnemar_ignores_items_both_systems_agree_on():
    base_a = [True, False]
    base_b = [False, True]
    small = mcnemar(base_a, base_b)
    padded = mcnemar(base_a + [True] * 50, base_b + [True] * 50)
    assert small.p_value == padded.p_value
    assert padded.n_pairs > small.n_pairs


def test_mcnemar_on_identical_systems():
    result = mcnemar([True, False, True], [True, False, True])
    assert result.p_value == 1.0
    assert "agree on every item" in result.verdict()


# --------------------------------------------------------------------------
# Classification
# --------------------------------------------------------------------------


def test_pipeline_failures_are_not_folded_into_a_content_class():
    """Regression: the old harness mapped ParseError to Insufficient Evidence,
    so a crashed run scored as principled abstention."""
    report = classification_report(
        ["Yes", "Yes", "No"],
        ["Yes", "ParseError", "No"],
        classes=["Yes", "No", "Insufficient Evidence"],
    )
    assert FAILURE_CLASS in report.classes
    assert report.failures == 1
    insufficient = report.classes.index("Insufficient Evidence")
    assert sum(row[insufficient] for row in report.matrix) == 0


def test_macro_f1_ignores_classes_with_no_gold_examples():
    """The corpus has no Insufficient Evidence gold label; averaging over it
    drags macro-F1 down and makes the number unreadable."""
    report = classification_report(
        ["Yes"] * 8 + ["No"] * 8,
        ["Yes"] * 8 + ["No"] * 8,
        classes=["Yes", "No", "Insufficient Evidence"],
    )
    assert report.macro_f1 == 1.0
    assert report.per_class["Insufficient Evidence"]["support"] == 0


def test_accuracy_carries_an_interval():
    report = classification_report(["Yes"] * 13 + ["No"] * 3, ["Yes"] * 16)
    assert report.accuracy.low < report.accuracy.point < report.accuracy.high
    assert report.to_dict()["minimum_detectable_difference"] > 0


# --------------------------------------------------------------------------
# Grounding
# --------------------------------------------------------------------------


@dataclass
class _Answer:
    abstained: bool = False
    citations: list = field(default_factory=list)
    review_flags: list = field(default_factory=list)


def test_grounding_counts_verification_outcomes_not_word_overlap():
    answers = [
        _Answer(citations=["c1"]),
        _Answer(citations=[], review_flags=["citation_not_in_evidence:xyz"]),
        _Answer(citations=[], review_flags=["quote_not_in_chunk:abc"]),
        _Answer(abstained=True),
    ]
    report = grounding_report(answers)
    assert report.answered == 3
    assert report.with_citation == 1
    assert report.fabricated_citations == 1
    assert report.fabricated_quotes == 1
    assert report.abstentions == 1
    assert 0 < report.fabrication_rate <= 1


def test_grounding_report_handles_an_empty_run():
    report = grounding_report([])
    assert report.citation_rate == 0.0
