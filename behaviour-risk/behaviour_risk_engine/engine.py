"""
BehaviourEngine — wires per-frame detections through every registered
BehaviourDetector, scores and explains whatever they flag, and hands the
resulting Event to the event sink.

This is the module's single entry point: everything else (detectors,
risk_scoring, explanations, event_sink) is called from here, not from each
other, so the pipeline stays easy to trace end to end.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Callable, Deque, List, Optional, Tuple

from . import explanations, risk_scoring
from .behaviours.base import BehaviourDetector
from .behaviours.dragged import DraggedDetector
from .behaviours.dropped import DroppedDetector
from .behaviours.incorrect_stacking import IncorrectStackingDetector
from .behaviours.no_required_equipment import NoRequiredEquipmentDetector
from .behaviours.outside_designated_area import OutsideDesignatedAreaDetector
from .behaviours.pallet_incorrect_position import PalletIncorrectPositionDetector
from .behaviours.pushed_or_thrown import PushedOrThrownDetector
from .behaviours.rolling import RollingDetector
from .behaviours.rough_handling import RoughHandlingDetector
from .behaviours.stepping_on_product import SteppingOnProductDetector
from .behaviours.strap_misuse import StrapMisuseDetector
from .behaviours.unsafe_loading_sequence import UnsafeLoadingSequenceDetector
from .behaviours.unstable_stacking import UnstableStackingDetector
from .behaviours.wrong_orientation import WrongOrientationDetector
from .event_sink import default_event_sink
from .models import DetectedObject, Event, RawDetection
from .track_stitcher import TrackStitcher
from .track_store import TrackStore

REPEAT_WINDOW_S = 300.0  # 5 minutes — how far back "repeat frequency" looks


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def evidence_path_for(event_id: str) -> str:
    """Matches shared/config.py's evidence_path_for convention without
    importing it directly, since that module creates the evidence directory
    as a side effect on import — this module shouldn't need the real
    filesystem to build a path string."""
    return f"shared/evidence/{event_id}.jpg"


class BehaviourEngine:
    def __init__(
        self,
        bay: str = "bay_1",
        detectors: Optional[List[BehaviourDetector]] = None,
        event_sink: Optional[Callable[[Event], None]] = None,
    ) -> None:
        self.bay = bay
        self.store = TrackStore()
        self.stitcher = TrackStitcher()
        self.detectors: List[BehaviourDetector] = detectors or [
            DroppedDetector(),
            DraggedDetector(),
            RoughHandlingDetector(),
            SteppingOnProductDetector(),
            IncorrectStackingDetector(),
            UnstableStackingDetector(),
            OutsideDesignatedAreaDetector(),
            NoRequiredEquipmentDetector(),
            PalletIncorrectPositionDetector(),
            PushedOrThrownDetector(),
            UnsafeLoadingSequenceDetector(),
            RollingDetector(),
            WrongOrientationDetector(),
            StrapMisuseDetector(),
        ]
        self.sink = event_sink or default_event_sink
        self._event_counter = 0
        self._recent_events: Deque[Tuple[datetime, str]] = deque()

    def process_frame(self, frame: dict) -> List[Event]:
        frame_id = frame["frame_id"]
        timestamp = _parse_timestamp(frame["timestamp"])
        objects = [DetectedObject.from_dict(o) for o in frame["objects"]]
        self.stitcher.stitch(frame_id, objects)  # remap fragmented real track_ids onto one canonical id
        self.store.update(frame_id, timestamp, objects)

        events: List[Event] = []
        for detector in self.detectors:
            for raw in detector.process_frame(frame_id, timestamp, objects, self.store):
                event = self._build_event(raw)
                events.append(event)
                self.sink(event)
        return events

    def _build_event(self, raw: RawDetection) -> Event:
        self._event_counter += 1
        event_id = f"evt_{self._event_counter:05d}"

        repeat_count = self._count_recent(raw.behaviour_type, raw.timestamp)
        self._recent_events.append((raw.timestamp, raw.behaviour_type))

        score = risk_scoring.compute_risk_score(
            behaviour_type=raw.behaviour_type,
            details=raw.details,
            bay=self.bay,
            repeat_count=repeat_count,
        )
        level = risk_scoring.bucket(score)
        explanation = explanations.build_explanation(raw.behaviour_type, raw.details)

        return Event(
            event_id=event_id,
            timestamp=_format_timestamp(raw.timestamp),
            behaviour_type=raw.behaviour_type,
            risk_level=level,
            risk_score=round(score, 3),
            bay=self.bay,
            object_ids=raw.object_ids,
            evidence_frame_path=evidence_path_for(event_id),
            explanation=explanation,
        )

    def _count_recent(self, behaviour_type: str, now: datetime) -> int:
        while self._recent_events and (now - self._recent_events[0][0]).total_seconds() > REPEAT_WINDOW_S:
            self._recent_events.popleft()
        return sum(1 for _, b in self._recent_events if b == behaviour_type)
