"""
Data model for the behaviour-risk module.

DetectedObject mirrors Member 1's per-frame output schema exactly (see the
root CLAUDE.md's "Per-frame detection/tracking output" section). Event
mirrors the event schema there too (Member 3's event store, Member 4's
dashboard) — any change to either shape must go through /shared and be
flagged to the team per that file's rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class DetectedObject:
    track_id: int
    cls: str  # renamed from "class" (a reserved word) — see from_dict/to_dict
    bbox: List[float]  # [x1, y1, x2, y2]
    confidence: float
    keypoints: Optional[List[List[float]]] = None  # person only: [[x, y, conf], ...]

    @classmethod
    def from_dict(cls, d: dict) -> "DetectedObject":
        return cls(
            track_id=d["track_id"],
            cls=d["class"],
            bbox=list(d["bbox"]),
            confidence=d["confidence"],
            keypoints=d.get("keypoints"),
        )

    @property
    def x1(self) -> float:
        return self.bbox[0]

    @property
    def y1(self) -> float:
        return self.bbox[1]

    @property
    def x2(self) -> float:
        return self.bbox[2]

    @property
    def y2(self) -> float:
        return self.bbox[3]

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def center(self) -> Tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


@dataclass
class RawDetection:
    """What a BehaviourDetector emits — engine.py turns this into a full Event
    (risk score, explanation, event_id) so detectors never touch the schema
    or the DB directly."""

    behaviour_type: str
    object_ids: List[int]
    frame_id: int
    timestamp: object  # datetime; kept loosely typed to avoid a circular import
    details: Dict


@dataclass
class Event:
    event_id: str
    timestamp: str  # ISO 8601 UTC, e.g. "2026-09-06T10:15:04Z"
    behaviour_type: str
    risk_level: str
    risk_score: float
    bay: str
    object_ids: List[int]
    evidence_frame_path: str
    explanation: str

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "behaviour_type": self.behaviour_type,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "bay": self.bay,
            "object_ids": self.object_ids,
            "evidence_frame_path": self.evidence_frame_path,
            "explanation": self.explanation,
        }
