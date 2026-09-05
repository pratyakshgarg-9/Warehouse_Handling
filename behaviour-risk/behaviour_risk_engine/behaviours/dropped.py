"""
"Product dropped" — behaviour #1: a carton undergoes a rapid, uncontrolled
fall (bottom edge moving down fast) and then comes to rest, rather than
being lowered under control.

Per-track state machine: idle -> falling -> (settled -> report if the fall
was big enough to count, otherwise just idle again).

Thresholds below are v1 guesses (no calibrated footage yet) — tune once
Member 1's real detection stream is wired in (Sep 6-7 per the roadmap).
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from ..constants import PRODUCT_CLASSES
from ..models import DetectedObject, RawDetection
from ..track_store import TrackStore
from .base import BehaviourDetector

FALL_VELOCITY_PX_S = 300.0     # bottom-edge downward speed that counts as "falling", not lowering
SETTLE_VELOCITY_PX_S = 40.0    # speed below which the object is considered to have stopped moving
MIN_FALL_DISPLACEMENT_PX = 25.0  # ignore tiny jitter that crosses the fall threshold for an instant


class DroppedDetector(BehaviourDetector):
    behaviour_type = "dropped"

    def __init__(self) -> None:
        self._state: Dict[int, dict] = {}

    def process_frame(
        self,
        frame_id: int,
        timestamp: datetime,
        objects: List[DetectedObject],
        store: TrackStore,
    ) -> List[RawDetection]:
        results: List[RawDetection] = []
        current_ids = set()

        for obj in objects:
            if obj.cls not in PRODUCT_CLASSES:
                continue
            current_ids.add(obj.track_id)

            vy = store.vertical_velocity(obj.track_id, window=3)
            st = self._state.setdefault(obj.track_id, {"phase": "idle", "start_y2": None, "start_time": None})

            if st["phase"] == "idle":
                if vy > FALL_VELOCITY_PX_S:
                    st["phase"] = "falling"
                    st["start_y2"] = obj.y2
                    st["start_time"] = timestamp
            elif st["phase"] == "falling":
                if abs(vy) < SETTLE_VELOCITY_PX_S:
                    displacement = obj.y2 - st["start_y2"]
                    duration = (timestamp - st["start_time"]).total_seconds()
                    if displacement > MIN_FALL_DISPLACEMENT_PX:
                        results.append(RawDetection(
                            behaviour_type=self.behaviour_type,
                            object_ids=[obj.track_id],
                            frame_id=frame_id,
                            timestamp=timestamp,
                            details={"drop_displacement_px": displacement, "fall_duration_s": duration},
                        ))
                    st["phase"] = "idle"
                    st["start_y2"] = None
                    st["start_time"] = None

        for tid in list(self._state):
            if tid not in current_ids:
                self._state.pop(tid, None)

        return results
