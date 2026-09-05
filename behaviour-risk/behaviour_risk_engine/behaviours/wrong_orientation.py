"""
"Vertical product kept horizontally" — a product from a class that's
normally handled upright (see constants.ORIENTATION_SENSITIVE_CLASSES) is
observed lying on its side for a sustained stretch. Shows up in the real
demo footage ("...vertical product kept horizontally...").

Proxy: a landscape bbox (width clearly greater than height) for a class
that should be portrait when handled correctly. There's no real per-product
"design orientation" field in the schema — this only works for classes
where lying flat is inherently wrong, which is why it's scoped to
ORIENTATION_SENSITIVE_CLASSES rather than every product class.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Set

from ..constants import ORIENTATION_SENSITIVE_CLASSES
from ..models import DetectedObject, RawDetection
from ..pair_debounce import PairDebouncer
from ..track_store import TrackStore
from .base import BehaviourDetector

LANDSCAPE_RATIO_THRESHOLD = 1.3  # width > 1.3x height counts as clearly lying on its side
MIN_DURATION_S = 1.0


class WrongOrientationDetector(BehaviourDetector):
    behaviour_type = "wrong_orientation"

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
        active: Set[int] = set()

        for obj in objects:
            if obj.cls not in ORIENTATION_SENSITIVE_CLASSES:
                continue
            if obj.height <= 0:
                continue
            ratio = obj.width / obj.height
            if ratio < LANDSCAPE_RATIO_THRESHOLD:
                continue
            if self._debounce.observe(obj.track_id, timestamp, active):
                results.append(RawDetection(
                    behaviour_type=self.behaviour_type,
                    object_ids=[obj.track_id],
                    frame_id=frame_id,
                    timestamp=timestamp,
                    details={"width_to_height_ratio": ratio},
                ))

        self._debounce.sweep(active)
        return results
