"""
Where finished Event objects go.

Per the root CLAUDE.md, Member 2 must call Member 3's insert function rather
than writing to the DB directly — but that function isn't published yet
(backend-assistant is still just a requirements.txt as of 2026-09-05).
Until it lands, events are appended to a local JSONL file so this module is
fully runnable standalone.

`_write_via_backend` guesses at Member 3's eventual module path/signature —
it's wrapped in try/except so a wrong guess just falls back to the local
log rather than crashing. Once Member 3 publishes the real insert function,
update the import here (nothing in engine.py or the detectors needs to
change).
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Event

LOCAL_LOG_PATH = Path(__file__).resolve().parent.parent / "output" / "events_log.jsonl"


def _write_via_backend(event: Event) -> bool:
    try:
        from backend_assistant.db import insert_event  # published by Member 3 — path is a guess for now
    except ImportError:
        return False
    insert_event(event.to_dict())
    return True


def _write_local(event: Event) -> None:
    LOCAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCAL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event.to_dict()) + "\n")


def default_event_sink(event: Event) -> None:
    if not _write_via_backend(event):
        _write_local(event)
