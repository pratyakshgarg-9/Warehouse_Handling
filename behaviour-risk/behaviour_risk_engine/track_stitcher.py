"""
Lightweight track re-identification: remaps a newly-appeared track_id onto
a recently-lost one of the same class, close by, so a real detector's
identity churn doesn't fragment one physical object into many track_ids.

Built after validating against Member 1's real pipeline output (2026-09-07):
every duration/distance-gated behaviour here is keyed by track_id, but a
real clip can reassign a brand-new id almost every time an object is
briefly occluded or drops below confidence — one clip produced 56 distinct
carton track_ids in 451 frames. `dragged`, `incorrect_stacking`, and every
other behaviour needing sustained signal on one id never had a chance to
accumulate it. This is the fix: engine.py runs every frame's objects
through this before they reach TrackStore or any detector, so downstream
code only ever sees the stitched (canonical) id.

Matching is deliberately conservative — same class, small gap, small
displacement — to keep the false-merge risk (stitching together two
different objects that happen to be nearby) low. It will still miss a
genuine re-identification across a big gap or fast motion, and it can
still wrongly merge two different objects of the same class that swap
places during an occlusion — neither failure mode is silent-safe by
construction, just judged the better trade-off against doing nothing.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

MAX_GAP_FRAMES = 30            # ~1s at 30fps — longer than this, treat it as a genuinely new object
BASE_DISTANCE_PX = 40.0        # tolerance even for a same-frame/near-zero gap (detection noise)
DISTANCE_PER_GAP_FRAME_PX = 8.0  # generous per-frame allowance for real motion during the gap


class TrackStitcher:
    def __init__(
        self,
        max_gap_frames: int = MAX_GAP_FRAMES,
        base_distance_px: float = BASE_DISTANCE_PX,
        distance_per_gap_frame_px: float = DISTANCE_PER_GAP_FRAME_PX,
    ) -> None:
        self._max_gap_frames = max_gap_frames
        self._base_distance_px = base_distance_px
        self._distance_per_gap_frame_px = distance_per_gap_frame_px

        self._remap: Dict[int, int] = {}  # raw track_id -> canonical id
        # canonical id -> (last_frame_id, last_center, cls)
        self._canonical_state: Dict[int, Tuple[int, Tuple[float, float], str]] = {}

    def stitch(self, frame_id: int, objects: List) -> None:
        """Rewrites `track_id` on each object in place to its canonical id.

        Two passes: first, any raw id we've already mapped before claims
        its canonical id immediately (sticky) — this reserves it so a
        *different*, still-unmapped raw id detected in this same frame
        can't also match onto it. Without that reservation, two genuinely
        different objects present in the same frame (e.g. two boxes) could
        both independently satisfy _find_match against the same recently-
        seen canonical id, merging two different physical objects into one
        and corrupting its position history with an alternating jump every
        frame — confirmed happening on a real clip with multiple boxes in
        frame at once before this fix.
        """
        claimed_this_frame = set()
        for obj in objects:
            if obj.track_id in self._remap:
                claimed_this_frame.add(self._remap[obj.track_id])

        for obj in objects:
            raw_id = obj.track_id
            canonical = self._remap.get(raw_id)

            if canonical is None:
                canonical = self._find_match(frame_id, obj.center, obj.cls, exclude=claimed_this_frame)
                if canonical is None:
                    canonical = raw_id
                self._remap[raw_id] = canonical
                claimed_this_frame.add(canonical)

            obj.track_id = canonical
            self._canonical_state[canonical] = (frame_id, obj.center, obj.cls)

    def _find_match(
        self,
        frame_id: int,
        center: Tuple[float, float],
        cls: str,
        exclude: "set[int]" = frozenset(),
    ) -> Optional[int]:
        best_id = None
        best_gap = None
        for canonical_id, (last_frame, last_center, last_cls) in self._canonical_state.items():
            if canonical_id in exclude:
                continue
            if last_cls != cls:
                continue
            gap = frame_id - last_frame
            if gap <= 0 or gap > self._max_gap_frames:
                continue
            allowed_distance = self._base_distance_px + self._distance_per_gap_frame_px * gap
            distance = ((center[0] - last_center[0]) ** 2 + (center[1] - last_center[1]) ** 2) ** 0.5
            if distance > allowed_distance:
                continue
            if best_gap is None or gap < best_gap:
                best_gap = gap
                best_id = canonical_id
        return best_id
