# CV pipeline per-frame output schema — source of truth

Published 2026-09-07 by Member 2, on Member 1's behalf, per Member 1's own
role spec ("the per-frame output format, published to `/shared` — this is
the contract Member 2 builds their rules against"). Updated 2026-09-09
after `cv_pipeline.py` was fixed (see below) — this file tracks whatever
the pipeline actually produces, not what was originally assumed.

## The actual shape (as produced by `cv_pipeline.py`)

```json
{
  "frame_id": 1042,
  "timestamp_ms": 41680,
  "objects": [
    {
      "track_id": 7,
      "class": "box",
      "confidence": 0.83,
      "bbox": [x1, y1, x2, y2],
      "pose": [{"x": 0.42, "y": 0.31, "z": -0.12, "visibility": 0.98}, "..."]
    }
  ]
}
```

- `timestamp_ms` — integer milliseconds, computed as
  `int((frame_id / fps) * 1000)`. **Frame-relative, not wall-clock.** The
  pipeline has no notion of real time of day; a video's frame 0 doesn't
  correspond to any particular UTC instant unless the caller supplies one.
- `class` — YOLO's label for the detection. See "Which model, which
  classes" below.
- `track_id` — from ByteTrack. **`-1` means no persistent id was assigned
  this frame** (short-lived or low-confidence detections often get this).
  Treat `-1` as "this detection can't be linked across frames" rather than
  as a real, shared track — several detections in the same frame can all
  be `-1` and are NOT the same object.
- `pose` — a flat list of `{x, y, z, visibility}` dicts, present (possibly
  empty) only on `person` detections; omitted entirely for other classes.
  Coordinates are relative to the person's cropped bbox, not full-frame,
  unless converted. Index/ordering matches MediaPipe's standard 33-landmark
  layout (not yet confirmed against a populated example — do that before
  building logic against specific landmark indices).

## Which model, which classes (updated 2026-09-09)

Two models exist in `cv-pipeline/models/`:

| Model | Classes | Status |
| --- | --- | --- |
| `best.pt` (**active default**) | `box`, `forklift`, `pallet`, `person` | Working — real confidence spread (0.5-0.95 on clear detections), used for the submitted prototype |
| `warehouse_merged_5ep_best.pt` | adds `trolley`, `robot`, `white_roll`, `small_load_carrier`, `stillage` (merged LOCO + warehouse datasets, `pallet_truck`/`cart`→`trolley`, `pallets`→`pallet`) | **Not usable yet** — only 5 of the suggested 50 epochs (Colab free-tier compute ran out), and it shows it: every class, including `person`/`box` which `best.pt` already handles well, clustered at ~0.20-0.29 confidence (the inference floor) across two real test clips — one clip produced *zero* detections of anything. This isn't "fewer classes trained well," it's under-trained across the board, likely because training started fresh from `yolo11n.pt` instead of continuing from `best.pt`'s already-good weights. Kept in the repo for future work; not wired into the pipeline's default. |

**Practical effect on behaviour-risk's 14 behaviours**: with `best.pt`
active, `pallet_incorrect_position` is actually viable now (`pallet` is a
real class!) — the earlier "3 dead behaviours" note was written when only
person/box/forklift were confirmed. Still dead: `strap_misuse` and
`wrong_orientation` (need `strap`/`cupboard`/`mattress`, in neither
model). **11 of 14 behaviours are demonstrable against real footage with
the current active model** — that's the honest scope for this prototype.

## `cv_pipeline.py` interface (fixed 2026-09-09)

A version committed 2026-09-08/09 (alongside the merged-dataset model)
broke every integration outside the exact Colab session it was written
in: hardcoded `/content/Member1_CV/...` absolute paths, `argparse` running
at import time (so even `import cv_pipeline` would fail without
`--video` in `sys.argv`), and the schema drifted again (`class_name`
instead of `class`, no `timestamp_ms`, no `confidence`, pose nested
differently). Fixed back to an importable function with repo-relative
paths:

```python
from cv_pipeline import run_cv
run_cv("path/to/clip.mp4")                      # writes to cv-pipeline/outputs/
run_cv("path/to/clip.mp4", model_path="...")    # try a different checkpoint
```

Still works as a CLI too (`python cv_pipeline.py --video clip.mp4
[--model path] [--show]`) for Member 1's own Colab-style usage — both
paths call the same function now, so they can't drift apart again.

## Who needs to know this

- **Member 2** (`behaviour-risk`): adapted — see
  `behaviour_risk_engine/cv_pipeline_adapter.py`.
- **Member 4** (`dashboard`): `dashboard/data_access.py`'s
  `load_detections()` is written against the root CLAUDE.md's original
  (never-real) schema — it'll break or silently misparse once pointed at
  real output. Reuse the mapping in Member 2's adapter above. Also:
  `overlays.py`'s `CLASS_COLORS` only has person/carton/pallet/trolley —
  doesn't cover `box`/`forklift` (the real class names) or the 4
  behaviours added after `overlays.py` was written.
- **Member 3** (`backend-assistant`): not yet built. This per-frame format
  isn't what gets written to the event store — Member 2's `Event` schema
  (root CLAUDE.md) is unaffected by any of this.

## Still open

- No `video_start_utc` convention has been agreed on for turning
  `timestamp_ms` into a real timestamp. `dashboard/config.py` already has
  a `DASHBOARD_VIDEO_START_UTC` env var for this; Member 2's adapter has
  an equivalent parameter with a different default. Whoever runs the
  pipeline for the actual demo should pick one value and pass it
  consistently to both.
- `strap_misuse` and `wrong_orientation` need classes neither model has.
  Out of scope for tomorrow's submission — call it future work in the deck
  rather than silently missing it.
