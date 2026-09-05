"""
"Product dragged instead of lifted" — behaviour #2: a carton moves a
meaningful distance across the floor while staying in continuous contact
with a person, without ever being lifted (its bottom edge height barely
changes) — contrasted with a correct lift-and-carry where the bottom edge
rises well clear of the floor.

Per-track baseline state machine: while a person stays near the carton, we
track the bottom-edge height from when handling started. If it's ever
lifted clear of that height, the whole contact episode is disqualified as
a normal carry — even after it plateaus at the new (lifted) height, since
that's a legitimate "walk while holding it steady" motion, not a drag.
Only an episode where the height never leaves the starting band, while
moving sideways for long enough, counts as a drag. A disqualified episode
can only become eligible again once contact fully breaks and restarts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from ..constants import PERSON_CLASS, PRODUCT_CLASSES
from ..geometry import bboxes_overlap
from ..models import DetectedObject, RawDetection
from ..track_store import TrackStore
from .base import BehaviourDetector

CONTACT_PAD_PX = 20.0           # how close a person must be to the carton to count as "handling" it
MAX_LIFT_PX = 15.0              # bottom-edge movement within this band still counts as "not lifted"
MIN_DRAG_DISTANCE_PX = 60.0     # total horizontal movement required before it counts as a drag
DRAG_WINDOW_FRAMES = 15         # ~0.5s at 30fps — window used to measure that movement
MIN_DRAG_DURATION_S = 0.4       # must have been in sustained un-lifted contact this long


class DraggedDetector(BehaviourDetector):
    behaviour_type = "dragged"

    def __init__(self) -> None:
        self._state: Dict[int, dict] = {}

    def process_frame(
        self,
        frame_id: int,
        timestamp: datetime,
        objects: List[DetectedObject],
        store: TrackStore,
    ) -> List[RawDetection]:
        results: List[RawDetection] = []
        persons = [o for o in objects if o.cls == PERSON_CLASS]
        current_ids = set()

        for obj in objects:
            if obj.cls not in PRODUCT_CLASSES:
                continue
            current_ids.add(obj.track_id)

            handlers = [p for p in persons if bboxes_overlap(obj.bbox, p.bbox, pad=CONTACT_PAD_PX)]
            st = self._state.get(obj.track_id)

            if not handlers:
                self._state[obj.track_id] = {
                    "baseline_y2": obj.y2, "baseline_time": timestamp, "reported": False, "disqualified": False,
                }
                continue

            if st is None:
                self._state[obj.track_id] = {
                    "baseline_y2": obj.y2, "baseline_time": timestamp, "reported": False, "disqualified": False,
                }
                continue

            lifted = abs(obj.y2 - st["baseline_y2"]) >= MAX_LIFT_PX
            if lifted:
                st["disqualified"] = True  # a real lift happened during this contact episode — never a drag,
            if st["disqualified"]:         # even once the height plateaus again at the new, lifted height
                continue

            elapsed = (timestamp - st["baseline_time"]).total_seconds()
            distance = store.horizontal_displacement(obj.track_id, window=DRAG_WINDOW_FRAMES)

            if (
                not st["reported"]
                and elapsed >= MIN_DRAG_DURATION_S
                and distance >= MIN_DRAG_DISTANCE_PX
            ):
                results.append(RawDetection(
                    behaviour_type=self.behaviour_type,
                    object_ids=[obj.track_id] + [p.track_id for p in handlers],
                    frame_id=frame_id,
                    timestamp=timestamp,
                    details={"distance_px": distance, "duration_s": elapsed},
                ))
                st["reported"] = True

        for tid in list(self._state):
            if tid not in current_ids:
                self._state.pop(tid, None)

        return results
