"""
Runs the engine over the synthetic sample scenarios and checks that each
implemented behaviour fires, and that every produced event matches the
shared event schema (root CLAUDE.md) and never overclaims confirmed damage
(behaviour-risk/CLAUDE.md's explicit rule).
"""

from __future__ import annotations

import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
BR_DIR = THIS_DIR.parent
REPO_ROOT = BR_DIR.parent
for p in (REPO_ROOT, BR_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from behaviour_risk_engine.engine import BehaviourEngine  # noqa: E402
from sample_data.generate_sample_frames import generate_sample_frames  # noqa: E402


def _run_engine():
    engine = BehaviourEngine(bay="bay_1", event_sink=lambda event: None)
    events = []
    for frame in generate_sample_frames():
        events.extend(engine.process_frame(frame))
    return events


def test_all_four_scenarios_produce_events():
    events = _run_engine()
    types = {e.behaviour_type for e in events}
    assert {"dropped", "dragged", "rough_handling", "incorrect_stacking"} <= types


def test_events_match_shared_schema():
    events = _run_engine()
    assert events, "expected at least one event from the sample scenarios"
    for e in events:
        d = e.to_dict()
        assert d["event_id"].startswith("evt_")
        assert d["risk_level"] in {"Low", "Medium", "High", "Critical"}
        assert 0.0 <= d["risk_score"] <= 1.0
        assert d["bay"] == "bay_1"
        assert d["object_ids"]
        assert d["evidence_frame_path"].startswith("shared/evidence/")
        assert d["explanation"]


def test_never_asserts_confirmed_damage():
    events = _run_engine()
    for e in events:
        assert "confirmed damage" not in e.explanation.lower()


def test_dropped_event_has_expected_details_derived_score():
    events = _run_engine()
    dropped = [e for e in events if e.behaviour_type == "dropped"]
    assert len(dropped) == 1
    assert dropped[0].risk_score > 0.35  # base severity alone, before impact/duration terms
