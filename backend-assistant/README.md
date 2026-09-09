# Member 3 — Backend, Event Store & Conversational Assistant

Implements the spec: the SQLite event store (single source of truth) and
the conversational assistant that answers supervisor questions from it,
strictly grounded in stored events.

**2026-09-09**: the schema below is the real, shared one — `event_id`,
`behaviour_type`, `risk_level`, `risk_score`, `bay`, `object_ids`,
`evidence_frame_path`, `explanation` — matching the event schema in the
repo root's `CLAUDE.md` and `shared/config.py`'s `BEHAVIOUR_TYPES`/
`RISK_LEVELS`, which is what Member 2's behaviour engine actually
produces and Member 4's dashboard actually reads. An earlier version of
this folder was built against an invented schema (`loading_bay`,
`activity`, `behaviour="no_ppe"`, `risk_level` in lowercase) that had no
connection to what the rest of the team built — rewritten to match reality
before the submission deadline. If you're picking this back up: the real
contract lives in the root `CLAUDE.md`, not in a copy inside this folder —
don't recreate a second "source of truth" doc here again.

## Files

| File                  | Purpose                                                                 |
| ---------------------- | ----------------------------------------------------------------------|
| `schema.sql`            | DDL for the `events` table. Enums mirror `shared/config.py`. |
| `store.py`              | `insert_event()` (the only write path) + read-only query functions.    |
| `tools.py`              | Function-calling tool definitions (JSON schema) + `dispatch()`, wired 1:1 onto `store.py`. |
| `assistant.py`          | The conversational assistant: Groq/Gemini function-calling loop, or offline fallback. Also exposes a module-level `ask(question) -> str` for `dashboard/assistant_client.py`'s module-integration path. |
| `offline_router.py`     | Deterministic rule-based router used when no API key is set — covers all four required query types with zero network access. |
| `seed_data.py`          | Generates realistic sample events (text mirrors `behaviour_risk_engine/explanations.py`) for local development/testing. |
| `test_assistant.py`     | Test suite: the four required query types + edge cases (empty store, invalid inserts, unknown id, ambiguous query). |

## Interface Member 2 uses

```python
from store import insert_event

# Matches Event.to_dict()'s keys exactly, so this also works directly:
#   insert_event(**event.to_dict())
event_id = insert_event(
    event_id="evt_00042",
    timestamp="2026-09-06T10:15:04Z",
    behaviour_type="dropped",
    risk_level="High",
    risk_score=0.78,
    bay="bay_1",
    object_ids=[7, 3],
    evidence_frame_path="shared/evidence/evt_00042.jpg",
    explanation="Product dropped from approximately 1 metre during unloading...",
)
```

Member 2 never touches `events.db` directly — this function is the only
write path, and it validates every field (behaviour_type/risk_level
against `shared/config.py`'s enums, risk_score range, required fields)
before inserting, raising `EventValidationError` on bad input.

## Required query types (all covered)

1. "Show me all high-risk handling events from today's unloading." → `get_high_risk_events(date, bay)` — the pilot has one bay/process, so date+bay is the real scoping available; "unloading" isn't a separate stored dimension.
2. "What were the three most common risky behaviours during the morning shift?" → `get_top_risky_behaviours(shift, limit, date)` — shift (Morning/Evening/Night, matching `dashboard/config.py`'s SHIFTS) is derived from `timestamp` at query time, not stored.
3. "Which loading bay had the highest number of risky events?" → `get_bay_with_most_risky_events(date)`
4. "Why was this event classified as high risk?" → `get_event_by_id(event_id)`

Plus `search_events(...)` as a general-purpose fallback and
`is_store_empty()` so the assistant can answer honestly when there's
nothing to query yet.

## Running

```bash
pip install -r backend-assistant-requirements.txt   # only needed for the live Groq/Gemini path — offline mode is stdlib-only

# Seed sample data for local testing
python seed_data.py --reset --n 60

# Run the test suite (required query types + edge cases)
python test_assistant.py

# Talk to the assistant interactively
export GROQ_API_KEY=...     # or GEMINI_API_KEY=...
python assistant.py

# Or, with no key set, it runs in offline (rule-based) mode automatically
python assistant.py
```

## Grounding guarantee

The LLM-backed assistant can only see data by calling a tool in
`tools.TOOLS`; every tool is a read-only, store-backed query function. The
system prompt additionally instructs the model to never state a fact that
didn't come back from a tool call, and to say so plainly when the store has
no matching data — this satisfies the spec's explicit requirement that the
assistant "must answer only from stored events, never invent information."

## Notes

- `assistant.py`'s Groq/Gemini code paths are written against their real
  OpenAI-compatible APIs but haven't been exercised with a live key yet.
  Everything else (schema, store, validation, tool wiring, and all four
  required query types) is fully tested and passing via `offline_router.py`,
  which uses the exact same `store.py`/`tools.py` code the real LLM path
  calls. Swapping in a live key is a drop-in change — no other code moves.
- No "activity" (loading/unloading/handling) or stored "shift" column —
  see `schema.sql`'s note on why, given the pilot's single-bay/single-process
  scope.
