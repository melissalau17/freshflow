"""Unit tests for src/agent_client.py — all HTTP calls are mocked."""
from unittest.mock import MagicMock, patch

import requests

from src.agent_client import ask_agent, extract_reply

# ---------------------------------------------------------------------------
# extract_reply
# ---------------------------------------------------------------------------

_LFX_RESPONSE = {"result": "Dispatch H1 first.", "success": True}

_LANGFLOW_RESPONSE = {
    "outputs": [{"outputs": [{"results": {"message": {"text": "Dispatch H1 first."}}}]}]
}


def test_extract_reply_lfx_format():
    assert extract_reply(_LFX_RESPONSE) == "Dispatch H1 first."


def test_extract_reply_langflow_format():
    assert extract_reply(_LANGFLOW_RESPONSE) == "Dispatch H1 first."


def test_extract_reply_malformed_returns_none():
    assert extract_reply({}) is None


def test_extract_reply_lfx_failure_not_extracted():
    # success=False result is handled by ask_agent, not extract_reply
    # extract_reply should still return the text (caller checks success flag)
    data = {"result": "Some error text", "success": False}
    assert extract_reply(data) == "Some error text"


# ---------------------------------------------------------------------------
# ask_agent — mocked HTTP
# ---------------------------------------------------------------------------

def _mock_resp(json_data, status_code=200):
    m = MagicMock()
    m.ok = status_code < 400
    m.status_code = status_code
    m.json.return_value = json_data
    m.text = str(json_data)
    return m


def test_ask_agent_lfx_serve_happy_path(monkeypatch):
    """lfx serve endpoint (/flows/{id}/run) succeeds on first try."""
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-id")
    monkeypatch.delenv("LANGFLOW_API_KEY", raising=False)
    with patch("requests.post", return_value=_mock_resp(_LFX_RESPONSE)) as mock_post:
        ok, reply = ask_agent("Run demo", "sess-1")
    assert ok is True
    assert reply == "Dispatch H1 first."
    called_url = mock_post.call_args[0][0]
    assert "/flows/test-id/run" in called_url


def test_ask_agent_langflow_fallback(monkeypatch):
    """Falls back to /api/v1/run/{id} when lfx endpoint returns 404."""
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-id")
    monkeypatch.delenv("LANGFLOW_API_KEY", raising=False)
    responses = [_mock_resp({}, 404), _mock_resp(_LANGFLOW_RESPONSE, 200)]
    with patch("requests.post", side_effect=responses) as mock_post:
        ok, reply = ask_agent("Run demo", "sess-2")
    assert ok is True
    assert reply == "Dispatch H1 first."
    assert mock_post.call_count == 2
    assert "/api/v1/run/test-id" in mock_post.call_args_list[1][0][0]


def test_ask_agent_lfx_success_false_returns_error(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-id")
    with patch("requests.post", return_value=_mock_resp({"result": "WatsonX key missing", "success": False})):
        ok, reply = ask_agent("ping", "sess-3")
    assert ok is False
    assert "WatsonX key missing" in reply


def test_ask_agent_sends_api_key_header(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-id")
    monkeypatch.setenv("LANGFLOW_API_KEY", "sk-secret")
    with patch("requests.post", return_value=_mock_resp(_LFX_RESPONSE)) as mock_post:
        ask_agent("hello", "sess-4")
    assert mock_post.call_args[1]["headers"]["x-api-key"] == "sk-secret"


def test_ask_agent_missing_flow_id(monkeypatch):
    monkeypatch.delenv("LANGFLOW_FLOW_ID", raising=False)
    ok, reply = ask_agent("hello", "sess-5")
    assert ok is False
    assert "LANGFLOW_FLOW_ID" in reply


def test_ask_agent_connection_error(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-id")
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError()):
        ok, reply = ask_agent("hello", "sess-6")
    assert ok is False
    assert "Cannot reach" in reply


def test_ask_agent_timeout(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-id")
    with patch("requests.post", side_effect=requests.exceptions.Timeout()):
        ok, reply = ask_agent("hello", "sess-7")
    assert ok is False
    assert "too long" in reply


def test_ask_agent_401(monkeypatch):
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-id")
    with patch("requests.post", return_value=_mock_resp({}, 401)):
        ok, reply = ask_agent("hello", "sess-8")
    assert ok is False
    assert "API_KEY" in reply or "rejected" in reply


def test_ask_agent_both_endpoints_404(monkeypatch):
    """Both endpoints 404 → returns last_error."""
    monkeypatch.setenv("LANGFLOW_FLOW_ID", "test-id")
    with patch("requests.post", return_value=_mock_resp({}, 404)):
        ok, reply = ask_agent("hello", "sess-9")
    assert ok is False
    assert "LANGFLOW_FLOW_ID" in reply or "LANGFLOW_URL" in reply
