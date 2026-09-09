"""
seed_data.py — populate events.db with realistic sample events so the
assistant and dashboard have something to query during development.

This stands in for Member 2's real pipeline output until it starts
flowing (or as a supplement if only a handful of real events exist).
Behaviour types and explanation text mirror
behaviour-risk/behaviour_risk_engine/explanations.py so sample data reads
like real output, not placeholder text. Run directly:
`python seed_data.py [--reset] [--n 60]`
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import store

BAYS = ["bay_1"]  # pilot scope is a single bay

# (behaviour_type, risk_level, risk_score range, explanation) — explanation
# text matches behaviour_risk_engine/explanations.py's templates.
SCENARIOS = [
    ("dropped", "High", (0.55, 0.75),
     "Product underwent a rapid, uncontrolled fall rather than being lowered under control. "
     "Potential risk: impact damage to the product or its contents. "
     "Correct practice: lift and lower cartons with a controlled, supported motion — never let them fall or drop from height."),
    ("dragged", "Medium", (0.25, 0.45),
     "Product was dragged across the floor instead of being lifted clear of the ground. "
     "Potential risk: surface abrasion, seam damage, or contamination to the product. "
     "Correct practice: lift the product fully before moving it, using a trolley for longer distances."),
    ("rough_handling", "High", (0.5, 0.8),
     "Product experienced a sudden, high-force impact while still being actively handled. "
     "Potential risk: internal or structural damage from excessive force. "
     "Correct practice: handle products with smooth, deliberate movements and avoid sudden jolts or impacts."),
    ("stepping_on_product", "Medium", (0.4, 0.55),
     "A person stepped or stood on the product instead of handling it directly. "
     "Potential risk: crushing damage from applied body weight. "
     "Correct practice: never use product packaging as a step or support surface — use designated equipment."),
    ("no_required_equipment", "Medium", (0.35, 0.5),
     "Product was carried a substantial distance by hand with no handling equipment used. "
     "Potential risk: strain-related mishandling or drops over a long manual carry. "
     "Correct practice: use a trolley or other designated equipment for moves beyond a short distance."),
    ("pushed_or_thrown", "Critical", (0.65, 0.9),
     "Product was moving at high speed with nobody in contact with it, consistent with being pushed or thrown rather than carried. "
     "Potential risk: impact damage on landing or collision with other stock. "
     "Correct practice: always carry or lower products by hand — never push or throw them to their destination."),
]


def seed(n: int = 60, seed_value: int = 42) -> list[str]:
    rng = random.Random(seed_value)
    ids = []
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    for i in range(n):
        day_offset = rng.choice([0, 0, 0, -1])  # mostly today, some yesterday
        hour = rng.randint(5, 23)
        minute = rng.randint(0, 59)
        second = rng.randint(0, 59)
        ts = today + timedelta(days=day_offset, hours=hour, minutes=minute, seconds=second)

        behaviour_type, risk_level, score_range, explanation = rng.choice(SCENARIOS)
        risk_score = round(rng.uniform(*score_range), 3)
        event_id = f"evt_{i + 1:05d}"

        object_ids = [rng.randint(1, 200)]
        if rng.random() < 0.5:
            object_ids.append(rng.randint(1, 200))

        inserted_id = store.insert_event(
            event_id=event_id,
            timestamp=ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            behaviour_type=behaviour_type,
            risk_level=risk_level,
            risk_score=risk_score,
            bay=rng.choice(BAYS),
            object_ids=object_ids,
            evidence_frame_path=f"shared/evidence/{event_id}.jpg",
            explanation=explanation,
        )
        ids.append(inserted_id)
    return ids


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Delete events.db before seeding.")
    parser.add_argument("--n", type=int, default=60, help="Number of events to generate.")
    args = parser.parse_args()

    if args.reset and store.DB_PATH.exists():
        Path(store.DB_PATH).unlink()

    store.init_db()
    ids = seed(n=args.n)
    print(f"Seeded {len(ids)} events into {store.DB_PATH}")
