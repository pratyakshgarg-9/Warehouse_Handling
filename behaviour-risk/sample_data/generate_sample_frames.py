"""
Synthetic per-frame detection stream, standing in for Member 1's real
output until cv-pipeline publishes one (it's still just a requirements.txt
as of 2026-09-05). Frames match the schema in the root CLAUDE.md exactly, so
swapping this generator for a real stream later is a one-line change in
whatever calls BehaviourEngine.process_frame.

Four short, scripted scenarios are concatenated into one continuous
timeline (as if they were four separate moments in one shift recording),
one per behaviour implemented so far: dropped, dragged, rough_handling
(stepping-on-product), incorrect_stacking.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

FPS = 30
FRAME_DT = timedelta(seconds=1.0 / FPS)
START_TIME = datetime(2026, 9, 5, 10, 0, 0, tzinfo=timezone.utc)


def _format_timestamp(timestamp: datetime) -> str:
    """ISO 8601 UTC with millisecond precision. The root CLAUDE.md's example
    ("2026-09-06T10:15:03Z") only shows whole seconds, but at 30fps that
    resolution can't distinguish consecutive frames — velocity/duration math
    needs sub-second precision. Confirm this assumption once Member 1
    publishes their real per-frame stream (Sep 6 handoff)."""
    return timestamp.strftime("%Y-%m-%dT%H:%M:%S.") + f"{timestamp.microsecond // 1000:03d}Z"


def _frame(frame_id: int, timestamp: datetime, objects: List[dict]) -> dict:
    return {
        "frame_id": frame_id,
        "timestamp": _format_timestamp(timestamp),
        "objects": objects,
    }


def _obj(track_id: int, cls: str, bbox: List[float], confidence: float = 0.9) -> dict:
    return {"track_id": track_id, "class": cls, "bbox": bbox, "confidence": confidence}


def _dropped_scenario(frame_id: int, t: datetime) -> tuple:
    """Carton 101 is held steady, falls fast over a few frames, then settles."""
    frames = []
    carton_y = 340.0  # bbox bottom edge, held at waist height
    # held steady
    for _ in range(5):
        frames.append(_frame(frame_id, t, [_obj(101, "carton", [300, 300, 360, carton_y])]))
        frame_id += 1
        t += FRAME_DT
    # rapid fall: bottom edge drops ~180px over 4 frames (~1350px/s, well past the 300px/s threshold)
    for step in range(1, 5):
        carton_y = 340.0 + step * 45.0
        frames.append(_frame(frame_id, t, [_obj(101, "carton", [300, 300, 360, carton_y])]))
        frame_id += 1
        t += FRAME_DT
    # settled on the floor
    for _ in range(10):
        frames.append(_frame(frame_id, t, [_obj(101, "carton", [300, 300, 360, carton_y])]))
        frame_id += 1
        t += FRAME_DT
    return frames, frame_id, t


def _dragged_scenario(frame_id: int, t: datetime) -> tuple:
    """Carton 102 stays at floor height while person 201 moves it sideways.
    Person stands just beside the carton (not over it) so this scenario
    doesn't also trip the rough_handling "stepping on product" check."""
    frames = []
    floor_y = 520.0
    x = 100.0
    for _ in range(20):
        carton_bbox = [x, floor_y - 40, x + 60, floor_y]
        person_bbox = [x - 50, floor_y - 150, x - 2, floor_y]
        frames.append(_frame(frame_id, t, [
            _obj(102, "carton", carton_bbox),
            _obj(201, "person", person_bbox),
        ]))
        frame_id += 1
        t += FRAME_DT
        x += 6.0  # ~120px of horizontal travel over the scenario, well past the 60px threshold
    return frames, frame_id, t


def _rough_handling_scenario(frame_id: int, t: datetime) -> tuple:
    """Person 202 stands on carton 103 for a sustained stretch."""
    frames = []
    carton_bbox = [400, 460, 460, 500]
    # person's bbox bottom sits inside/overlapping the carton's bbox (feet on the carton)
    person_bbox = [405, 350, 455, 500]
    for _ in range(15):
        frames.append(_frame(frame_id, t, [
            _obj(103, "carton", carton_bbox),
            _obj(202, "person", person_bbox),
        ]))
        frame_id += 1
        t += FRAME_DT
    return frames, frame_id, t


def _incorrect_stacking_scenario(frame_id: int, t: datetime) -> tuple:
    """Carton 105 rests on carton 104 (base), overhanging its footprint by
    more than the configured threshold, held for long enough to be flagged."""
    frames = []
    base_bbox = [200, 400, 320, 460]  # width 120
    # top carton's footprint overhangs ~40% of the base's width to the right
    top_bbox = [260, 340, 380, 400]
    for _ in range(35):  # 35 frames @ 30fps = ~1.17s, past the 1.0s stability threshold
        frames.append(_frame(frame_id, t, [
            _obj(104, "carton", base_bbox),
            _obj(105, "carton", top_bbox),
        ]))
        frame_id += 1
        t += FRAME_DT
    return frames, frame_id, t


def generate_sample_frames() -> List[Dict]:
    frame_id = 1
    t = START_TIME
    all_frames: List[Dict] = []

    for scenario in (
        _dropped_scenario,
        _dragged_scenario,
        _rough_handling_scenario,
        _incorrect_stacking_scenario,
    ):
        frames, frame_id, t = scenario(frame_id, t)
        all_frames.extend(frames)

    return all_frames
