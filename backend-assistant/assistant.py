"""
assistant.py — the conversational assistant that answers supervisor
questions strictly from the event store.

Two providers are supported, both free-tier and both OpenAI-style
function-calling compatible:

  - Groq   (llama-3.x models, via the OpenAI-compatible /openai/v1 endpoint)
  - Gemini (gemini-1.5/2.x, via its OpenAI-compatible endpoint)

Set GROQ_API_KEY or GEMINI_API_KEY as an environment variable to use the
corresponding provider. If neither is set, the assistant runs in offline
mode using a small rule-based router (see `offline_router.py`) so the four
required query types can be exercised end-to-end without any network
access or API key — this is what test_assistant.py uses.

Grounding rule (hard requirement from the spec): the model can only see
data by calling a tool in tools.TOOLS, each of which is a read-only,
store-backed query. The system prompt additionally instructs the model to
never state a fact that didn't come back from a tool call, and to say so
plainly when the store has no matching data.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

# dashboard/assistant_client.py loads this file via importlib from a
# different directory (dashboard/), which doesn't add this file's own
# directory to sys.path the way running `python assistant.py` directly
# would — so `import store`/`import tools` fail with "No module named
# 'store'" unless this is here first. Confirmed happening 2026-09-09
# when actually running the dashboard's Assistant page against this file.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import store
import tools

SYSTEM_PROMPT = """You are a safety-operations assistant for a warehouse \
supervisor. You answer questions ONLY using the tools available to you, \
which read from the event store. You must never invent, assume, or recall \
from general knowledge any event, count, bay name, behaviour, or \
explanation that a tool call did not actually return.

Rules:
- For any question about events, counts, or risk reasons, call a tool \
before answering. Do not answer from memory of earlier turns if a fresh \
tool call would give a more accurate answer.
- If a tool returns an empty list or None, say plainly that there is no \
matching data in the event store — do not fill the gap with a plausible \
guess.
- If a question is ambiguous (e.g. "today" when no date is given, or \
"risky" without specifying which risk level), state the assumption you're \
making before answering, or ask a brief clarifying question if the \
ambiguity is too large to guess safely.
- Keep answers concise and cite concrete numbers/event_ids from the tool results.
"""


def _get_provider() -> str:
    if os.environ.get("GROQ_API_KEY"):
        return "groq"
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini"
    return "offline"


class Assistant:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None):
        self.provider = provider or _get_provider()
        self.history: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

        if self.provider == "groq":
            from openai import OpenAI  # groq exposes an OpenAI-compatible API

            self.client = OpenAI(
                api_key=os.environ["GROQ_API_KEY"],
                base_url="https://api.groq.com/openai/v1",
            )
            self.model = model or "llama-3.3-70b-versatile"
        elif self.provider == "gemini":
            from openai import OpenAI  # Gemini also exposes an OpenAI-compatible endpoint

            self.client = OpenAI(
                api_key=os.environ["GEMINI_API_KEY"],
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            )
            self.model = model or "gemini-2.0-flash"
        elif self.provider == "offline":
            self.client = None
            self.model = None
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def ask(self, question: str) -> str:
        if self.provider == "offline":
            from offline_router import answer_offline

            return answer_offline(question)
        return self._ask_llm(question)

    def _ask_llm(self, question: str) -> str:
        self.history.append({"role": "user", "content": question})

        # Function-calling loop: keep resolving tool calls until the model
        # returns a plain text answer, capped to avoid runaway loops.
        for _ in range(5):
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.history,
                tools=tools.TOOLS,
                tool_choice="auto",
            )
            message = response.choices[0].message
            self.history.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                return message.content or ""

            for call in message.tool_calls:
                try:
                    args = json.loads(call.function.arguments or "{}")
                    result = tools.dispatch(call.function.name, args)
                    content = json.dumps(result)
                except Exception as exc:  # surfaced back to the model, not swallowed
                    content = json.dumps({"error": str(exc)})
                self.history.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": content,
                    }
                )

        return (
            "I wasn't able to resolve that after several tool calls — "
            "could you rephrase or narrow the question?"
        )


# --------------------------------------------------------------------------
# Module-level entry point — this is what dashboard/assistant_client.py
# looks for (`ask(question) -> str`) when ASSISTANT_URL isn't set. Reuses
# one Assistant instance so conversation history persists across calls
# within a single dashboard process, rather than reconnecting per question.
# --------------------------------------------------------------------------

_shared_assistant: Optional[Assistant] = None


def ask(question: str) -> str:
    global _shared_assistant
    if _shared_assistant is None:
        _shared_assistant = Assistant()
    return _shared_assistant.ask(question)


if __name__ == "__main__":
    store.init_db()
    assistant = Assistant()
    print(f"Assistant ready (provider={assistant.provider}). Type 'quit' to exit.")
    while True:
        q = input("\nSupervisor> ").strip()
        if q.lower() in {"quit", "exit"}:
            break
        if not q:
            continue
        print(assistant.ask(q))
