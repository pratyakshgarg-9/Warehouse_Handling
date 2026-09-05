"""
Run the behaviour-risk pipeline standalone against synthetic sample frames
(Member 1's real per-frame stream isn't published yet). Prints every event
produced, matching the schema in the root CLAUDE.md exactly.

Usage:
    python demo.py
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

from behaviour_risk_engine.engine import BehaviourEngine  # noqa: E402
from sample_data.generate_sample_frames import generate_sample_frames  # noqa: E402


def main() -> None:
    frames = generate_sample_frames()
    engine = BehaviourEngine(bay="bay_1")

    all_events = []
    for frame in frames:
        all_events.extend(engine.process_frame(frame))

    print(f"Processed {len(frames)} synthetic frames -> {len(all_events)} events\n")
    for event in all_events:
        print(json.dumps(event.to_dict(), indent=2))
        print()


if __name__ == "__main__":
    main()
