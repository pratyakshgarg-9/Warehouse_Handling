"""
"Product handled without required equipment" — behaviour #6: a person
manually carries/moves a carton a substantial distance with no trolley
anywhere near it, when the process expects longer moves to use one.

Distinct from "dragged": dragged flags the specific pattern of never
lifting the product off the floor. This one is about distance without
equipment, regardless of whether it was lifted — a long manual carry is
the bad practice, not just the drag motion itself.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from ..constants import EQUIPMENT_CLASSES, PERSON_CLASS, PRODUCT_CLASSES
from ..geometry import bboxes_overlap
from ..models import DetectedObject, RawDetection
from ..track_store import TrackStore
from .base import BehaviourDetector

CONTACT_PAD_PX = 20.0
EQUIPMENT_PROXIMITY_PAD_PX = 150.0    # how close a trolley must be to count as "used" for this carry
LONG_CARRY_DISTANCE_PX = 200.0        # cumulative distance that should have used a trolley instead
LONG_CARRY_WINDOW_FRAMES = 45         # ~1.5s at 30fps


class NoRequiredEquipmentDetector(BehaviourDetector):
    behaviour_type = "no_required_equipment"

    def __init__(self) -> None:
        self._reported: Dict[int, bool] = {}

    def process_frame(
        self,
        frame_id: int,
        timestamp: datetime,
        objects: List[DetectedObject],
        store: TrackStore,
    ) -> List[RawDetection]:
        results: List[RawDetection] = []
        persons = [o for o in objects if o.cls == PERSON_CLASS]
        trolleys = [o for o in objects if o.cls in EQUIPMENT_CLASSES]
        cartons = [o for o in objects if o.cls in PRODUCT_CLASSES]
        current_ids = {c.track_id for c in cartons}

        for c in cartons:
            handlers = [p for p in persons if bboxes_overlap(c.bbox, p.bbox, pad=CONTACT_PAD_PX)]
            if not handlers:
                self._reported[c.track_id] = False
                continue

            near_trolley = any(bboxes_overlap(c.bbox, tr.bbox, pad=EQUIPMENT_PROXIMITY_PAD_PX) for tr in trolleys)
            if near_trolley:
                self._reported[c.track_id] = False  # equipment used for this handling episode; don't flag it
                continue

            distance = store.horizontal_displacement(c.track_id, window=LONG_CARRY_WINDOW_FRAMES)
            if distance >= LONG_CARRY_DISTANCE_PX and not self._reported.get(c.track_id, False):
                results.append(RawDetection(
                    behaviour_type=self.behaviour_type,
                    object_ids=[c.track_id] + [p.track_id for p in handlers],
                    frame_id=frame_id,
                    timestamp=timestamp,
                    details={"distance_px": distance},
                ))
                self._reported[c.track_id] = True

        for tid in list(self._reported):
            if tid not in current_ids:
                self._reported.pop(tid, None)

        return results
