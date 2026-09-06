"""
Run BehaviourEngine against Member 1's REAL published cv-pipeline output
(cv-pipeline/outputs/*.json) via cv_pipeline_adapter — the actual Sep 6
"first integration" checkpoint, using real detections instead of the
synthetic sample_data used for standalone development/testing.

Usage:
    python run_on_cv_output.py [path/to/cv_output.json]

Defaults to cv-pipeline/outputs/cv_output.json if no path is given.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent
for p in (REPO_ROOT, THIS_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from behaviour_risk_engine.cv_pipeline_adapter import adapt_frame  # noqa: E402
from behaviour_risk_engine.engine import BehaviourEngine  # noqa: E402


def main() -> None:
    default_path = REPO_ROOT / "cv-pipeline" / "outputs" / "cv_output.json"
    raw_path = Path(sys.argv[1]) if len(sys.argv) > 1 else default_path

    raw_frames = json.loads(raw_path.read_text(encoding="utf-8"))

    total_raw_objects = sum(len(f.get("objects", [])) for f in raw_frames)
    total_tracked_objects = sum(
        1 for f in raw_frames for o in f.get("objects", []) if o.get("track_id", -1) != -1
    )

    engine = BehaviourEngine(bay="bay_1")
    all_events = []
    adapted_object_count = 0
    for raw_frame in raw_frames:
        frame = adapt_frame(raw_frame)
        adapted_object_count += len(frame["objects"])
        all_events.extend(engine.process_frame(frame))

    print(f"Source: {raw_path}")
    print(f"Raw frames: {len(raw_frames)}")
    print(f"Raw detections (all): {total_raw_objects}")
    print(f"Raw detections with a real track_id (!= -1): {total_tracked_objects}")
    print(f"Detections surviving the adapter (tracked + confidence filter): {adapted_object_count}")
    print(f"Events produced: {len(all_events)}\n")

    for event in all_events:
        print(json.dumps(event.to_dict(), indent=2))
        print()


if __name__ == "__main__":
    main()
