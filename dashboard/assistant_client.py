"""
dashboard/assistant_client.py — adapter to Member 3's conversational assistant.

The assistant itself is Member 3's deliverable; the dashboard only CALLS it.
Two integration paths are supported, tried in order:

  1. HTTP:  ASSISTANT_URL env var — POST {"question": ...} -> {"answer": ...}
  2. Module: backend-assistant/assistant.py exposing ask(question) -> str

If neither is available we raise AssistantUnavailable and the chat page shows
an honest "not connected yet" state — never a fabricated answer.
"""

from __future__ import annotations

import importlib.util
import json
import os
import urllib.request
from pathlib import Path

import config


class AssistantUnavailable(Exception):
    """Raised when Member 3's assistant service can't be reached.

    `suggestions` carries the challenge doc's example queries so the UI can
    show what WILL be answerable once connected.
    """

    SUGGESTIONS = [
        "Show me all high-risk handling events from today's unloading.",
        "What were the three most common risky behaviours during the morning shift?",
        "Which loading bay had the highest number of risky events?",
        "Why was this event classified as high risk?",
    ]

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason
        self.suggestions = self.SUGGESTIONS


def ask(question: str) -> str:
    """Send a question to Member 3's assistant and return its answer.

    Raises AssistantUnavailable if the service isn't connected yet.
    """
    url = os.environ.get("ASSISTANT_URL", "").strip()
    if url:
        return _ask_http(url, question)
    answer = _ask_module(question)
    if answer is None:
        raise AssistantUnavailable(
            "No assistant service found. Set ASSISTANT_URL to Member 3's HTTP "
            "endpoint, or make sure backend-assistant/assistant.py (exposing "
            "ask(question) -> str) is present."
        )
    return answer


def _ask_http(url: str, question: str) -> str:
    payload = json.dumps({"question": question}).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # network/HTTP/JSON problems -> honest failure
        raise AssistantUnavailable(f"Assistant endpoint unreachable ({exc}).") from exc
    answer = body.get("answer")
    if not answer:
        raise AssistantUnavailable("Assistant endpoint returned no answer field.")
    return str(answer)


def _ask_module(question: str):
    """Try to import Member 3's assistant module and call ask(question)."""
    module_path = config.REPO_ROOT / "backend-assistant" / "assistant.py"
    if not module_path.exists():
        return None
    spec = importlib.util.spec_from_file_location("backend_assistant_service", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, "ask", None)
    if not callable(fn):
        return None
    result = fn(question)
    return str(result) if result is not None else None
