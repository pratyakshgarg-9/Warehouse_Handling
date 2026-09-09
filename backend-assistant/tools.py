"""
tools.py — function-calling tool definitions for the conversational assistant.

Each tool maps 1:1 onto a read-only query function in store.py. The LLM
never gets raw DB access; it can only call these, so it can never answer
beyond what's actually stored. `dispatch()` is the single place that turns
a tool call name + args into a store.py call, so it's easy to audit that
every tool the model can invoke is read-only and store-backed.
"""

from __future__ import annotations

from typing import Any

import store

# JSON-schema tool definitions, written in the OpenAI/Groq "tools" format.
# Gemini's function-calling schema is structurally the same (name /
# description / parameters as JSON Schema), so this list is reused verbatim
# for both providers in assistant.py.
_SHIFT_NAMES = [name for name, _, _ in store.SHIFT_WINDOWS]

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "get_high_risk_events",
            "description": (
                "Get all High/Critical-risk events, optionally filtered by "
                "date and bay. Use for questions like 'show me all "
                "high-risk handling events from today's unloading' — the "
                "pilot has one bay and one process, so date+bay is the "
                "real scoping available."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Filter to this date, format YYYY-MM-DD. Omit for all dates.",
                    },
                    "bay": {
                        "type": "string",
                        "description": "Filter to this bay, e.g. 'bay_1'. Omit for all bays.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_risky_behaviours",
            "description": (
                "Get the most common behaviour_types among risky "
                "(Medium/High/Critical) events, optionally scoped to a "
                "shift and/or date, ranked by frequency. Use for questions "
                "like 'what were the three most common risky behaviours "
                "during the morning shift'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "shift": {
                        "type": "string",
                        "enum": _SHIFT_NAMES,
                        "description": "Restrict to this shift. Omit for all shifts.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Filter to this date, format YYYY-MM-DD. Omit for all dates.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "How many top behaviours to return. Defaults to 3.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_bay_with_most_risky_events",
            "description": (
                "Get the bay with the highest count of risky "
                "(Medium/High/Critical) events, optionally scoped to a "
                "date. Use for questions like 'which loading bay had the "
                "highest number of risky events'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Filter to this date, format YYYY-MM-DD. Omit for all dates.",
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_event_by_id",
            "description": (
                "Get full details for one event by its event_id, including "
                "its explanation. Use for questions like 'why was this "
                "event classified as high risk' when an event_id is known "
                "or was just mentioned in conversation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The event's id, e.g. 'evt_00042'.",
                    }
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_events",
            "description": (
                "General-purpose fallback search over events, filterable by "
                "any combination of date, shift, bay, risk_level, "
                "behaviour_type. Use this when a question doesn't map "
                "cleanly onto the other, more specific tools."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "shift": {"type": "string", "enum": _SHIFT_NAMES},
                    "bay": {"type": "string"},
                    "risk_level": {"type": "string", "enum": list(store.VALID_RISK_LEVELS)},
                    "behaviour_type": {"type": "string", "enum": list(store.VALID_BEHAVIOUR_TYPES)},
                    "limit": {"type": "integer", "description": "Max rows to return, defaults to 100."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "is_store_empty",
            "description": (
                "Check whether the event store currently has zero events. "
                "Call this first if you suspect there may be no data yet, "
                "so you can tell the user clearly rather than guessing."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def dispatch(name: str, args: dict[str, Any]) -> Any:
    """Execute a tool call by name against store.py. Raises KeyError for an
    unknown tool name so misuse fails loudly rather than silently."""
    handlers = {
        "get_high_risk_events": store.get_high_risk_events,
        "get_top_risky_behaviours": store.get_top_risky_behaviours,
        "get_bay_with_most_risky_events": store.get_bay_with_most_risky_events,
        "get_event_by_id": store.get_event_by_id,
        "search_events": store.search_events,
        "is_store_empty": store.is_store_empty,
    }
    if name not in handlers:
        raise KeyError(f"Unknown tool: {name}")
    return handlers[name](**args)
