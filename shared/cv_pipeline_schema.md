# CV pipeline per-frame output schema — source of truth

Published 2026-09-07 by Member 2, on Member 1's behalf, per Member 1's own
role spec ("the per-frame output format, published to `/shared` — this is
the contract Member 2 builds their rules against"). This wasn't published
here when the pipeline shipped (2026-09-06/07) — the format only lived in
`cv-pipeline/README.md` and diverged from the schema locked in the root
`CLAUDE.md` without the team being flagged, which the Sep 6 integration
checkpoint in `Member1_CV_Spec.md` explicitly calls for. This file is that
missing flag, written after the fact — confirmed directly against the real
output in `cv-pipeline/outputs/*.json`, not just the README's description.

## The actual shape (as produced by `cv_pipeline.py`)

```json
{
  "frame_id": 1042,
  "timestamp_ms": 41680,
  "objects": [
    {
      "track_id": 7,
      "class_id": 2,
      "class_name": "box",
      "confidence": 0.83,
      "bbox": [x1, y1, x2, y2],
      "pose": { "landmarks": [] }
    }
  ]
}
```

- `timestamp_ms` — integer milliseconds, computed as
  `int((frame_id / fps) * 1000)`. **Frame-relative, not wall-clock.** The
  pipeline has no notion of real time of day; a video's frame 0 doesn't
  correspond to any particular UTC instant unless the caller supplies one.
- `class_name` / `class_id` — YOLO's label for the detection. The
  **currently trained model (`cv-pipeline/models/best.pt`) only produces
  `"person"`, `"box"`, and `"forklift"`** — confirmed by inspecting every
  object in both files under `cv-pipeline/outputs/`. It was never trained
  on `pallet`, `trolley`, `cupboard`, `mattress`, or `strap`, despite the
  original labeling plan (person/carton/pallet/trolley) and the doc's
  fuller product vocabulary. Retraining with a broader labeled dataset is
  real, separate work — not something fixable by changing this schema.
- `track_id` — from ByteTrack. **`-1` means no persistent id was assigned
  this frame** (short-lived or low-confidence detections often get this).
  Treat `-1` as "this detection can't be linked across frames" rather than
  as a real, shared track — several detections in the same frame can all
  be `-1` and are NOT the same object.
- `pose.landmarks` — MediaPipe Pose output for `person` detections,
  `null`/empty for everything else. Coordinates are relative to the
  person's cropped bbox, not full-frame, unless converted. Index/ordering
  matches MediaPipe's standard 33-landmark layout (not yet confirmed
  against a populated example — do that before building logic against
  specific landmark indices).

## How this differs from the schema in the root `CLAUDE.md`

| Root CLAUDE.md (originally assumed) | Actual (`cv_pipeline.py`) |
| --- | --- |
| `timestamp` (ISO 8601 UTC string) | `timestamp_ms` (int, frame-relative) |
| `class` | `class_name` (+ `class_id`) |
| `keypoints: [[x, y, conf], ...]` | `pose: {landmarks: [...]}` |
| implied every detection is trackable | `track_id: -1` for untracked detections |
| person/carton/pallet/trolley vocabulary | person/box/forklift only |

## Who needs to know this

- **Member 2** (`behaviour-risk`): already adapted — see
  `behaviour_risk_engine/cv_pipeline_adapter.py` for the translation layer
  and the full rationale for each mapping decision.
- **Member 4** (`dashboard`): `dashboard/data_access.py`'s
  `load_detections()` is written against the root CLAUDE.md's original
  (incorrect) schema — it will break or silently misparse once pointed at
  real output. Reuse the mapping in Member 2's adapter above rather than
  writing an independent translation that could drift from it.
- **Member 3** (`backend-assistant`): not yet built, but this per-frame
  format is not what gets written to the event store — Member 2's `Event`
  schema (root CLAUDE.md) is unaffected by any of this.

## Still open

- No `video_start_utc` convention has been agreed on for turning
  `timestamp_ms` into a real timestamp. `dashboard/config.py` already has
  a `DASHBOARD_VIDEO_START_UTC` env var for this; Member 2's adapter has
  an equivalent parameter with a different default. Whoever runs the
  pipeline for the actual demo should pick one value and pass it
  consistently to both.
- The class-vocabulary gap (no pallet/trolley/strap/cupboard/mattress)
  means `pallet_incorrect_position`, `strap_misuse`, and
  `wrong_orientation` cannot produce real events until the model is
  retrained with a broader labeled dataset.
