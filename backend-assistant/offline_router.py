"""
offline_router.py — a small rule-based stand-in for the LLM function-calling
loop, used when no GROQ_API_KEY / GEMINI_API_KEY is set.

This is NOT meant to replace the real assistant — it exists so that:
  1. store.py + tools.py can be exercised end-to-end without any API key or
     network access.
  2. test_assistant.py has something deterministic to assert against.
  3. There's a working assistant for tomorrow's demo/submission even if no
     API key is configured in time.

It covers exactly the four required query types from the spec, plus a
"why" fallback for arbitrary event ids, plus an honest "no data" response
when the store is empty. Everything it says still comes only from store.py.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import store


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _format_events(events: list[dict]) -> str:
    if not events:
        return "No matching events found in the event store."
    lines = [
        f"{e['event_id']} [{e['timestamp']}] bay={e['bay']} "
        f"behaviour={e['behaviour_type']} risk={e['risk_level']}"
        for e in events
    ]
    return f"Found {len(events)} event(s):\n" + "\n".join(lines)


def _find_shift(q: str) -> str | None:
    for name, _, _ in store.SHIFT_WINDOWS:
        if re.search(rf"\b{name.lower()}\b", q):
            return name
    return None


def answer_offline(question: str) -> str:
    q = question.lower()

    if store.is_store_empty():
        return (
            "The event store currently has no events logged yet, so I have "
            "nothing to answer this from."
        )

    # "Why was this event classified as high risk?" — checked before the
    # general high-risk branch below, since this question also contains the
    # words "high risk" and would otherwise be misrouted.
    if "why" in q and re.search(r"evt_\d+|#?\d+", q):
        m = re.search(r"(evt_\d+)", question) or re.search(r"#?(\d+)", q)
        event_id = m.group(1) if m.group(1).startswith("evt_") else f"evt_{int(m.group(1)):05d}"
        event = store.get_event_by_id(event_id)
        if event is None:
            return f"I couldn't find an event with id {event_id} in the store."
        return (
            f"Event {event['event_id']} ({event['behaviour_type']} at "
            f"{event['bay']}, {event['timestamp']}) was classified as "
            f"{event['risk_level']} risk because: {event['explanation']}"
        )

    # "Show me all high-risk handling events from today's unloading."
    if "high-risk" in q or "high risk" in q:
        date = _today() if "today" in q else None
        events = store.get_high_risk_events(date=date)
        scope_str = f" (today, {date})" if date else ""
        return f"High-risk events{scope_str}:\n" + _format_events(events)

    # "What were the three most common risky behaviours during the morning shift?"
    if "risky behaviour" in q or "risky behavior" in q or "common" in q:
        shift = _find_shift(q)
        date = _today() if "today" in q else None
        m = re.search(r"\b(\d+)\b", q)
        limit = int(m.group(1)) if m else 3
        results = store.get_top_risky_behaviours(shift=shift, limit=limit, date=date)
        scope = f" during the {shift} shift" if shift else ""
        if not results:
            return f"No risky behaviours found{scope}."
        lines = [f"{i+1}. {r['behaviour_type']} ({r['count']} occurrences)" for i, r in enumerate(results)]
        return f"Top {len(results)} risky behaviours{scope}:\n" + "\n".join(lines)

    # "Which loading bay had the highest number of risky events?"
    if "loading bay" in q or "which bay" in q:
        date = _today() if "today" in q else None
        result = store.get_bay_with_most_risky_events(date=date)
        if result is None:
            return "No risky events found, so no bay stands out."
        scope = " today" if date else ""
        return (
            f"{result['bay']} had the highest number of risky "
            f"events{scope}, with {result['count']} event(s)."
        )

    # "Why was this event classified as high risk?" with no id at all —
    # ask for clarification rather than guessing which event is meant.
    if "why" in q:
        return (
            "Which event do you mean? Please give me the event id "
            "(e.g. 'why was evt_00012 classified as high risk?')."
        )

    # Fallback: general filtered search using whatever recognizable filters
    # appear in the question, so ad-hoc queries still get a grounded answer.
    kwargs = {}
    shift = _find_shift(q)
    if shift:
        kwargs["shift"] = shift
    for level in store.VALID_RISK_LEVELS:
        if re.search(rf"\b{level.lower()}\b", q):
            kwargs["risk_level"] = level
    if "today" in q:
        kwargs["date"] = _today()

    events = store.search_events(**kwargs, limit=20)
    if not events and not kwargs:
        return (
            "I'm not sure how to map that question to the event store yet — "
            "try asking about high-risk events, common risky behaviours, "
            "which bay has the most risky events, or why a specific event "
            "(by event_id) was classified as it was."
        )
    return _format_events(events)
