"""
seed_real_events.py — rebuilds the real event store from ALL of Member 1's
real cv-pipeline outputs (cv-pipeline/outputs/*.json), each clip anchored
to its own distinct video_start_utc.

Why this exists: the original seeding pass (run ad hoc, not saved as a
script) called the engine without passing video_start_utc for any clip, so
cv_pipeline_adapter.py's DEFAULT_REFERENCE_TIME (2026-01-01T00:00:00Z) was
used for all 7 clips. Every clip's event timestamps are frame-relative
(seconds since that clip's own start), so with a shared reference they all
land in the same ~30-second window — discovered when the dashboard's Video
Review page showed an event from a completely different clip (rolling_drag)
overlaid on dock_level_dragging_cupboard's footage, because both clips'
events fall inside the same [0s, 31s) query window.

Fix: give each clip its own video_start_utc, spread far enough apart
(hourly) that no two clips' events can ever land in the same window, spread
across a single demo day and across all three shifts (Morning/Evening/
Night) so the Timeline & Trends heatmap and the assistant's shift-scoped
questions have something real to show instead of everything clustering at
hour 0.

Usage:
    python seed_real_events.py
"""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent
for p in (REPO_ROOT, THIS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from behaviour_risk_engine.cv_pipeline_adapter import adapt_frame  # noqa: E402
from behaviour_risk_engine.engine import BehaviourEngine  # noqa: E402

_STORE_PATH = REPO_ROOT / "backend-assistant" / "store.py"


def _init_events_table() -> None:
    """events.db is gitignored, so a fresh clone has no schema yet — load
    store.py the same way event_sink.py does (hyphenated folder, not an
    importable package name) and create the table before seeding."""
    spec = importlib.util.spec_from_file_location("backend_assistant_store", _STORE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.init_db()

OUTPUTS_DIR = REPO_ROOT / "cv-pipeline" / "outputs"
EVENTS_DB = REPO_ROOT / "backend-assistant" / "events.db"

# One demo day, one distinct hour per clip, spread across all three shifts
# (Morning 6-14, Evening 14-22, Night 22-6) so shift-scoped questions and
# the heatmap have real spread instead of everything at hour 0.
CLIP_SCHEDULE = {
    "dock_level_dragging_cupboard": "2026-09-08T08:15:00Z",
    "kd_packets_dragged_heavy_box": "2026-09-08T10:40:00Z",
    "rolling_dragging_wet_floor":   "2026-09-08T13:05:00Z",
    "rolling_dropping_carton":      "2026-09-08T15:20:00Z",
    "stepping_vertical_heavy":      "2026-09-08T18:50:00Z",
    "throwing_mattresses":          "2026-09-08T21:10:00Z",
    "throwing_seating_strap":       "2026-09-08T23:30:00Z",
}


def main() -> None:
    _init_events_table()
    with sqlite3.connect(EVENTS_DB) as conn:
        before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        conn.execute("DELETE FROM events")
        conn.commit()
    print(f"Cleared events table ({before} rows removed).\n")

    total_events = 0
    for clip_name, start_iso in CLIP_SCHEDULE.items():
        raw_path = OUTPUTS_DIR / f"{clip_name}_cv.json"
        if not raw_path.exists():
            print(f"SKIP {clip_name}: {raw_path} not found")
            continue

        video_start_utc = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        raw_frames = json.loads(raw_path.read_text(encoding="utf-8"))

        engine = BehaviourEngine(bay="bay_1", event_id_prefix=clip_name[:14])
        clip_events = []
        for raw_frame in raw_frames:
            frame = adapt_frame(raw_frame, video_start_utc=video_start_utc)
            clip_events.extend(engine.process_frame(frame))

        behaviours = sorted({e.behaviour_type for e in clip_events})
        print(f"{clip_name:32s} start={start_iso}  events={len(clip_events):3d}  behaviours={behaviours}")
        total_events += len(clip_events)

    print(f"\nTotal events inserted: {total_events}")
    print("\nPer-clip DASHBOARD_VIDEO_START_UTC for the Video Review page:")
    for clip_name, start_iso in CLIP_SCHEDULE.items():
        print(f"  {clip_name:32s} {start_iso}")


if __name__ == "__main__":
    main()
