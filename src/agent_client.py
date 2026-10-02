"""Thin client for the Langflow flow (the FreshFlow AI agent).

Env vars: LANGFLOW_URL (default http://localhost:7862), LANGFLOW_FLOW_ID, LANGFLOW_API_KEY (optional).
Never raises: returns (ok, text) so the dashboard keeps working when Langflow is down.
"""
import os

import requests


def agent_configured():
    return bool(os.environ.get("LANGFLOW_FLOW_ID"))


def extract_reply(data):
    """Pull the agent's text out of a Langflow /run response."""
    try:
        return data["outputs"][0]["outputs"][0]["results"]["message"]["text"]
    except (KeyError, IndexError, TypeError):
        pass

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


def ask_agent(message, session_id, timeout=60):
    base = os.environ.get("LANGFLOW_URL", "http://localhost:7862").rstrip("/")
    flow_id = os.environ.get("LANGFLOW_FLOW_ID")
    if not flow_id:
        return False, "The agent is not configured. Set LANGFLOW_FLOW_ID (see README)."
    headers = {"Content-Type": "application/json"}
    if os.environ.get("LANGFLOW_API_KEY"):
        headers["x-api-key"] = os.environ["LANGFLOW_API_KEY"]
    payload = {"input_value": message, "input_type": "chat", "output_type": "chat", "session_id": session_id}
    try:
        resp = requests.post(f"{base}/api/v1/run/{flow_id}", json=payload, headers=headers, timeout=timeout)
    except requests.exceptions.ConnectionError:
        return False, f"Cannot reach Langflow at {base}. Check that it is running."
    except requests.exceptions.Timeout:
        return False, "The agent took too long to respond. Try again."
    if resp.status_code in (401, 403):
        return False, "Langflow rejected the request. Check LANGFLOW_API_KEY."
    if resp.status_code == 404:
        return False, "Flow not found. Check LANGFLOW_FLOW_ID."
    if not resp.ok:
        return False, f"Langflow returned an error ({resp.status_code})."
    try:
        text = extract_reply(resp.json())
    except ValueError:
        text = None
    return (True, text) if text else (False, "The agent returned no readable answer.")