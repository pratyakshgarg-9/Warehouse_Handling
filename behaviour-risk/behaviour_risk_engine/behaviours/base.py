"""
Base interface for a single behaviour's rule-based state machine.

Each detector owns exactly one behaviour_type from the shared enum (root
CLAUDE.md). It never touches the DB or builds a full Event itself — it just
recognizes when its behaviour has completed on the current frame and hands
back the raw facts; engine.py turns that into a full Event (risk score,
explanation, event_id).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List

from ..models import DetectedObject, RawDetection
from ..track_store import TrackStore


class BehaviourDetector(ABC):
    behaviour_type: str

    @abstractmethod
    def process_frame(
        self,
        frame_id: int,
        timestamp: datetime,
        objects: List[DetectedObject],
        store: TrackStore,
    ) -> List[RawDetection]:
        """Return zero or more raw detections completed on this frame."""
        raise NotImplementedError
