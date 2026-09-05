"""
"Rough handling / excessive impact" — behaviour #3, covering two sub-cases
from the challenge doc's bad-practice list:

  (a) a person stepping or standing on a carton (the doc's "stepping or
      standing on cartons" item) — there's no dedicated slot for this in the
      shared behaviour_type enum in the root CLAUDE.md, so it's folded into
      rough_handling here. If the team wants it as its own category, that's
      an enum change and needs to go through /shared first per that file's
      rules — flagging this mapping rather than deciding it unilaterally.
  (b) a carton being jolted or slammed sideways with high speed — deliberately
      horizontal-only so it doesn't double-count the same motion that the
      "dropped" state machine (vertical falls) already owns.

Sub-case (a) approximates "feet" as the bottom slice of a person's bbox
(see geometry.bottom_strip) rather than actual pose keypoints, since the
per-frame schema doesn't document keypoint index/ordering semantics yet.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Set, Tuple

from ..constants import PERSON_CLASS, PRODUCT_CLASSES
from ..geometry import bboxes_overlap, bottom_strip
from ..models import DetectedObject, RawDetection
from ..track_store import TrackStore
from .base import BehaviourDetector

STEP_MIN_DURATION_S = 0.3     # how long a foot must overlap a carton before it counts (ignores brief brushes)
JERK_SPEED_PX_S = 500.0       # horizontal bbox-center speed that counts as a sideways jolt/impact


class RoughHandlingDetector(BehaviourDetector):
    behaviour_type = "rough_handling"

    def __init__(self) -> None:
        self._stepping_since: Dict[Tuple[int, int], datetime] = {}
        self._reported_steps: Set[Tuple[int, int]] = set()
        self._jerking: Set[int] = set()  # track_ids currently above the jerk threshold, to report once per jolt

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

        active_pairs: Set[Tuple[int, int]] = set()
        for p in persons:
            feet = bottom_strip(p)
            for c in cartons:
                if not bboxes_overlap(feet, c.bbox):
                    continue
                pair = (p.track_id, c.track_id)
                active_pairs.add(pair)
                start = self._stepping_since.setdefault(pair, timestamp)
                duration = (timestamp - start).total_seconds()
                if duration >= STEP_MIN_DURATION_S and pair not in self._reported_steps:
                    results.append(RawDetection(
                        behaviour_type=self.behaviour_type,
                        object_ids=[p.track_id, c.track_id],
                        frame_id=frame_id,
                        timestamp=timestamp,
                        details={"cause": "stepping_on_product", "duration_s": duration},
                    ))
                    self._reported_steps.add(pair)

        for pair in list(self._stepping_since):
            if pair not in active_pairs:
                self._stepping_since.pop(pair, None)
                self._reported_steps.discard(pair)

        current_carton_ids = {c.track_id for c in cartons}
        for c in cartons:
            speed = store.horizontal_speed(c.track_id, window=2)
            if speed > JERK_SPEED_PX_S:
                if c.track_id not in self._jerking:
                    self._jerking.add(c.track_id)
                    results.append(RawDetection(
                        behaviour_type=self.behaviour_type,
                        object_ids=[c.track_id],
                        frame_id=frame_id,
                        timestamp=timestamp,
                        details={"cause": "sudden_impact", "peak_speed_px_s": speed},
                    ))
            else:
                self._jerking.discard(c.track_id)
        for tid in list(self._jerking):
            if tid not in current_carton_ids:
                self._jerking.discard(tid)

        return results
