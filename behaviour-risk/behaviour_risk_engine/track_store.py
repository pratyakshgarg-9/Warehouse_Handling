"""
Rolling per-track_id history of recent detections, across frames.

Behaviour detectors ask this store what a track has been doing recently
(velocity, displacement, duration) instead of each keeping their own frame
buffers — keeps the detectors themselves as small, readable state machines.
"""

from __future__ import annotations

import math
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, List, Optional

from .models import DetectedObject

DEFAULT_HISTORY_LEN = 60  # ~2s at 30fps — the longest lookback any detector uses is no_required_equipment's 45-frame carry window
MAX_STEP_GAP_S = 0.2      # ~6 frames at 30fps — see _contiguous_tail


@dataclass
class TrackSnapshot:
    timestamp: datetime
    obj: DetectedObject


class TrackStore:
    def __init__(self, history_len: int = DEFAULT_HISTORY_LEN, stale_after_frames: int = 15):
        self._history: Dict[int, Deque[TrackSnapshot]] = defaultdict(lambda: deque(maxlen=history_len))
        self._last_seen_frame: Dict[int, int] = {}
        self._stale_after_frames = stale_after_frames

    def update(self, frame_id: int, timestamp: datetime, objects: List[DetectedObject]) -> None:
        for obj in objects:
            self._history[obj.track_id].append(TrackSnapshot(timestamp, obj))
            self._last_seen_frame[obj.track_id] = frame_id
        self._prune(frame_id)

    def _prune(self, frame_id: int) -> None:
        stale = [
            tid for tid, last in self._last_seen_frame.items()
            if frame_id - last > self._stale_after_frames
        ]
        for tid in stale:
            self._history.pop(tid, None)
            self._last_seen_frame.pop(tid, None)

    def history(self, track_id: int) -> Deque[TrackSnapshot]:
        return self._history.get(track_id, deque())

    def latest(self, track_id: int) -> Optional[DetectedObject]:
        h = self._history.get(track_id)
        return h[-1].obj if h else None

    def duration_seconds(self, track_id: int) -> float:
        h = self._history.get(track_id)
        if not h or len(h) < 2:
            return 0.0
        return (h[-1].timestamp - h[0].timestamp).total_seconds()

    def _contiguous_tail(self, snapshots: List[TrackSnapshot]) -> List[TrackSnapshot]:
        """The trailing run of snapshots with no unusually large gap between
        consecutive entries. Velocity/speed math needs this: TrackStitcher
        (engine.py) remaps a real detector's fragmented track_ids onto one
        canonical id, so two adjacent stored snapshots can span a real gap
        of many missed frames — dividing that positional jump by the
        (correctly large) elapsed time gives a number that looks like a
        velocity reading but isn't actually measuring a sudden motion, just
        unknown drift over an unknown span. Excluding any step wider than
        MAX_STEP_GAP_S keeps genuine sudden-motion detection intact while
        refusing to manufacture a jolt out of a stitched-together gap.
        horizontal_displacement deliberately does NOT use this — bridging
        that same gap for cumulative distance is the whole point of
        stitching a fragmented track back together."""
        if len(snapshots) < 2:
            return snapshots
        cut = 0
        for i in range(len(snapshots) - 1, 0, -1):
            gap = (snapshots[i].timestamp - snapshots[i - 1].timestamp).total_seconds()
            if gap > MAX_STEP_GAP_S:
                cut = i
                break
        return snapshots[cut:]

    def vertical_velocity(self, track_id: int, window: int = 5) -> float:
        """Pixels/sec of the bbox bottom edge over the last `window` snapshots.
        Positive = moving down (falling toward the floor in image coordinates)."""
        h = self.history(track_id)
        if len(h) < 2:
            return 0.0
        recent = self._contiguous_tail(list(h)[-window:])
        if len(recent) < 2:
            return 0.0
        dt = (recent[-1].timestamp - recent[0].timestamp).total_seconds()
        if dt <= 0:
            return 0.0
        dy = recent[-1].obj.y2 - recent[0].obj.y2
        return dy / dt

    def horizontal_displacement(self, track_id: int, window: int = 10) -> float:
        """Absolute pixel displacement of the bbox center's x-coordinate over
        the last `window` snapshots (not net velocity — total movement)."""
        h = self.history(track_id)
        if len(h) < 2:
            return 0.0
        recent = list(h)[-window:]
        cx0 = recent[0].obj.center[0]
        cx1 = recent[-1].obj.center[0]
        return abs(cx1 - cx0)

    def speed(self, track_id: int, window: int = 3) -> float:
        """Combined pixels/sec of the bbox center over the last `window`
        snapshots — used to catch sideways jolts that a purely vertical
        velocity check (vertical_velocity) would miss."""
        h = self.history(track_id)
        if len(h) < 2:
            return 0.0
        recent = self._contiguous_tail(list(h)[-window:])
        if len(recent) < 2:
            return 0.0
        dt = (recent[-1].timestamp - recent[0].timestamp).total_seconds()
        if dt <= 0:
            return 0.0
        cx0, cy0 = recent[0].obj.center
        cx1, cy1 = recent[-1].obj.center
        return math.hypot(cx1 - cx0, cy1 - cy0) / dt

    def horizontal_speed(self, track_id: int, window: int = 3) -> float:
        """Pixels/sec of the bbox center's x-coordinate only (unsigned) —
        deliberately excludes vertical motion so a straight-down drop (owned
        by the "dropped" behaviour) doesn't also register as a sideways jolt."""
        h = self.history(track_id)
        if len(h) < 2:
            return 0.0
        recent = self._contiguous_tail(list(h)[-window:])
        if len(recent) < 2:
            return 0.0
        dt = (recent[-1].timestamp - recent[0].timestamp).total_seconds()
        if dt <= 0:
            return 0.0
        dx = recent[-1].obj.center[0] - recent[0].obj.center[0]
        return abs(dx) / dt
