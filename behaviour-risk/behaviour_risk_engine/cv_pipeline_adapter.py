"""
Translates Member 1's cv-pipeline per-frame output (cv_pipeline.py,
confirmed against real files in cv-pipeline/outputs/*.json) into the frame
shape BehaviourEngine.process_frame expects (documented in the root
CLAUDE.md and shared/cv_pipeline_schema.md).

Updated 2026-09-09 when cv_pipeline.py was fixed (it had drifted to a
Colab-only script with a different, incompatible output shape — see that
file's docstring and the root CLAUDE.md status line for the full story).
The two shapes are close now, but this adapter is kept rather than
inlining a passthrough, since the remaining differences are exactly the
kind that tend to silently reappear:

  - "timestamp_ms" (int, frame-relative — int((frame_id / fps) * 1000))
    instead of "timestamp" (ISO 8601 UTC string). There's no wall-clock
    reference in Member 1's output — it's a recorded-video batch pipeline,
    not a live feed. Converted here using the same "video_start_utc"
    convention Member 4's dashboard/config.py uses (DASHBOARD_VIDEO_START_UTC)
    for the identical problem, so both modules interpret a video's events
    against the same wall-clock reference rather than inventing two
    incompatible ones. Pass it in; if omitted, an arbitrary fixed reference
    is used and event timestamps will NOT reflect real time of day.
  - "pose" is now a flat list of {x,y,z,visibility} dicts (person only),
    not "keypoints": [[x, y, conf], ...]. Not translated 1:1 — always
    emitted as None. Nothing in this module uses keypoints yet
    (stepping_on_product uses a bbox-based foot approximation instead).
    Revisit if a future behaviour needs real pose data.
  - track_id == -1 means ByteTrack couldn't assign a persistent id this
    frame. Every behaviour detector here depends on track_id identity
    being stable across frames, so treating all -1 detections as one
    shared fake track would silently corrupt velocity/duration math for
    unrelated objects. Dropped instead.
  - Low-confidence noise: a MIN_CONFIDENCE floor filters weak detections
    before they reach any detector.

Model-vocabulary gap (not something this adapter can fix): the ACTIVE
model (cv-pipeline/models/best.pt) detects person/box/forklift/pallet.
A second model exists at cv-pipeline/models/warehouse_merged_5ep_best.pt
with 9 classes (adds trolley, robot, white_roll, small_load_carrier,
stillage) from a merged dataset, but it's not the active default — only
5 epochs of training were possible before the team's Colab compute ran
out, and real-clip testing showed every class (including person/box,
which best.pt already handles well) clustering at ~0.20-0.29 confidence,
right at the noise floor. Concretely: pallet_incorrect_position (needs
"pallet" — actually available!), strap_misuse, and wrong_orientation
(need "strap"/"cupboard"/"mattress" — not in EITHER model) still can't
produce reliable events. Swap `model_path` in cv_pipeline.run_cv() to try
the merged model once it's had more training.
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
            "class": _resolve_class(raw_obj["class"]),
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
