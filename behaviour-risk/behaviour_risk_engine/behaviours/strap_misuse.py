"""
"Using packaging straps to lift or pull cartons" — a person handling a
carton while a strap-class object overlaps it, rather than using a proper
lifting point or equipment. Shows up in the real demo footage ("...using
strap to hold").

This depends entirely on Member 1's detector recognizing a dedicated
"strap" class (constants.STRAP_CLASSES), which isn't part of any labeling
plan discussed so far (person/carton/pallet/trolley). Until that class
exists in the real stream, this detector will simply never fire on real
data — flagged rather than silently assumed away.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Set

from ..constants import PERSON_CLASS, PRODUCT_CLASSES, STRAP_CLASSES
from ..geometry import bboxes_overlap
from ..models import DetectedObject, RawDetection
from ..pair_debounce import PairDebouncer
from ..track_store import TrackStore
from .base import BehaviourDetector

CONTACT_PAD_PX = 20.0
MIN_DURATION_S = 0.5


class StrapMisuseDetector(BehaviourDetector):
    behaviour_type = "strap_misuse"

    def __init__(self) -> None:
        self._debounce = PairDebouncer(MIN_DURATION_S)

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
        straps = [o for o in objects if o.cls in STRAP_CLASSES]

        active: Set[int] = set()
        for c in cartons:
            handled = any(bboxes_overlap(c.bbox, p.bbox, pad=CONTACT_PAD_PX) for p in persons)
            if not handled:
                continue
            strap_attached = any(bboxes_overlap(c.bbox, s.bbox, pad=CONTACT_PAD_PX) for s in straps)
            if not strap_attached:
                continue
            if self._debounce.observe(c.track_id, timestamp, active):
                results.append(RawDetection(
                    behaviour_type=self.behaviour_type,
                    object_ids=[c.track_id],
                    frame_id=frame_id,
                    timestamp=timestamp,
                    details={},
                ))

        self._debounce.sweep(active)
        return results
