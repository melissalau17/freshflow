"""HTTP client for the FreshFlow AI agent.

Supports both runtimes automatically:
  - lfx serve  (Render):  POST /flows/{id}/run        → {"result": str, "success": bool}
  - Langflow   (local):   POST /api/v1/run/{id}        → {"outputs": [...]}

Env vars:
    LANGFLOW_URL      Base URL (default: http://localhost:7862)
    LANGFLOW_FLOW_ID  Flow UUID (required)
    LANGFLOW_API_KEY  Sent as x-api-key header when set
"""
import os

import requests


def agent_configured() -> bool:
    return bool(os.environ.get("LANGFLOW_FLOW_ID"))


def extract_reply(data: dict) -> str | None:
    """Pull reply text from either lfx-serve or Langflow response envelope."""
    # ── lfx serve: {"result": "...", "success": bool} ──────────────────────
    if "result" in data and isinstance(data["result"], str) and data["result"].strip():
        return data["result"]

    # ── Langflow: outputs[0].outputs[0].results.message.text ───────────────
    try:
        return data["outputs"][0]["outputs"][0]["results"]["message"]["text"]
    except (KeyError, IndexError, TypeError):
        pass

    # ── recursive fallback: first non-empty "text" anywhere in the tree ────
    def find(node):
        if isinstance(node, dict):
            if isinstance(node.get("text"), str) and node["text"].strip():
                return node["text"]
            for v in node.values():
                r = find(v)
                if r:
                    return r
        elif isinstance(node, list):
            for v in node:
                r = find(v)
                if r:
                    return r
        return None

    return find(data)


def _endpoints(base: str, flow_id: str) -> list[str]:
    """Return candidate POST URLs in preference order (lfx serve first)."""
    return [
        f"{base}/flows/{flow_id}/run",       # lfx serve (Render)
        f"{base}/api/v1/run/{flow_id}",       # full Langflow (local)
    ]


def ask_agent(message: str, session_id: str, timeout: int = 60) -> tuple[bool, str]:
    """Call the agent. Returns (ok, reply_text). Never raises."""
    base = os.environ.get("LANGFLOW_URL", "http://localhost:7862").rstrip("/")
    flow_id = os.environ.get("LANGFLOW_FLOW_ID")
    if not flow_id:
        return False, "The agent is not configured. Set LANGFLOW_FLOW_ID (see README)."

    headers: dict[str, str] = {"Content-Type": "application/json"}
    api_key = os.environ.get("LANGFLOW_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    payload = {
        "input_value": message,
        "input_type": "chat",
        "output_type": "chat",
        "session_id": session_id,
    }

    last_error = ""
    for url in _endpoints(base, flow_id):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        except requests.exceptions.ConnectionError:
            return False, (
                f"Cannot reach the agent server at {base}. "
                "Check that it is running and that LANGFLOW_URL is correct."
            )
        except requests.exceptions.Timeout:
            return False, "The agent took too long to respond. Try again."
        except requests.exceptions.RequestException as exc:
            return False, f"Request error: {exc}"

        if resp.status_code in (401, 403):
            return False, "The server rejected the request. Check LANGFLOW_API_KEY."
        if resp.status_code == 404:
            # This endpoint doesn't exist on this runtime — try the next one
            last_error = (
                f"Flow not found at {url}. "
                "Check LANGFLOW_FLOW_ID and LANGFLOW_URL."
            )
            continue
        if not resp.ok:
            return False, f"The server returned an error ({resp.status_code}: {resp.text[:200]})."

        # Parse response
        try:
            data = resp.json()
        except ValueError:
            return False, f"Response was not valid JSON. Start of response: {resp.text[:200]}"

        # lfx serve reports failures inside a successful HTTP 200
        if isinstance(data, dict) and data.get("success") is False:
            msg = data.get("result") or data.get("error") or "The agent reported a failure."
            return False, f"Agent error: {msg}"

        text = extract_reply(data)
        if text:
            return True, text
        return False, (
            f"The response format was not recognised. "
            f"Start of response: {str(data)[:300]}"
        )

    return False, last_error
