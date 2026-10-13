"""Regressions for the silent-failure paths in the previous implementation.

Each test here pins a behaviour where the old pipeline produced a plausible
number from a broken component. The common thread: a failure must be visible
in the output, not inferable only from reading the logs.
"""

from __future__ import annotations

import pytest
import requests

from ragaudit.generate.llm import LLMError, LLMUnavailable, OllamaClient
from ragaudit.retrieve.embedder import CrossEncoderReranker, Embedder, ModelLoadError


# --------------------------------------------------------------------------
# Model loading: fail loud, never substitute
# --------------------------------------------------------------------------


def test_missing_embedding_weights_raise_rather_than_substituting_a_model():
    """Old behaviour: fell back from bge-m3 to bge-large, silently changing
    the vector space, with nothing recorded about which model actually ran."""
    with pytest.raises(ModelLoadError, match="not found"):
        Embedder("models/definitely-not-staged")


def test_missing_reranker_weights_raise_rather_than_scoring_by_rank():
    """Old behaviour: returned 1.0/(i+1) as a 'score', so rank 0 always scored
    exactly 1.0 and always cleared the confidence gate."""
    with pytest.raises(ModelLoadError, match="not found"):
        CrossEncoderReranker("models/definitely-not-staged")


def test_model_load_error_names_the_path_it_tried():
    with pytest.raises(ModelLoadError) as exc:
        Embedder("models/nope")
    assert "models/nope" in str(exc.value) or "models\\nope" in str(exc.value)


# --------------------------------------------------------------------------
# LLM client
# --------------------------------------------------------------------------


class _Response:
    def __init__(self, status_code: int, payload=None, text: str = ""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class _RecordingSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def post(self, url, json=None, timeout=None):
        self.calls += 1
        item = self.responses[min(self.calls - 1, len(self.responses) - 1)]
        if isinstance(item, Exception):
            raise item
        return item

    def get(self, url, timeout=None):
        return _Response(200)

    def close(self):
        pass


def _client(session, **kwargs):
    return OllamaClient(session=session, backoff_base_s=0.0, **kwargs)


def test_client_does_not_retry_a_client_error():
    """A 400 will fail identically on attempt three; retrying it only triples
    the latency of a guaranteed failure."""
    session = _RecordingSession([_Response(400, text="bad request")])
    with pytest.raises(LLMError, match="rejected the request"):
        _client(session, max_retries=3).generate("hi")
    assert session.calls == 1


def test_client_retries_a_transient_error_then_succeeds():
    session = _RecordingSession([
        _Response(503, text="warming up"),
        _Response(200, {"response": "ok"}),
    ])
    completion = _client(session, max_retries=3).generate("hi")
    assert completion.text == "ok"
    assert completion.attempts == 2


def test_client_gives_up_after_max_retries():
    session = _RecordingSession([_Response(503, text="down")])
    with pytest.raises(LLMUnavailable, match="after 3 attempt"):
        _client(session, max_retries=3).generate("hi")
    assert session.calls == 3


def test_connection_errors_are_retried_then_reported():
    session = _RecordingSession([requests.ConnectionError("refused")])
    with pytest.raises(LLMUnavailable, match="refused"):
        _client(session, max_retries=2).generate("hi")
    assert session.calls == 2


def test_circuit_opens_after_repeated_failures_and_then_fails_fast():
    session = _RecordingSession([_Response(503, text="down")])
    client = _client(session, max_retries=1, circuit_breaker_threshold=3)

    for _ in range(3):
        with pytest.raises(LLMUnavailable):
            client.generate("hi")
    calls_before = session.calls

    with pytest.raises(LLMUnavailable, match="circuit is open"):
        client.generate("hi")
    assert session.calls == calls_before, "an open circuit must not reach the network"


def test_a_client_error_does_not_trip_the_circuit():
    """The server is healthy; the request was wrong. Opening the circuit here
    would take down every other caller for one malformed payload."""
    session = _RecordingSession([_Response(400, text="bad")])
    client = _client(session, max_retries=1, circuit_breaker_threshold=2)
    for _ in range(4):
        with pytest.raises(LLMError):
            client.generate("hi")
    assert session.calls == 4


def test_non_json_success_body_is_an_error_not_an_empty_answer():
    session = _RecordingSession([_Response(200, None, text="<html>proxy error</html>")])
    with pytest.raises(LLMError, match="non-JSON"):
        _client(session).generate("hi")


def test_base_url_is_configurable():
    """Old behaviour: localhost:11434 was a module constant."""
    assert OllamaClient(base_url="http://gpu-01:11434/").base_url == "http://gpu-01:11434"


def test_token_counts_are_captured():
    session = _RecordingSession([
        _Response(200, {"response": "ok", "prompt_eval_count": 120, "eval_count": 35})
    ])
    completion = _client(session).generate("hi")
    assert (completion.prompt_tokens, completion.completion_tokens) == (120, 35)


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------


def test_settings_are_overridable_by_environment(monkeypatch):
    monkeypatch.setenv("RAGAUDIT_GENERATION__MODEL_NAME", "qwen3:14b")
    monkeypatch.setenv("RAGAUDIT_RETRIEVAL__TOP_K", "42")
    from ragaudit.config import Settings

    settings = Settings()
    assert settings.generation.model_name == "qwen3:14b"
    assert settings.retrieval.top_k == 42


def test_faiss_backend_requested_without_faiss_raises_clearly(tmp_path):
    pytest.importorskip  # noqa: B018
    try:
        import faiss  # noqa: F401
    except ImportError:
        from ragaudit.store.vectors import open_index

        with pytest.raises(RuntimeError, match="faiss is not installed"):
            open_index(tmp_path, dimension=8, backend="faiss")
    else:
        pytest.skip("faiss is installed in this environment")
