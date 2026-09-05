"""
"Product placed outside designated area" — behaviour #5: once a carton
comes to rest (isn't still being carried into position), its center should
land inside the bay's designated placement zone.

DESIGNATED_AREA_BBOX is a placeholder pixel-space rectangle — there's no
camera calibration in the pilot yet, so this can't be a real-world zone.
Needs to be set from the actual camera framing once Member 1's real
footage/camera setup is available.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Set

from ..constants import PRODUCT_CLASSES
from ..models import DetectedObject, RawDetection
from ..pair_debounce import PairDebouncer
from ..track_store import TrackStore
from .base import BehaviourDetector

DESIGNATED_AREA_BBOX = [50.0, 250.0, 700.0, 560.0]  # placeholder — calibrate against real footage
REST_SPEED_PX_S = 40.0       # below this, the product is considered "at rest" for placement checking
OUTSIDE_MIN_DURATION_S = 1.0  # ignore products still in transit through the zone boundary


def _inside_area(cx: float, cy: float) -> bool:
    x1, y1, x2, y2 = DESIGNATED_AREA_BBOX
    return x1 <= cx <= x2 and y1 <= cy <= y2


class OutsideDesignatedAreaDetector(BehaviourDetector):
    behaviour_type = "outside_designated_area"

    def __init__(self) -> None:
        self._debounce = PairDebouncer(OUTSIDE_MIN_DURATION_S)

    def process_frame(
        self,
        frame_id: int,
        timestamp: datetime,
        objects: List[DetectedObject],
        store: TrackStore,
    ) -> List[RawDetection]:
        results: List[RawDetection] = []
        active: Set[int] = set()

        for obj in objects:
            if obj.cls not in PRODUCT_CLASSES:
                continue
            if store.speed(obj.track_id, window=3) > REST_SPEED_PX_S:
                continue  # still moving; only judge placement once it's settled
            cx, cy = obj.center
            if _inside_area(cx, cy):
                continue
            if self._debounce.observe(obj.track_id, timestamp, active):
                results.append(RawDetection(
                    behaviour_type=self.behaviour_type,
                    object_ids=[obj.track_id],
                    frame_id=frame_id,
                    timestamp=timestamp,
                    details={"duration_s": OUTSIDE_MIN_DURATION_S},
                ))

        self._debounce.sweep(active)
        return results
