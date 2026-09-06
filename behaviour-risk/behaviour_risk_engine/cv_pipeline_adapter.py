"""
Translates Member 1's ACTUAL cv-pipeline per-frame output (documented in
cv-pipeline/README.md §7, confirmed against the real files in
cv-pipeline/outputs/*.json) into the frame shape BehaviourEngine.process_frame
expects (documented in the root CLAUDE.md).

The two shapes diverge in ways the root CLAUDE.md didn't anticipate — this
module is the one place that bridges the gap, so nothing else in
behaviour_risk_engine needs to know about it:

  - "class_name" instead of "class".
  - "timestamp_ms" (int, frame-relative — computed as
    int((frame_id / fps) * 1000), confirmed in cv_pipeline.py) instead of
    "timestamp" (ISO 8601 UTC string). There's no wall-clock reference in
    Member 1's output at all — it's a recorded-video batch pipeline, not a
    live feed. Converted here using the same "video_start_utc" convention
    Member 4's dashboard/config.py already uses (DASHBOARD_VIDEO_START_UTC)
    for the identical problem, so both modules interpret a video's events
    against the same wall-clock reference rather than inventing two
    incompatible ones. Pass it in; if omitted, an arbitrary fixed reference
    is used and event timestamps will NOT reflect real time of day.
  - "pose": {"landmarks": [...]} instead of "keypoints": [[x, y, conf], ...].
    Not translated 1:1 — always emitted as None. Nothing in this module
    uses keypoints yet (stepping_on_product uses a bbox-based foot
    approximation instead), and MediaPipe's landmark index layout vs. this
    module's assumed [[x,y,conf], ...] shape hasn't been reconciled. Revisit
    if a future behaviour needs real pose data.
  - track_id == -1 means "ByteTrack couldn't assign a persistent id this
    frame" (cv-pipeline/README.md §5). Every behaviour detector here
    depends on track_id identity being stable across frames, so treating
    all -1 detections as one shared fake track would silently corrupt
    velocity/duration math for unrelated objects. Dropped instead.
  - Low-confidence noise: the real model is a prototype (README §4/§12 —
    "some objects were detected with relatively low confidence"). A
    MIN_CONFIDENCE floor filters those out before they reach any detector.

Known model-vocabulary gap (not something this adapter can fix): the
actual trained model (cv-pipeline/models/best.pt) only detects "person",
"box", and "forklift" — confirmed by inspecting cv-pipeline/outputs/*.json.
It was never trained on pallet, trolley, strap, cupboard, or mattress.
Practically, that means pallet_incorrect_position, strap_misuse, and
wrong_orientation cannot produce any events against this model's current
output — every class they depend on is simply never detected. This is a
prototype-model limitation Member 1's own README already calls out
("Improving cardboard box detection", "larger and more diverse warehouse
dataset"), not a bug in this adapter or in those detectors.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

# Real-classes-only alias, confirmed from cv-pipeline/outputs/*.json — the
# broader constants.PRODUCT_CLASSES set stays as-is (forward-compatible with
# a future richer model); "box" is what actually arrives today.
REAL_PRODUCT_CLASS_ALIASES = {"box": "carton"}

DEFAULT_REFERENCE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)
MIN_CONFIDENCE = 0.25  # below this, treat the detection as noise rather than a real object


def _resolve_class(class_name: str) -> str:
    return REAL_PRODUCT_CLASS_ALIASES.get(class_name, class_name)


def adapt_frame(raw_frame: dict, video_start_utc: Optional[datetime] = None) -> dict:
    """Convert one of Member 1's raw per-frame dicts into the shape
    BehaviourEngine.process_frame expects. Always returns a frame dict
    (even with an empty objects list) so frame_id stays continuous for
    TrackStore's staleness pruning."""
    reference = video_start_utc or DEFAULT_REFERENCE_TIME

    objects: List[dict] = []
    for raw_obj in raw_frame.get("objects", []):
        if raw_obj.get("track_id", -1) == -1:
            continue
        if raw_obj.get("confidence", 0.0) < MIN_CONFIDENCE:
            continue
        objects.append({
            "track_id": raw_obj["track_id"],
            "class": _resolve_class(raw_obj["class_name"]),
            "bbox": raw_obj["bbox"],
            "confidence": raw_obj.get("confidence", 0.0),
            "keypoints": None,
        })

    timestamp = reference + timedelta(milliseconds=raw_frame.get("timestamp_ms", 0))
    return {
        "frame_id": raw_frame["frame_id"],
        "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S.") + f"{timestamp.microsecond // 1000:03d}Z",
        "objects": objects,
    }


def adapt_stream(raw_frames: List[dict], video_start_utc: Optional[datetime] = None) -> List[dict]:
    return [adapt_frame(f, video_start_utc=video_start_utc) for f in raw_frames]
