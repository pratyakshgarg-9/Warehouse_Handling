"""
"Unstable stacking" — the complementary failure mode to incorrect_stacking:
a stack that's tall and narrow relative to its base footprint is prone to
toppling even when each carton is fully supported (no overhang). Flagged
by height-to-base-width ratio rather than overhang.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Set, Tuple

from ..constants import PRODUCT_CLASSES
from ..geometry import is_resting_on
from ..models import DetectedObject, RawDetection
from ..pair_debounce import PairDebouncer
from ..track_store import TrackStore
from .base import BehaviourDetector

HEIGHT_TO_WIDTH_RATIO_THRESHOLD = 1.5  # a stack taller than 1.5x its base footprint's width is toppling-prone
STABLE_MIN_S = 1.0


class UnstableStackingDetector(BehaviourDetector):
    behaviour_type = "unstable_stacking"

    def __init__(self) -> None:
        self._debounce = PairDebouncer(STABLE_MIN_S)

    def process_frame(
        self,
        frame_id: int,
        timestamp: datetime,
        objects: List[DetectedObject],
        store: TrackStore,
    ) -> List[RawDetection]:
        results: List[RawDetection] = []
        cartons = [o for o in objects if o.cls in PRODUCT_CLASSES]

        active: Set[Tuple[int, int]] = set()
        for top in cartons:
            for base in cartons:
                if top.track_id == base.track_id:
                    continue
                if not is_resting_on(top, base):
                    continue
                if base.width <= 0:
                    continue
                stack_height = base.y2 - top.y1  # base's bottom edge to top's top edge
                ratio = stack_height / base.width
                if ratio <= HEIGHT_TO_WIDTH_RATIO_THRESHOLD:
                    continue

                key = (top.track_id, base.track_id)
                if self._debounce.observe(key, timestamp, active):
                    results.append(RawDetection(
                        behaviour_type=self.behaviour_type,
                        object_ids=[top.track_id, base.track_id],
                        frame_id=frame_id,
                        timestamp=timestamp,
                        details={"height_to_width_ratio": ratio},
                    ))

        self._debounce.sweep(active)
        return results
