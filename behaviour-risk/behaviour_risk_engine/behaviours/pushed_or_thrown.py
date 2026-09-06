"""
"Material pushed or thrown" — behaviour #8: a carton moving at high speed
with nobody currently in contact with it — i.e. already released/in-flight,
as opposed to rough_handling's "jolted while still being handled" (which
requires contact) or dragged's sustained floor-level slide (which requires
continuous contact throughout).

SPEED_WINDOW and CONSECUTIVE_FRAMES_REQUIRED were widened after testing
against Member 1's real cv-pipeline output (2026-09-07): a real detector's
bbox jitters several px frame-to-frame even when nothing is actually
moving, and at 30fps that jitter alone crosses a naive 2-3 frame speed
threshold constantly (41 of 159 frames in one real clip, mostly on a
single stationary-ish track). Averaging over a longer window and requiring
the elevated speed to hold for 2 consecutive frames collapsed that same
clip down to 3 tight 3-frame clusters — a signature much more consistent
with real, sustained motion than single-frame noise.

That wider window creates a second problem though: `horizontal_speed`'s
net-displacement-over-the-window calculation keeps reflecting a real jolt
for several frames after it happened, even once contact has actually
ended — so a jolt that occurred *while* a person was holding the carton
(rough_handling's case) would still read as high-speed for a few frames
after they let go, double-counting the same event as "thrown" too. Fixed
with a small cooldown: contact must have ended at least SPEED_WINDOW
frames ago before this detector will even look at the speed, so the
window has fully "flushed" past any contact-era motion.
"""

from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Set

from ..constants import PERSON_CLASS, PRODUCT_CLASSES
from ..geometry import bboxes_overlap
from ..models import DetectedObject, RawDetection
from ..track_store import TrackStore
from .base import BehaviourDetector

THROWN_SPEED_PX_S = 400.0
CONTACT_PAD_PX = 20.0
SPEED_WINDOW = 6
CONSECUTIVE_FRAMES_REQUIRED = 2


class PushedOrThrownDetector(BehaviourDetector):
    behaviour_type = "pushed_or_thrown"

    def __init__(self) -> None:
        self._streak: Dict[int, int] = {}
        self._reported: Set[int] = set()
        self._frames_since_contact: Dict[int, int] = {}

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
        current_ids = {c.track_id for c in cartons}

        for c in cartons:
            in_contact = any(bboxes_overlap(c.bbox, p.bbox, pad=CONTACT_PAD_PX) for p in persons)
            if in_contact:
                self._frames_since_contact[c.track_id] = 0
            else:
                self._frames_since_contact[c.track_id] = self._frames_since_contact.get(c.track_id, SPEED_WINDOW) + 1

            cooled_down = self._frames_since_contact[c.track_id] >= SPEED_WINDOW
            speed = store.horizontal_speed(c.track_id, window=SPEED_WINDOW)
            qualifies = cooled_down and speed > THROWN_SPEED_PX_S

            if not qualifies:
                self._streak[c.track_id] = 0
                self._reported.discard(c.track_id)
                continue

            self._streak[c.track_id] = self._streak.get(c.track_id, 0) + 1
            if self._streak[c.track_id] >= CONSECUTIVE_FRAMES_REQUIRED and c.track_id not in self._reported:
                self._reported.add(c.track_id)
                results.append(RawDetection(
                    behaviour_type=self.behaviour_type,
                    object_ids=[c.track_id],
                    frame_id=frame_id,
                    timestamp=timestamp,
                    details={"peak_speed_px_s": speed},
                ))

        for tid in list(self._reported):
            if tid not in current_ids:
                self._reported.discard(tid)
        for tid in list(self._streak):
            if tid not in current_ids:
                self._streak.pop(tid, None)
        for tid in list(self._frames_since_contact):
            if tid not in current_ids:
                self._frames_since_contact.pop(tid, None)

        return results
