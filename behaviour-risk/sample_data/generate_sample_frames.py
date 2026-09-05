"""
Synthetic per-frame detection stream, standing in for Member 1's real
output until cv-pipeline publishes one (it's still just a requirements.txt
as of 2026-09-05). Frames match the schema in the root CLAUDE.md exactly, so
swapping this generator for a real stream later is a one-line change in
whatever calls BehaviourEngine.process_frame.

One short, scripted scenario per implemented behaviour, concatenated into
a single continuous timeline (as if they were separate moments in one
shift recording): dropped, dragged, rough_handling, stepping_on_product,
incorrect_stacking, unstable_stacking, outside_designated_area,
no_required_equipment, pallet_incorrect_position, pushed_or_thrown,
unsafe_loading_sequence, rolling, wrong_orientation, strap_misuse.
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
    for _ in range(10):
        frames.append(_frame(frame_id, t, [_obj(101, "carton", [300, 300, 360, carton_y])]))
        frame_id += 1
        t += FRAME_DT
    return frames, frame_id, t


def _dragged_scenario(frame_id: int, t: datetime) -> tuple:
    """Carton 102 stays at floor height while person 201 moves it sideways.
    Person stands just beside the carton (not over it) so this scenario
    doesn't also trip the stepping_on_product check."""
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
    """Carton 106 gets jolted sideways by ~80px in a single frame while
    person 203 is in contact — rough_handling's sudden_impact sub-rule.
    Contact only lasts a few frames so this doesn't also read as a
    sustained "dragged" episode."""
    frames = []
    y = 500.0
    x = 500.0
    for i in range(5):
        if i == 3:
            x = 580.0  # sudden jolt
        carton_bbox = [x, y - 40, x + 60, y]
        person_bbox = [x - 50, y - 150, x - 2, y]
        frames.append(_frame(frame_id, t, [
            _obj(106, "carton", carton_bbox),
            _obj(203, "person", person_bbox),
        ]))
        frame_id += 1
        t += FRAME_DT
    # person moves away; carton stays put (contact must end well before dragged's 0.4s threshold)
    for _ in range(5):
        carton_bbox = [x, y - 40, x + 60, y]
        frames.append(_frame(frame_id, t, [_obj(106, "carton", carton_bbox)]))
        frame_id += 1
        t += FRAME_DT
    return frames, frame_id, t


def _stepping_on_product_scenario(frame_id: int, t: datetime) -> tuple:
    """Person 202 stands on carton 103 for a sustained stretch."""
    frames = []
    carton_bbox = [400, 460, 460, 500]
    person_bbox = [405, 350, 455, 500]  # bottom of person's bbox overlaps the carton's bbox (feet on it)
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
    top_bbox = [260, 340, 380, 400]   # overhangs ~40% of the base's width to the right
    for _ in range(35):  # 35 frames @ 30fps = ~1.17s, past the 1.0s stability threshold
        frames.append(_frame(frame_id, t, [
            _obj(104, "carton", base_bbox),
            _obj(105, "carton", top_bbox),
        ]))
        frame_id += 1
        t += FRAME_DT
    return frames, frame_id, t


def _unstable_stacking_scenario(frame_id: int, t: datetime) -> tuple:
    """Carton 109 rests squarely on carton 108 (no overhang) but the
    combined stack is more than 1.5x taller than the narrow base — a
    toppling risk that incorrect_stacking's overhang check wouldn't catch."""
    frames = []
    base_bbox = [300, 400, 360, 460]  # width 60, height 60
    top_bbox = [300, 300, 360, 400]   # directly above, height 100 -> stack height 160, ratio 2.67
    for _ in range(35):
        frames.append(_frame(frame_id, t, [
            _obj(108, "carton", base_bbox),
            _obj(109, "carton", top_bbox),
        ]))
        frame_id += 1
        t += FRAME_DT
    return frames, frame_id, t


def _outside_designated_area_scenario(frame_id: int, t: datetime) -> tuple:
    """Carton 116 comes to rest well outside the bay's designated
    placement zone (see outside_designated_area.DESIGNATED_AREA_BBOX)."""
    frames = []
    bbox = [880.0, 280.0, 940.0, 320.0]  # center (910, 300) — past the zone's x2=700
    for _ in range(35):
        frames.append(_frame(frame_id, t, [_obj(116, "carton", bbox)]))
        frame_id += 1
        t += FRAME_DT
    return frames, frame_id, t


def _no_required_equipment_scenario(frame_id: int, t: datetime) -> tuple:
    """Carton 115 is genuinely lifted clear of the floor, then carried a
    long distance by hand with no trolley anywhere nearby. Lifting first
    (rather than holding a constant height throughout) exercises dragged's
    disqualify-on-lift fix — this episode must NOT also read as a drag."""
    frames = []
    floor_y = 520.0
    carried_y = 340.0
    x = 50.0
    person_dx = -50.0

    for _ in range(3):  # initial floor contact — baseline forms here
        carton_bbox = [x, floor_y - 40, x + 60, floor_y]
        person_bbox = [x + person_dx, floor_y - 200, x + person_dx + 48, floor_y]
        frames.append(_frame(frame_id, t, [_obj(115, "carton", carton_bbox), _obj(204, "person", person_bbox)]))
        frame_id += 1
        t += FRAME_DT

    for y2 in (440.0, carried_y):  # lift clear of the floor over a couple of frames
        carton_bbox = [x, y2 - 40, x + 60, y2]
        person_bbox = [x + person_dx, y2 - 200, x + person_dx + 48, y2]
        frames.append(_frame(frame_id, t, [_obj(115, "carton", carton_bbox), _obj(204, "person", person_bbox)]))
        frame_id += 1
        t += FRAME_DT

    for _ in range(45):  # long carry at the lifted height, no trolley in the frame
        carton_bbox = [x, carried_y - 40, x + 60, carried_y]
        person_bbox = [x + person_dx, carried_y - 200, x + person_dx + 48, carried_y]
        frames.append(_frame(frame_id, t, [_obj(115, "carton", carton_bbox), _obj(204, "person", person_bbox)]))
        frame_id += 1
        t += FRAME_DT
        x += 10.0  # 450px of travel, comfortably past the 200px threshold

    return frames, frame_id, t


def _pallet_incorrect_position_scenario(frame_id: int, t: datetime) -> tuple:
    """Carton 114 rests on pallet 301 but overhangs its footprint on both
    sides — the product doesn't fit the pallet it's on."""
    frames = []
    pallet_bbox = [200, 460, 320, 500]  # width 120
    carton_bbox = [180, 400, 340, 460]  # width 160, overhangs both edges
    for _ in range(35):
        frames.append(_frame(frame_id, t, [
            _obj(301, "pallet", pallet_bbox),
            _obj(114, "carton", carton_bbox),
        ]))
        frame_id += 1
        t += FRAME_DT
    return frames, frame_id, t


def _pushed_or_thrown_scenario(frame_id: int, t: datetime) -> tuple:
    """Carton 110 covers a large distance in a single frame with nobody in
    contact — consistent with being pushed or thrown rather than carried."""
    frames = []
    positions = [100.0, 100.0, 260.0, 260.0, 260.0]
    for x in positions:
        bbox = [x, 300, x + 60, 340]
        frames.append(_frame(frame_id, t, [_obj(110, "carton", bbox)]))
        frame_id += 1
        t += FRAME_DT
    return frames, frame_id, t


def _unsafe_loading_sequence_scenario(frame_id: int, t: datetime) -> tuple:
    """Three products moving at once for a sustained stretch — an
    uncoordinated, non-sequential handling pattern rather than one product
    being staged at a time."""
    frames = []
    x1, x2, x3 = 50.0, 250.0, 450.0
    for _ in range(35):
        objs = [
            _obj(111, "carton", [x1, 200, x1 + 60, 240]),
            _obj(112, "carton", [x2, 200, x2 + 60, 240]),
            _obj(113, "carton", [x3, 200, x3 + 60, 240]),
        ]
        frames.append(_frame(frame_id, t, objs))
        frame_id += 1
        t += FRAME_DT
        x1 += 8.0
        x2 += 8.0
        x3 += 8.0
    return frames, frame_id, t


def _rolling_scenario(frame_id: int, t: datetime) -> tuple:
    """Carton 117 is rolled along the floor — its bbox aspect ratio wobbles
    (tips edge-over-edge) as it travels, unlike dragged's steady slide.
    No person track is included, so dragged/no_required_equipment (which
    both require person contact) can't cross-trigger here."""
    frames = []
    x = 100.0
    y_center = 480.0
    shapes = [(60.0, 40.0), (40.0, 60.0)] * 15  # enough frames for both the distance and duration thresholds to be met
    for w, h in shapes:
        bbox = [x, y_center - h / 2, x + w, y_center + h / 2]
        frames.append(_frame(frame_id, t, [_obj(117, "carton", bbox)]))
        frame_id += 1
        t += FRAME_DT
        x += 8.0
    return frames, frame_id, t


def _wrong_orientation_scenario(frame_id: int, t: datetime) -> tuple:
    """Cupboard 118 is kept lying on its side (wide bbox) instead of
    upright, sustained long enough to be a real placement rather than a
    momentary tilt while being moved."""
    frames = []
    bbox = [500.0, 300.0, 700.0, 360.0]  # width 200, height 60 -> ratio 3.33
    for _ in range(35):
        frames.append(_frame(frame_id, t, [_obj(118, "cupboard", bbox)]))
        frame_id += 1
        t += FRAME_DT
    return frames, frame_id, t


def _strap_misuse_scenario(frame_id: int, t: datetime) -> tuple:
    """Carton 119 is being handled by person 205 with a strap 401
    overlapping it — carried via its packaging strap rather than a proper
    handling point. Static (no movement), so this doesn't also read as a
    dragged/no_required_equipment episode, which both need real distance."""
    frames = []
    carton_bbox = [600.0, 300.0, 660.0, 360.0]
    person_bbox = [560.0, 250.0, 610.0, 400.0]
    strap_bbox = [605.0, 280.0, 655.0, 305.0]
    for _ in range(20):
        frames.append(_frame(frame_id, t, [
            _obj(119, "carton", carton_bbox),
            _obj(205, "person", person_bbox),
            _obj(401, "strap", strap_bbox),
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
        _stepping_on_product_scenario,
        _incorrect_stacking_scenario,
        _unstable_stacking_scenario,
        _outside_designated_area_scenario,
        _no_required_equipment_scenario,
        _pallet_incorrect_position_scenario,
        _pushed_or_thrown_scenario,
        _unsafe_loading_sequence_scenario,
        _rolling_scenario,
        _wrong_orientation_scenario,
        _strap_misuse_scenario,
    ):
        frames, frame_id, t = scenario(frame_id, t)
        all_frames.extend(frames)

    return all_frames
