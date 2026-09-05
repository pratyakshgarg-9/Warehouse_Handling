"""
"Pallet positioned incorrectly / product larger than pallet" — behaviour
#7: a carton resting on a pallet overhangs the pallet's footprint —
either the product doesn't fit the pallet, or it wasn't placed centered
on it. Reuses the same resting-on/overhang geometry as incorrect_stacking,
just between a carton and a pallet instead of two cartons.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Set, Tuple

from ..constants import PRODUCT_CLASSES, SUPPORT_CLASSES
from ..geometry import is_resting_on, overhang_ratio
from ..models import DetectedObject, RawDetection
from ..pair_debounce import PairDebouncer
from ..track_store import TrackStore
from .base import BehaviourDetector

OVERHANG_RATIO_THRESHOLD = 0.25  # pallets are meant to fully contain the product, so a tighter threshold than carton-on-carton
STABLE_MIN_S = 1.0


class PalletIncorrectPositionDetector(BehaviourDetector):
    behaviour_type = "pallet_incorrect_position"

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
        pallets = [o for o in objects if o.cls in SUPPORT_CLASSES]

        active: Set[Tuple[int, int]] = set()
        for carton in cartons:
            for pallet in pallets:
                if not is_resting_on(carton, pallet):
                    continue
                ratio = overhang_ratio(carton, pallet)
                if ratio <= OVERHANG_RATIO_THRESHOLD:
                    continue

                key = (carton.track_id, pallet.track_id)
                if self._debounce.observe(key, timestamp, active):
                    results.append(RawDetection(
                        behaviour_type=self.behaviour_type,
                        object_ids=[carton.track_id, pallet.track_id],
                        frame_id=frame_id,
                        timestamp=timestamp,
                        details={"overhang_ratio": ratio},
                    ))

        self._debounce.sweep(active)
        return results
