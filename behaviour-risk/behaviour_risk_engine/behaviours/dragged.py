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

GRACE_FRAMES was added after testing against Member 1's real cv-pipeline
output (2026-09-07): a real "person overlaps carton" bbox check flickers
on and off during a genuine, continuous drag — not just because contact
itself is intermittent (occlusion, viewing angle), but because the carton
track's own detections drop out for stretches too (one real clip showed
gaps up to 29 frames on an otherwise-continuous track — the prototype
model's detections are "relatively sparse" per its own README). Without
tolerance for that, every brief gap in either signal fully reset the
episode and "dragged" never accumulated MIN_DRAG_DURATION_S, so it never
fired on real footage at all despite genuine dragging being the filmed
content. The grace counter now ages out an episode based on frames since
its last *confirmed contact*, regardless of whether the gap was caused by
"carton detected but no one touching it" or "carton not detected this
frame at all" — both are the same real-world problem (a momentary gap in
an otherwise-continuous handling episode) and need the same tolerance.
The grace window is comfortably longer than the observed within-episode
gaps, but much shorter than the multi-second gaps between genuinely
separate episodes, so distinct episodes still don't get merged.
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
GRACE_FRAMES = 20               # tolerate brief contact-detection dropouts without resetting the episode


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
        cartons = {o.track_id: o for o in objects if o.cls in PRODUCT_CLASSES}
        confirmed_this_frame = set()

        for track_id, obj in cartons.items():
            handlers = [p for p in persons if bboxes_overlap(obj.bbox, p.bbox, pad=CONTACT_PAD_PX)]
            if not handlers:
                continue  # aged via the grace sweep below, same as a track that isn't detected at all this frame

            confirmed_this_frame.add(track_id)
            st = self._state.get(track_id)

            if st is None:
                self._state[track_id] = {
                    "baseline_y2": obj.y2, "baseline_time": timestamp, "reported": False,
                    "disqualified": False, "frames_since_contact": 0,
                }
                continue

            st["frames_since_contact"] = 0

            lifted = abs(obj.y2 - st["baseline_y2"]) >= MAX_LIFT_PX
            if lifted:
                st["disqualified"] = True  # a real lift happened during this contact episode — never a drag,
            if st["disqualified"]:         # even once the height plateaus again at the new, lifted height
                continue

            elapsed = (timestamp - st["baseline_time"]).total_seconds()
            distance = store.horizontal_displacement(track_id, window=DRAG_WINDOW_FRAMES)

            if (
                not st["reported"]
                and elapsed >= MIN_DRAG_DURATION_S
                and distance >= MIN_DRAG_DISTANCE_PX
            ):
                results.append(RawDetection(
                    behaviour_type=self.behaviour_type,
                    object_ids=[track_id] + [p.track_id for p in handlers],
                    frame_id=frame_id,
                    timestamp=timestamp,
                    details={"distance_px": distance, "duration_s": elapsed},
                ))
                st["reported"] = True

        for tid in list(self._state):
            if tid in confirmed_this_frame:
                continue
            st = self._state[tid]
            st["frames_since_contact"] = st.get("frames_since_contact", 0) + 1
            if st["frames_since_contact"] > GRACE_FRAMES:
                self._state.pop(tid, None)

        return results
