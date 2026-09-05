"""
"Unsafe loading/unloading sequence" — behaviour #10: products staged or
moved without a stable, one-at-a-time plan. The doc frames this at the
level of the overall process rather than a single object's motion, which a
per-track rule can't really assess — the closest frame-level proxy
available here is a chaos signal: several products in motion at once
rather than a controlled, sequential handoff.

This is a single, bay-wide detector (not per-track), unlike every other
behaviour here — it looks at how many cartons are moving simultaneously,
not what any one of them is doing.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from ..constants import PRODUCT_CLASSES
from ..models import DetectedObject, RawDetection
from ..track_store import TrackStore
from .base import BehaviourDetector

MOVING_SPEED_PX_S = 60.0
CONCURRENT_MOVING_THRESHOLD = 3   # this many products in motion at once suggests an uncoordinated sequence
SUSTAINED_MIN_S = 1.0


class UnsafeLoadingSequenceDetector(BehaviourDetector):
    behaviour_type = "unsafe_loading_sequence"

    def __init__(self) -> None:
        self._since: Optional[datetime] = None
        self._reported = False

    def process_frame(
        self,
        frame_id: int,
        timestamp: datetime,
        objects: List[DetectedObject],
        store: TrackStore,
    ) -> List[RawDetection]:
        cartons = [o for o in objects if o.cls in PRODUCT_CLASSES]
        moving = [c for c in cartons if store.speed(c.track_id, window=3) > MOVING_SPEED_PX_S]

        if len(moving) < CONCURRENT_MOVING_THRESHOLD:
            self._since = None
            self._reported = False
            return []

        if self._since is None:
            self._since = timestamp
        duration = (timestamp - self._since).total_seconds()

        if duration >= SUSTAINED_MIN_S and not self._reported:
            self._reported = True
            return [RawDetection(
                behaviour_type=self.behaviour_type,
                object_ids=[c.track_id for c in moving],
                frame_id=frame_id,
                timestamp=timestamp,
                details={"concurrent_count": len(moving), "duration_s": duration},
            )]

        return []
