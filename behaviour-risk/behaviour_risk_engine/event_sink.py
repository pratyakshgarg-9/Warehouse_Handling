"""
Where finished Event objects go.

Per the root CLAUDE.md, Member 2 must call Member 3's insert function
rather than writing to the DB directly. Wired up 2026-09-09 once Member
3's real store.py landed (rewritten that day against the actual shared
schema — see backend-assistant/README.md for that history).

`backend-assistant` has a hyphen, so it isn't an importable Python package
name — loaded via importlib from its file path instead, same pattern
dashboard/assistant_client.py uses for assistant.py. Falls back to a local
JSONL log if that module can't be loaded (e.g. running this module in
isolation without the full repo checked out) so this module stays
runnable standalone either way.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

from .models import Event

LOCAL_LOG_PATH = Path(__file__).resolve().parent.parent / "output" / "events_log.jsonl"
_STORE_MODULE_PATH = Path(__file__).resolve().parent.parent.parent / "backend-assistant" / "store.py"

_store_module = None


def _load_store():
    global _store_module
    if _store_module is not None:
        return _store_module
    if not _STORE_MODULE_PATH.exists():
        return None
    spec = importlib.util.spec_from_file_location("backend_assistant_store", _STORE_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # store.py's @dataclass needs this registered before exec — it
    spec.loader.exec_module(module)  # looks itself up via sys.modules[cls.__module__] at class-definition time
    _store_module = module
    return module


def _write_via_backend(event: Event) -> bool:
    store = _load_store()
    if store is None:
        return False
    store.insert_event(**event.to_dict())  # Event.to_dict()'s keys match insert_event's kwargs exactly
    return True


def _write_local(event: Event) -> None:
    LOCAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCAL_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(event.to_dict()) + "\n")


def default_event_sink(event: Event) -> None:
    if not _write_via_backend(event):
        _write_local(event)
