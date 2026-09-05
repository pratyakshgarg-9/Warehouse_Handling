"""
"Rolling cartons or mattresses" instead of carrying or using proper
equipment — a bad practice from the challenge doc's table, and something
that actually shows up twice in the real demo footage ("Rolling and
dragging on wet floor", "Rolling and dropping carton").

The per-frame schema has no object-orientation field, so there's no direct
"is this spinning" signal. Approximated instead by watching for the bbox's
aspect ratio wobbling (tipping edge-over-edge alternates between a
tall-narrow and short-wide silhouette) while the object also travels a
real distance — as opposed to "dragged", where the bbox shape stays
essentially constant as it slides.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from ..constants import PRODUCT_CLASSES
from ..models import DetectedObject, RawDetection
from ..track_store import TrackStore
from .base import BehaviourDetector

WOBBLE_WINDOW_FRAMES = 15
ASPECT_RATIO_WOBBLE_RATIO = 0.35   # (max-min)/mean aspect-ratio swing over the window that counts as "wobbling"
MIN_ROLL_DISTANCE_PX = 60.0
MIN_ROLL_DURATION_S = 0.4


class RollingDetector(BehaviourDetector):
    behaviour_type = "rolling"

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

            window = list(store.history(obj.track_id))[-WOBBLE_WINDOW_FRAMES:]
            st = self._state.setdefault(obj.track_id, {"since": None, "reported": False})

            if len(window) < 4:
                continue

            ratios = [s.obj.width / s.obj.height for s in window if s.obj.height > 0]
            if not ratios:
                continue
            mean_ratio = sum(ratios) / len(ratios)
            if mean_ratio <= 0:
                continue
            wobble = (max(ratios) - min(ratios)) / mean_ratio
            distance = store.horizontal_displacement(obj.track_id, window=WOBBLE_WINDOW_FRAMES)

            qualifies = wobble >= ASPECT_RATIO_WOBBLE_RATIO and distance >= MIN_ROLL_DISTANCE_PX
            if not qualifies:
                st["since"] = None
                st["reported"] = False
                continue

            if st["since"] is None:
                st["since"] = timestamp
            duration = (timestamp - st["since"]).total_seconds()
            if duration >= MIN_ROLL_DURATION_S and not st["reported"]:
                st["reported"] = True
                results.append(RawDetection(
                    behaviour_type=self.behaviour_type,
                    object_ids=[obj.track_id],
                    frame_id=frame_id,
                    timestamp=timestamp,
                    details={"aspect_ratio_wobble": wobble, "distance_px": distance},
                ))

        for tid in list(self._state):
            if tid not in current_ids:
                self._state.pop(tid, None)

        return results
