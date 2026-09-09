"""
store.py — the single shared source of truth for the SQLite event store.

Member 2's behaviour engine calls `insert_event()` to log events; nobody
writes to the DB directly. Member 4's dashboard and the conversational
assistant both read via the query functions here (or read-only SQL
against the same schema).

Schema is defined in schema.sql. Enums (BEHAVIOUR_TYPES, RISK_LEVELS) are
imported from shared/config.py rather than redefined here, so this module
can never drift out of sync with the one file everyone else also imports
from.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
for _p in (str(_REPO_ROOT), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.config import BEHAVIOUR_TYPES, RISK_LEVELS  # noqa: E402

DB_PATH = _HERE / "events.db"
SCHEMA_PATH = _HERE / "schema.sql"

VALID_BEHAVIOUR_TYPES = tuple(BEHAVIOUR_TYPES)
VALID_RISK_LEVELS = tuple(RISK_LEVELS)

# Matches dashboard/config.py's SHIFTS exactly, so both modules group
# shifts identically. Not a stored column — derived from `timestamp` at
# query time.
SHIFT_WINDOWS = (
    ("Morning", 6, 14),
    ("Evening", 14, 22),
    ("Night", 22, 6),
)


class EventValidationError(ValueError):
    """Raised when an event payload doesn't satisfy the schema contract."""


@dataclass
class Event:
    event_id: str
    timestamp: str
    behaviour_type: str
    risk_level: str
    risk_score: float
    bay: str
    object_ids: list
    evidence_frame_path: str
    explanation: str
    created_at: str = ""

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Event":
        return cls(
            event_id=row["event_id"],
            timestamp=row["timestamp"],
            behaviour_type=row["behaviour_type"],
            risk_level=row["risk_level"],
            risk_score=row["risk_score"],
            bay=row["bay"],
            object_ids=json.loads(row["object_ids"]),
            evidence_frame_path=row["evidence_frame_path"],
            explanation=row["explanation"],
            created_at=row["created_at"],
        )

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "behaviour_type": self.behaviour_type,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "bay": self.bay,
            "object_ids": self.object_ids,
            "evidence_frame_path": self.evidence_frame_path,
            "explanation": self.explanation,
            "created_at": self.created_at,
        }


def shift_for_hour(hour: int) -> str:
    """Same Morning/Evening/Night, 6/14/22 boundaries as
    dashboard/config.py's SHIFTS, so both modules group shifts identically."""
    for name, start, end in SHIFT_WINDOWS:
        if start < end:
            if start <= hour < end:
                return name
        else:  # wraps midnight (Night: 22-06)
            if hour >= start or hour < end:
                return name
    return "Night"  # unreachable given the windows above cover all 24 hours


def init_db(db_path: Optional[Path] = None) -> None:
    """Create the events table (and indexes) if it doesn't exist yet."""
    db_path = db_path or DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    ddl = SCHEMA_PATH.read_text()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(ddl)


@contextmanager
def _connect(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    db_path = db_path or DB_PATH
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_event(
    *,
    event_id: str,
    timestamp: str,
    behaviour_type: str,
    risk_level: str,
    risk_score: float,
    bay: str,
    object_ids: list,
    evidence_frame_path: str,
    explanation: str,
    db_path: Optional[Path] = None,
) -> str:
    """The single write interface into the event store. Member 2's engine
    calls this for every produced event (matches Event.to_dict()'s keys
    exactly, so `insert_event(**event.to_dict())` works directly) —
    nothing else writes to events.db.

    Returns:
        The event_id that was inserted (unchanged — this function doesn't
        generate ids, Member 2's engine already did).

    Raises:
        EventValidationError: if any field fails validation.
    """
    if not event_id:
        raise EventValidationError("event_id is required")
    if behaviour_type not in VALID_BEHAVIOUR_TYPES:
        raise EventValidationError(
            f"behaviour_type must be one of {VALID_BEHAVIOUR_TYPES}, got {behaviour_type!r}"
        )
    if risk_level not in VALID_RISK_LEVELS:
        raise EventValidationError(
            f"risk_level must be one of {VALID_RISK_LEVELS}, got {risk_level!r}"
        )
    if not (0.0 <= risk_score <= 1.0):
        raise EventValidationError(f"risk_score must be in [0.0, 1.0], got {risk_score!r}")
    if not bay:
        raise EventValidationError("bay is required")
    if not object_ids:
        raise EventValidationError("object_ids must be a non-empty list")
    if not evidence_frame_path:
        raise EventValidationError("evidence_frame_path is required")
    if not explanation:
        raise EventValidationError("explanation is required")

    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EventValidationError(f"timestamp must be ISO-8601, got {timestamp!r}") from exc

    created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with _connect(db_path) as conn:
        try:
            conn.execute(
                """
                INSERT INTO events (
                    event_id, timestamp, behaviour_type, risk_level, risk_score,
                    bay, object_ids, evidence_frame_path, explanation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    timestamp,
                    behaviour_type,
                    risk_level,
                    risk_score,
                    bay,
                    json.dumps(object_ids),
                    evidence_frame_path,
                    explanation,
                    created_at,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise EventValidationError(f"event_id {event_id!r} already exists") from exc
        return event_id


# --------------------------------------------------------------------------
# Query functions — used by both the dashboard (Member 4) and the
# conversational assistant's function-calling tools.
# --------------------------------------------------------------------------


def get_high_risk_events(
    date: Optional[str] = None,
    bay: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """High/Critical-risk events, optionally filtered by date (YYYY-MM-DD)
    and bay. Answers: "Show me all high-risk handling events from today's
    unloading" — the pilot has one bay and one process, so "unloading" and
    "handling" aren't separate filterable dimensions here; date + bay cover
    the same real scoping.
    """
    query = "SELECT * FROM events WHERE risk_level IN ('High', 'Critical')"
    params: list[Any] = []
    if date:
        query += " AND substr(timestamp, 1, 10) = ?"
        params.append(date)
    if bay:
        query += " AND bay = ?"
        params.append(bay)
    query += " ORDER BY timestamp DESC"

    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [Event.from_row(r).to_dict() for r in rows]


def get_top_risky_behaviours(
    shift: Optional[str] = None,
    limit: int = 3,
    db_path: Optional[Path] = None,
    date: Optional[str] = None,
) -> list[dict]:
    """Most common behaviour_types among risky (Medium/High/Critical)
    events, optionally scoped to a shift and/or date. Answers: "What were
    the three most common risky behaviours during the morning shift?"
    """
    if shift is not None and shift not in {name for name, _, _ in SHIFT_WINDOWS}:
        valid = tuple(name for name, _, _ in SHIFT_WINDOWS)
        raise EventValidationError(f"shift must be one of {valid}, got {shift!r}")

    query = "SELECT behaviour_type, timestamp FROM events WHERE risk_level IN ('Medium', 'High', 'Critical')"
    params: list[Any] = []
    if date:
        query += " AND substr(timestamp, 1, 10) = ?"
        params.append(date)

    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()

    counts: dict[str, int] = {}
    for row in rows:
        if shift:
            hour = int(row["timestamp"][11:13])
            if shift_for_hour(hour) != shift:
                continue
        counts[row["behaviour_type"]] = counts.get(row["behaviour_type"], 0) + 1

    ranked = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    return [{"behaviour_type": name, "count": count} for name, count in ranked]


def get_bay_with_most_risky_events(
    date: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Optional[dict]:
    """The bay with the highest count of risky (Medium/High/Critical)
    events, optionally scoped to a date. Answers: "Which loading bay had
    the highest number of risky events?"
    """
    query = "SELECT bay, COUNT(*) AS count FROM events WHERE risk_level IN ('Medium', 'High', 'Critical')"
    params: list[Any] = []
    if date:
        query += " AND substr(timestamp, 1, 10) = ?"
        params.append(date)
    query += " GROUP BY bay ORDER BY count DESC LIMIT 1"

    with _connect(db_path) as conn:
        row = conn.execute(query, params).fetchone()
    if row is None:
        return None
    return {"bay": row["bay"], "count": row["count"]}


def get_event_by_id(event_id: str, db_path: Optional[Path] = None) -> Optional[dict]:
    """Fetch one event by its event_id, including its explanation. Answers:
    "Why was this event classified as high risk?"
    """
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM events WHERE event_id = ?", (event_id,)).fetchone()
    if row is None:
        return None
    return Event.from_row(row).to_dict()


def search_events(
    date: Optional[str] = None,
    shift: Optional[str] = None,
    bay: Optional[str] = None,
    risk_level: Optional[str] = None,
    behaviour_type: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[Path] = None,
) -> list[dict]:
    """General-purpose filtered search, used as a fallback tool for queries
    that don't map cleanly onto the four canned functions above."""
    clauses, params = [], []
    if date:
        clauses.append("substr(timestamp, 1, 10) = ?")
        params.append(date)
    if bay:
        clauses.append("bay = ?")
        params.append(bay)
    if risk_level:
        clauses.append("risk_level = ?")
        params.append(risk_level)
    if behaviour_type:
        clauses.append("behaviour_type = ?")
        params.append(behaviour_type)

    query = "SELECT * FROM events"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)

    with _connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    events = [Event.from_row(r).to_dict() for r in rows]

    if shift:
        events = [e for e in events if shift_for_hour(int(e["timestamp"][11:13])) == shift]
    return events


def is_store_empty(db_path: Optional[Path] = None) -> bool:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()
    return row["c"] == 0


if __name__ == "__main__":
    init_db()
    print(f"Initialized event store at {DB_PATH}")
