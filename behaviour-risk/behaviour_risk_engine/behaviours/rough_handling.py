"""
"Rough handling / excessive impact" — behaviour #3: a carton being jolted
or slammed sideways with high speed *while still being actively handled by
a person*.

Deliberately horizontal-only (see track_store.horizontal_speed) so it
doesn't double-count a straight-down fall, which "dropped" already owns.
Requires person contact so it doesn't double-count a carton already in
flight after release, which "pushed_or_thrown" owns instead — that one is
the same kind of high-speed motion but with nobody in contact.

("Stepping or standing on cartons" — the doc's other bad practice originally
folded in here — now has its own detector: stepping_on_product.py.)

SPEED_WINDOW and CONSECUTIVE_FRAMES_REQUIRED were widened after testing
against Member 1's real cv-pipeline output (2026-09-07) — see
pushed_or_thrown.py's docstring for the full finding: a real detector's
bbox jitters enough frame-to-frame that a naive 2-frame speed window
crosses this threshold on pure noise, not real jolts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Set

from ..constants import PERSON_CLASS, PRODUCT_CLASSES
from ..geometry import bboxes_overlap
from ..models import DetectedObject, RawDetection
from ..track_store import TrackStore
from .base import BehaviourDetector

JERK_SPEED_PX_S = 500.0       # horizontal bbox-center speed that counts as a sideways jolt/impact
CONTACT_PAD_PX = 20.0
SPEED_WINDOW = 6
CONSECUTIVE_FRAMES_REQUIRED = 2


class RoughHandlingDetector(BehaviourDetector):
    behaviour_type = "rough_handling"

    def __init__(self) -> None:
        self._streak: Dict[int, int] = {}
        self._jerking: Set[int] = set()  # track_ids currently above the jerk threshold, to report once per jolt

    def process_frame(
        self,
        frame_id: int,
        timestamp: datetime,
        objects: List[DetectedObject],
        store: TrackStore,
    ) -> List[RawDetection]:
        results: List[RawDetection] = []
        persons = [o for o in objects if o.cls == PERSON_CLASS]
        cartons = [o for o in objects if o.cls in PRODUCT_CLASSES]
        current_carton_ids = {c.track_id for c in cartons}

        for c in cartons:
            in_contact = any(bboxes_overlap(c.bbox, p.bbox, pad=CONTACT_PAD_PX) for p in persons)
            speed = store.horizontal_speed(c.track_id, window=SPEED_WINDOW)
            qualifies = in_contact and speed > JERK_SPEED_PX_S

            if not qualifies:
                self._streak[c.track_id] = 0
                self._jerking.discard(c.track_id)
                continue

            self._streak[c.track_id] = self._streak.get(c.track_id, 0) + 1
            if self._streak[c.track_id] >= CONSECUTIVE_FRAMES_REQUIRED and c.track_id not in self._jerking:
                self._jerking.add(c.track_id)
                results.append(RawDetection(
                    behaviour_type=self.behaviour_type,
                    object_ids=[c.track_id] + [p.track_id for p in persons if bboxes_overlap(c.bbox, p.bbox, pad=CONTACT_PAD_PX)],
                    frame_id=frame_id,
                    timestamp=timestamp,
                    details={"cause": "sudden_impact", "peak_speed_px_s": speed},
                ))

        for tid in list(self._jerking):
            if tid not in current_carton_ids:
                self._jerking.discard(tid)
        for tid in list(self._streak):
            if tid not in current_carton_ids:
                self._streak.pop(tid, None)

        return results
