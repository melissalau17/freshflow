"""Unit tests for src/agent_client.py — all HTTP calls are mocked."""
import os
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.agent_client import _parse_reply, ask_agent

# ---------------------------------------------------------------------------
# _parse_reply — pure function, no mocking needed
# ---------------------------------------------------------------------------

_HAPPY_RESPONSE = {
    "outputs": [
        {
            "outputs": [
                {
                    "results": {
                        "message": {
                            "text": "H1 (tomato) should be dispatched first due to high urgency."
                        }
                    }
                }
            ]
        }
    ]
}


def test_parse_happy_path():
    assert _parse_reply(_HAPPY_RESPONSE) == "H1 (tomato) should be dispatched first due to high urgency."


def test_parse_malformed_response_returns_fallback():
    result = _parse_reply({})
    assert "Unexpected response" in result


def test_parse_missing_text_key_returns_fallback():
    bad = {"outputs": [{"outputs": [{"results": {}}]}]}
    result = _parse_reply(bad)
    assert "Unexpected response" in result


# ---------------------------------------------------------------------------
# ask_agent — mocked HTTP
# ---------------------------------------------------------------------------

def _make_mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    mock = MagicMock()
    mock.ok = status_code < 400
    mock.status_code = status_code
    mock.json.return_value = json_data
    mock.text = str(json_data)
    return mock


def test_ask_agent_happy_path(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-flow-id")
    monkeypatch.delenv("LANGFLOW_API_KEY", raising=False)
    with patch("requests.post", return_value=_make_mock_response(_HAPPY_RESPONSE)) as mock_post:
        result = ask_agent("What should I dispatch first?", session_id="sess-1")
    assert result == "H1 (tomato) should be dispatched first due to high urgency."
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "test-flow-id" in call_kwargs[0][0]          # URL contains flow id
    assert call_kwargs[1]["json"]["input_value"] == "What should I dispatch first?"
    assert call_kwargs[1]["json"]["session_id"] == "sess-1"


def test_ask_agent_sends_api_key_header(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-flow-id")
    monkeypatch.setenv("LANGFLOW_API_KEY", "secret-key")
    with patch("requests.post", return_value=_make_mock_response(_HAPPY_RESPONSE)):
        ask_agent("hello", "sess-2")
    with patch("requests.post", return_value=_make_mock_response(_HAPPY_RESPONSE)) as mock_post:
        ask_agent("hello", "sess-2")
    headers = mock_post.call_args[1]["headers"]
    assert headers.get("x-api-key") == "secret-key"


def test_ask_agent_missing_flow_id_returns_error(monkeypatch):
    monkeypatch.delenv("LANGFLOW_FLOW_ID", raising=False)
    result = ask_agent("hello", "sess-3")
    assert "LANGFLOW_FLOW_ID" in result


def test_ask_agent_connection_error_returns_friendly_message(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-flow-id")
    with patch("requests.post", side_effect=requests.ConnectionError("refused")):
        result = ask_agent("hello", "sess-4")
    assert "Could not reach Langflow" in result


def test_ask_agent_timeout_returns_friendly_message(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-flow-id")
    with patch("requests.post", side_effect=requests.Timeout()):
        result = ask_agent("hello", "sess-5")
    assert "timed out" in result


def test_ask_agent_http_error_returns_status(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-flow-id")
    with patch("requests.post", return_value=_make_mock_response({}, status_code=404)):
        result = ask_agent("hello", "sess-6")
    assert "404" in result
