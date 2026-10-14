"""Reranker loading and scoring.

These exist because of a bug found by running the system, not by reading it:
Qwen3-Reranker is a ``Qwen3ForCausalLM`` that scores through yes/no token
logits, but ``AutoModelForSequenceClassification`` loads it *successfully*
while randomly initialising ``score.weight``. The result is a reranker that
returns confident, meaningless orderings with no error anywhere.

Any test that only checked "does rerank() return floats" would have passed
against the broken version. These check the loading mode and the ordering.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ragaudit.retrieve.embedder import CrossEncoderReranker, ModelLoadError

RERANKER_PATH = Path(__file__).resolve().parents[1] / "models" / "Qwen3-Reranker-0.6B"
needs_weights = pytest.mark.skipif(
    not RERANKER_PATH.exists(), reason="reranker weights not staged in this environment"
)


def test_missing_weights_raise():
    with pytest.raises(ModelLoadError):
        CrossEncoderReranker("models/not-staged")


@needs_weights
def test_causal_lm_reranker_uses_logit_scoring_not_a_classification_head():
    """Regression: the classification path silently fabricates a score head."""
    reranker = CrossEncoderReranker(str(RERANKER_PATH), device="cpu", batch_size=2)
    reranker.load()
    assert reranker._mode == "logit_score"
    # The yes/no ids must come from the weights, not be guessed.
    assert reranker._true_id is not None and reranker._false_id is not None
    assert reranker._true_id != reranker._false_id


@needs_weights
def test_token_ids_match_the_shipped_config():
    """The model directory is the source of truth for these ids."""
    import json

    config = json.loads((RERANKER_PATH / "1_LogitScore" / "config.json").read_text())
    reranker = CrossEncoderReranker(str(RERANKER_PATH), device="cpu")
    reranker.load()
    assert reranker._true_id == config["true_token_id"]
    assert reranker._false_id == config["false_token_id"]


@needs_weights
def test_relevant_passage_outranks_an_irrelevant_one():
    """The behavioural check a broken scoring head cannot pass."""
    reranker = CrossEncoderReranker(str(RERANKER_PATH), device="cpu", batch_size=2)
    query = "What access control weaknesses were found?"
    passages = [
        "The audit team stayed at the Grand Hotel and travel was reimbursed in full.",
        "[OBS-01] Broken Access Control | Severity: High | The admin endpoint returned "
        "full user records to a session authenticated as a standard, non-administrative user.",
    ]
    scores = reranker.score(query, passages)
    assert len(scores) == 2
    assert scores[1] > scores[0], "the access-control passage must outrank the hotel passage"


@needs_weights
def test_batching_does_not_change_scores():
    """Qwen3 defines no pad token; a wrong padding setup corrupts batched rows."""
    reranker = CrossEncoderReranker(str(RERANKER_PATH), device="cpu", batch_size=1)
    query = "broken access control"
    passages = [
        "[OBS-01] Broken Access Control: authorisation was not enforced on the admin endpoint.",
        "[OBS-09] Verbose errors: stack traces were returned on malformed input.",
        "The report was approved by the release manager on 29 May.",
    ]
    one_at_a_time = reranker.score(query, passages)

    reranker.batch_size = 3
    batched = reranker.score(query, passages)

    for single, grouped in zip(one_at_a_time, batched):
        assert abs(single - grouped) < 0.05, "batched scoring diverged from unbatched"
