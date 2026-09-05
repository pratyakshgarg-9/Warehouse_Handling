"""
"Incorrect / unstable stacking" — behaviour #4: a carton is resting on top
of another with an unsupported overhang past the base carton's footprint,
held long enough to be a real stacking choice rather than a person still
mid-placement.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Set, Tuple

from ..constants import PRODUCT_CLASSES
from ..geometry import is_resting_on, overhang_ratio
from ..models import DetectedObject, RawDetection
from ..track_store import TrackStore
from .base import BehaviourDetector

OVERHANG_RATIO_THRESHOLD = 0.3   # fraction of the base carton's width allowed to overhang before flagging
STABLE_MIN_S = 1.0               # must hold this configuration this long before flagging (ignores mid-placement motion)


class IncorrectStackingDetector(BehaviourDetector):
    behaviour_type = "incorrect_stacking"

    def __init__(self) -> None:
        self._pair_since: Dict[Tuple[int, int], datetime] = {}
        self._reported: Set[Tuple[int, int]] = set()

    def process_frame(
        self,
        frame_id: int,
        timestamp: datetime,
        objects: List[DetectedObject],
        store: TrackStore,
    ) -> List[RawDetection]:
        results: List[RawDetection] = []
        cartons = [o for o in objects if o.cls in PRODUCT_CLASSES]

        active_pairs: Set[Tuple[int, int]] = set()
        for top in cartons:
            for base in cartons:
                if top.track_id == base.track_id:
                    continue
                if not is_resting_on(top, base):
                    continue
                ratio = overhang_ratio(top, base)
                if ratio <= OVERHANG_RATIO_THRESHOLD:
                    continue

                pair = (top.track_id, base.track_id)
                active_pairs.add(pair)
                start = self._pair_since.setdefault(pair, timestamp)
                duration = (timestamp - start).total_seconds()
                if duration >= STABLE_MIN_S and pair not in self._reported:
                    results.append(RawDetection(
                        behaviour_type=self.behaviour_type,
                        object_ids=[top.track_id, base.track_id],
                        frame_id=frame_id,
                        timestamp=timestamp,
                        details={"overhang_ratio": ratio, "duration_s": duration},
                    ))
                    self._reported.add(pair)

        for pair in list(self._pair_since):
            if pair not in active_pairs:
                self._pair_since.pop(pair, None)
                self._reported.discard(pair)

        return results
