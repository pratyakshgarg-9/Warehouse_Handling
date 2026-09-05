"""
"Stepping or standing on cartons" — the challenge doc's own bad-practice
item (behaviour #9), previously folded into rough_handling because the
shared behaviour_type enum had no dedicated slot for it. Now split out as
its own detector, with "stepping_on_product" added to the shared enum in
the root CLAUDE.md and shared/config.py — flagged to the team as a schema
change since other members build against those files.

Approximates a person's "feet" as the bottom 15% of their bbox
(geometry.bottom_strip) rather than real pose keypoints, since the
per-frame schema doesn't document keypoint index/ordering semantics yet.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Set, Tuple

from ..constants import PERSON_CLASS, PRODUCT_CLASSES
from ..geometry import bboxes_overlap, bottom_strip
from ..models import DetectedObject, RawDetection
from ..pair_debounce import PairDebouncer
from ..track_store import TrackStore
from .base import BehaviourDetector

STEP_MIN_DURATION_S = 0.3  # how long a foot must overlap a carton before it counts (ignores brief brushes)


class SteppingOnProductDetector(BehaviourDetector):
    behaviour_type = "stepping_on_product"

    def __init__(self) -> None:
        self._debounce = PairDebouncer(STEP_MIN_DURATION_S)

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

        active: Set[Tuple[int, int]] = set()
        for p in persons:
            feet = bottom_strip(p)
            for c in cartons:
                if not bboxes_overlap(feet, c.bbox):
                    continue
                key = (p.track_id, c.track_id)
                if self._debounce.observe(key, timestamp, active):
                    results.append(RawDetection(
                        behaviour_type=self.behaviour_type,
                        object_ids=[p.track_id, c.track_id],
                        frame_id=frame_id,
                        timestamp=timestamp,
                        details={"duration_s": STEP_MIN_DURATION_S},
                    ))
        self._debounce.sweep(active)
        return results
