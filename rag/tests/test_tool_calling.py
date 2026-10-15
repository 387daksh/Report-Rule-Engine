"""Tool calling in the LLM client.

The message shapes asserted here were captured from real Ollama responses
against qwen3:1.7b: arguments arrive as a dict rather than a JSON string, and
no call id is returned. Both differ from the OpenAI wire format, so anything
written against that spec would break here.
"""

from __future__ import annotations

import pytest
import requests

from ragaudit.generate.llm import LLMError, OllamaClient, ToolCall, _parse_tool_calls


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def test_parses_ollama_shape_with_dict_arguments():
    """The real qwen3:1.7b shape: arguments already a dict, no id."""
    message = {
        "content": "",
        "tool_calls": [
            {"function": {"name": "query_findings", "arguments": {"severity": "high"}}}
        ],
    }
    calls = _parse_tool_calls(message)
    assert len(calls) == 1
    assert calls[0].name == "query_findings"
    assert calls[0].arguments == {"severity": "high"}
    assert calls[0].call_id == ""


def test_parses_json_string_arguments():
    """Older builds and some proxies send arguments as a JSON string."""
    message = {"tool_calls": [{"id": "abc", "function": {"name": "f", "arguments": '{"x": 1}'}}]}
    calls = _parse_tool_calls(message)
    assert calls[0].arguments == {"x": 1}
    assert calls[0].call_id == "abc"


def test_malformed_entries_are_skipped_not_raised():
    """A bad entry must not crash the client; the loop recovers, an exception does not."""
    message = {
        "tool_calls": [
            "not a dict",
            {"no_function": True},
            {"function": {"name": ""}},
            {"function": {"name": "good", "arguments": "not json"}},
            {"function": {"name": "fine", "arguments": {"a": 1}}},
        ]
    }
    calls = _parse_tool_calls(message)
    assert [c.name for c in calls] == ["good", "fine"]
    assert calls[0].arguments == {}  # unparseable string falls back to empty


def test_no_tool_calls_returns_empty():
    assert _parse_tool_calls({"content": "hello"}) == []
    assert _parse_tool_calls({"tool_calls": None}) == []
    assert _parse_tool_calls({"tool_calls": "nonsense"}) == []


def test_tool_call_signature_is_stable_and_order_independent():
    a = ToolCall("q", {"severity": "high", "status": "open"})
    b = ToolCall("q", {"status": "open", "severity": "high"})
    assert a.signature() == b.signature()
    assert ToolCall("q", {"severity": "low"}).signature() != a.signature()


# --------------------------------------------------------------------------
# Client wiring
# --------------------------------------------------------------------------


class _Response:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = ""

    def json(self):
        return self._payload


class _CapturingSession:
    """Records the payload so we can assert what reached the wire."""

    def __init__(self, payload):
        self._payload = payload
        self.last_json = None
        self.last_timeout = None

    def post(self, url, json=None, timeout=None):
        self.last_json = json
        self.last_timeout = timeout
        return _Response(200, self._payload)

    def get(self, url, timeout=None):
        return _Response(200)

    def close(self):
        pass


def _client(session):
    return OllamaClient(session=session, backoff_base_s=0.0)


def test_chat_surfaces_tool_calls_on_completion():
    session = _CapturingSession({
        "message": {"content": "", "tool_calls": [
            {"function": {"name": "list_reports", "arguments": {}}}
        ]},
        "eval_count": 5,
    })
    completion = _client(session).chat([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])
    assert len(completion.tool_calls) == 1
    assert completion.tool_calls[0].name == "list_reports"


def test_tools_are_sent_in_the_payload():
    session = _CapturingSession({"message": {"content": "ok"}})
    tools = [{"type": "function", "function": {"name": "f", "parameters": {}}}]
    _client(session).chat([{"role": "user", "content": "x"}], tools=tools)
    assert session.last_json["tools"] == tools


def test_tools_and_format_schema_are_mutually_exclusive():
    """Ollama handles both together unreliably; the design never needs it."""
    client = _client(_CapturingSession({"message": {"content": "ok"}}))
    with pytest.raises(ValueError, match="mutually|cannot be combined"):
        client.chat([{"role": "user", "content": "x"}], tools=[{"a": 1}], format_schema={"b": 2})


def test_per_call_timeout_overrides_the_default():
    session = _CapturingSession({"message": {"content": "ok"}})
    client = OllamaClient(session=session, backoff_base_s=0.0, connect_timeout_s=5.0, timeout_s=120.0)
    client.chat([{"role": "user", "content": "x"}], timeout_s=10.0)
    # (connect, read) — the read timeout is the per-call override.
    assert session.last_timeout == (5.0, 10.0)


def test_default_timeout_used_when_no_override():
    session = _CapturingSession({"message": {"content": "ok"}})
    client = OllamaClient(session=session, backoff_base_s=0.0, connect_timeout_s=5.0, timeout_s=120.0)
    client.chat([{"role": "user", "content": "x"}])
    assert session.last_timeout == (5.0, 120.0)


def test_content_alongside_tool_calls_is_preserved():
    """Small models sometimes emit reasoning text beside a tool call."""
    session = _CapturingSession({
        "message": {"content": "Let me check.", "tool_calls": [
            {"function": {"name": "list_reports", "arguments": {}}}
        ]},
    })
    completion = _client(session).chat([{"role": "user", "content": "x"}], tools=[{"a": 1}])
    assert completion.text == "Let me check."
    assert len(completion.tool_calls) == 1
