"""Unit tests for src/agent_client.py — all HTTP calls are mocked."""
from unittest.mock import MagicMock, patch

import requests

from src.agent_client import ask_agent, extract_reply

# ---------------------------------------------------------------------------
# extract_reply — pure function, no mocking needed
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
    assert extract_reply(_HAPPY_RESPONSE) == "H1 (tomato) should be dispatched first due to high urgency."


def test_parse_malformed_response_returns_none():
    assert extract_reply({}) is None


def test_parse_missing_text_key_returns_none():
    bad = {"outputs": [{"outputs": [{"results": {}}]}]}
    assert extract_reply(bad) is None


# ---------------------------------------------------------------------------
# ask_agent — mocked HTTP; returns (ok: bool, text: str)
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
        ok, reply = ask_agent("What should I dispatch first?", session_id="sess-1")
    assert ok is True
    assert reply == "H1 (tomato) should be dispatched first due to high urgency."
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "test-flow-id" in call_kwargs[0][0]
    assert call_kwargs[1]["json"]["input_value"] == "What should I dispatch first?"
    assert call_kwargs[1]["json"]["session_id"] == "sess-1"


def test_ask_agent_sends_api_key_header(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-flow-id")
    monkeypatch.setenv("LANGFLOW_API_KEY", "secret-key")
    with patch("requests.post", return_value=_make_mock_response(_HAPPY_RESPONSE)) as mock_post:
        ask_agent("hello", "sess-2")
    headers = mock_post.call_args[1]["headers"]
    assert headers.get("x-api-key") == "secret-key"


def test_ask_agent_missing_flow_id_returns_error(monkeypatch):
    monkeypatch.delenv("LANGFLOW_FLOW_ID", raising=False)
    ok, reply = ask_agent("hello", "sess-3")
    assert ok is False
    assert "LANGFLOW_FLOW_ID" in reply


def test_ask_agent_connection_error_returns_friendly_message(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-flow-id")
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("refused")):
        ok, reply = ask_agent("hello", "sess-4")
    assert ok is False
    assert "Cannot reach Langflow" in reply


def test_ask_agent_timeout_returns_friendly_message(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-flow-id")
    with patch("requests.post", side_effect=requests.exceptions.Timeout()):
        ok, reply = ask_agent("hello", "sess-5")
    assert ok is False
    assert "too long" in reply


def test_ask_agent_http_401_returns_auth_error(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-flow-id")
    with patch("requests.post", return_value=_make_mock_response({}, status_code=401)):
        ok, reply = ask_agent("hello", "sess-6")
    assert ok is False
    assert "API_KEY" in reply or "rejected" in reply


def test_ask_agent_http_404_returns_flow_error(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-flow-id")
    with patch("requests.post", return_value=_make_mock_response({}, status_code=404)):
        ok, reply = ask_agent("hello", "sess-7")
    assert ok is False
    assert "FLOW_ID" in reply or "not found" in reply.lower()


def test_ask_agent_empty_reply_returns_false(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-flow-id")
    with patch("requests.post", return_value=_make_mock_response({})):
        ok, reply = ask_agent("hello", "sess-8")
    assert ok is False
    assert reply  # some explanation string
