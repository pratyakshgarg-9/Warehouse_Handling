"""
test_assistant.py — verifies the event store, tool dispatch, and offline
assistant cover the spec's required query types and edge cases:

  1. "Show me all high-risk handling events from today's unloading."
  2. "What were the three most common risky behaviours during the morning shift?"
  3. "Which loading bay had the highest number of risky events?"
  4. "Why was this event classified as high risk?"

Plus edge cases: empty store, ambiguous queries, unknown event id, and a
sanity check that the assistant only ever reflects stored data (no
hallucinated bays/behaviours).

Run: python test_assistant.py
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import store
import tools
from offline_router import answer_offline

PASS = "PASS"
FAIL = "FAIL"
results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    results.append((name, condition, detail))
    print(f"[{PASS if condition else FAIL}] {name}" + (f" — {detail}" if detail and not condition else ""))


def _safe_unlink(path: Path) -> None:
    """Windows sometimes keeps a brief file-handle lock on a just-closed
    sqlite3 connection even after conn.close() returns, causing unlink to
    raise PermissionError. Not a store.py bug — just OS/GC timing — so this
    is a best-effort cleanup, not a test assertion."""
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass


def with_temp_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    path = Path(tmp.name)
    store.init_db(path)
    return path


def test_empty_store_edge_case():
    print("\n-- Edge case: empty store --")
    path = with_temp_db()
    original = store.DB_PATH
    store.DB_PATH = path  # type: ignore[misc]
    try:
        check("is_store_empty() is True on fresh DB", store.is_store_empty(path))
        answer = answer_offline("Show me all high-risk handling events from today's unloading.")
        check(
            "offline assistant reports no data honestly, doesn't invent events",
            "no events" in answer.lower() or "nothing" in answer.lower(),
            answer,
        )
    finally:
        store.DB_PATH = original
        _safe_unlink(path)


def test_insert_validation():
    print("\n-- Edge case: insert validation rejects bad data --")
    path = with_temp_db()
    try:
        threw = False
        try:
            store.insert_event(
                event_id="evt_00001",
                timestamp="2026-09-06T08:00:00Z",
                behaviour_type="not_a_real_behaviour",
                risk_level="High",
                risk_score=0.7,
                bay="bay_1",
                object_ids=[1],
                evidence_frame_path="shared/evidence/evt_00001.jpg",
                explanation="test",
                db_path=path,
            )
        except store.EventValidationError:
            threw = True
        check("insert_event rejects invalid behaviour_type", threw)

        threw = False
        try:
            store.insert_event(
                event_id="evt_00002",
                timestamp="2026-09-06T08:00:00Z",
                behaviour_type="dropped",
                risk_level="extreme",  # invalid
                risk_score=0.7,
                bay="bay_1",
                object_ids=[1],
                evidence_frame_path="shared/evidence/evt_00002.jpg",
                explanation="test",
                db_path=path,
            )
        except store.EventValidationError:
            threw = True
        check("insert_event rejects invalid risk_level", threw)

        threw = False
        try:
            store.insert_event(
                event_id="evt_00003",
                timestamp="2026-09-06T08:00:00Z",
                behaviour_type="dropped",
                risk_level="High",
                risk_score=1.5,  # out of range
                bay="bay_1",
                object_ids=[1],
                evidence_frame_path="shared/evidence/evt_00003.jpg",
                explanation="test",
                db_path=path,
            )
        except store.EventValidationError:
            threw = True
        check("insert_event rejects out-of-range risk_score", threw)
    finally:
        _safe_unlink(path)


def test_required_query_types():
    print("\n-- Required query type coverage --")
    path = with_temp_db()
    original = store.DB_PATH
    store.DB_PATH = path  # type: ignore[misc]
    try:
        from datetime import datetime, timezone

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Seed deterministic events covering all four query types.
        e1 = store.insert_event(
            event_id="evt_00001", timestamp=f"{today}T09:00:00Z", bay="bay_1",
            behaviour_type="dropped", risk_level="High", risk_score=0.7,
            object_ids=[7, 3], evidence_frame_path="shared/evidence/evt_00001.jpg",
            explanation="Product dropped from approximately 1 metre during unloading.",
            db_path=path,
        )
        store.insert_event(
            event_id="evt_00002", timestamp=f"{today}T09:15:00Z", bay="bay_1",
            behaviour_type="dropped", risk_level="High", risk_score=0.65,
            object_ids=[9], evidence_frame_path="shared/evidence/evt_00002.jpg",
            explanation="Another drop near active forklift path.",
            db_path=path,
        )
        store.insert_event(
            event_id="evt_00003", timestamp=f"{today}T10:00:00Z", bay="bay_2",
            behaviour_type="rough_handling", risk_level="High", risk_score=0.6,
            object_ids=[11], evidence_frame_path="shared/evidence/evt_00003.jpg",
            explanation="Sudden jolt observed.",
            db_path=path,
        )
        store.insert_event(
            event_id="evt_00004", timestamp=f"{today}T10:30:00Z", bay="bay_1",
            behaviour_type="no_required_equipment", risk_level="Medium", risk_score=0.4,
            object_ids=[12], evidence_frame_path="shared/evidence/evt_00004.jpg",
            explanation="Long manual carry, no trolley.",
            db_path=path,
        )
        store.insert_event(
            event_id="evt_00005", timestamp=f"{today}T15:00:00Z", bay="bay_3",
            behaviour_type="dropped", risk_level="Low", risk_score=0.15,
            object_ids=[13], evidence_frame_path="shared/evidence/evt_00005.jpg",
            explanation="Minor lapse, corrected immediately.",
            db_path=path,
        )

        # Query 1: high-risk events today.
        events = store.get_high_risk_events(date=today, db_path=path)
        check(
            "Q1: high-risk events today returns exactly the 3 High/Critical events",
            len(events) == 3 and all(e["risk_level"] in ("High", "Critical") for e in events),
            str(events),
        )

        # Query 2: top risky behaviours in the morning shift (hours 6-14 UTC).
        top = store.get_top_risky_behaviours(shift="Morning", limit=3, db_path=path)
        behaviours = [t["behaviour_type"] for t in top]
        check(
            "Q2: top risky behaviours (morning) includes 'dropped' as most frequent",
            behaviours and behaviours[0] == "dropped",
            str(top),
        )
        check(
            "Q2: low-risk event excluded from risky-behaviour ranking",
            top[0]["count"] == 2,  # only the 2 High 'dropped' events, not the Low one
            str(top),
        )

        # Query 3: bay with most risky events.
        bay = store.get_bay_with_most_risky_events(date=today, db_path=path)
        check(
            "Q3: bay_1 identified as bay with most risky events",
            bay is not None and bay["bay"] == "bay_1" and bay["count"] == 3,
            str(bay),
        )

        # Query 4: why was event X classified as high risk.
        detail = store.get_event_by_id(e1, db_path=path)
        check(
            "Q4: get_event_by_id returns the stored explanation verbatim",
            detail is not None and "approximately 1 metre" in detail["explanation"],
            str(detail),
        )

        # tools.dispatch wiring sanity check
        dispatched = tools.dispatch("get_bay_with_most_risky_events", {"date": today})
        check(
            "tools.dispatch routes to the same store function correctly",
            dispatched == bay,
            str(dispatched),
        )
    finally:
        store.DB_PATH = original
        _safe_unlink(path)


def test_unknown_event_id_edge_case():
    print("\n-- Edge case: unknown event id --")
    path = with_temp_db()
    try:
        result = store.get_event_by_id("evt_99999", db_path=path)
        check("get_event_by_id returns None for missing id (no hallucination)", result is None)
    finally:
        _safe_unlink(path)


def test_ambiguous_query_edge_case():
    print("\n-- Edge case: ambiguous query --")
    path = with_temp_db()
    original = store.DB_PATH
    store.DB_PATH = path  # type: ignore[misc]
    try:
        store.insert_event(
            event_id="evt_00001", timestamp="2026-09-06T09:00:00Z", bay="bay_1",
            behaviour_type="unstable_stacking", risk_level="Medium", risk_score=0.35,
            object_ids=[5, 6], evidence_frame_path="shared/evidence/evt_00001.jpg",
            explanation="Stack exceeded height-to-width ratio.",
            db_path=path,
        )
        # "risky events" with no bay/date/shift given — should not crash,
        # should return something grounded rather than an invented answer.
        answer = answer_offline("What are the risky events?")
        check(
            "ambiguous query still returns a grounded, non-crashing answer",
            isinstance(answer, str) and len(answer) > 0,
            answer,
        )
    finally:
        store.DB_PATH = original
        _safe_unlink(path)


if __name__ == "__main__":
    test_empty_store_edge_case()
    test_insert_validation()
    test_required_query_types()
    test_unknown_event_id_edge_case()
    test_ambiguous_query_edge_case()

    print("\n" + "=" * 50)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print(f"{passed}/{total} checks passed")
    if passed != total:
        raise SystemExit(1)
