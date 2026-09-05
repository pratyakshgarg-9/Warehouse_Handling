"""
"Material pushed or thrown" — behaviour #8: a carton moving at high speed
with nobody currently in contact with it — i.e. already released/in-flight,
as opposed to rough_handling's "jolted while still being handled" (which
requires contact) or dragged's sustained floor-level slide (which requires
continuous contact throughout).
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Set

from ..constants import PERSON_CLASS, PRODUCT_CLASSES
from ..geometry import bboxes_overlap
from ..models import DetectedObject, RawDetection
from ..track_store import TrackStore
from .base import BehaviourDetector

THROWN_SPEED_PX_S = 400.0
CONTACT_PAD_PX = 20.0


class PushedOrThrownDetector(BehaviourDetector):
    behaviour_type = "pushed_or_thrown"

    def __init__(self) -> None:
        self._reported: Set[int] = set()

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
        current_ids = {c.track_id for c in cartons}

        for c in cartons:
            in_contact = any(bboxes_overlap(c.bbox, p.bbox, pad=CONTACT_PAD_PX) for p in persons)
            speed = store.horizontal_speed(c.track_id, window=3)

            if not in_contact and speed > THROWN_SPEED_PX_S:
                if c.track_id not in self._reported:
                    self._reported.add(c.track_id)
                    results.append(RawDetection(
                        behaviour_type=self.behaviour_type,
                        object_ids=[c.track_id],
                        frame_id=frame_id,
                        timestamp=timestamp,
                        details={"peak_speed_px_s": speed},
                    ))
            else:
                self._reported.discard(c.track_id)

        for tid in list(self._reported):
            if tid not in current_ids:
                self._reported.discard(tid)

        return results
