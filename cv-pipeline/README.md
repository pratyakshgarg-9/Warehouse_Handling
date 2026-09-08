# Member 1 — Computer Vision Pipeline

## Overview

Member 1 is responsible for converting warehouse video into structured computer-vision data for the rest of the project.

**Pipeline:**

```text
Warehouse Video
      ↓
YOLO11 Object Detection
      ↓
ByteTrack Object Tracking
      ↓
MediaPipe Pose Detection
      ↓
Per-frame JSON
      ↓
Member 2
```

## Dataset

Two Roboflow datasets were downloaded separately:

* **LOCO Warehouse Dataset**
* **Warehouse Dataset**

They were kept separate initially and then merged into a new dataset called `Combined_Warehouse`.

The original datasets were not modified.

Final classes:

```text
0 = box
1 = trolley
2 = forklift
3 = pallet
4 = person
5 = robot
6 = white_roll
7 = small_load_carrier
8 = stillage
```

`pallet_truck` and `cart` were mapped to `trolley`, while `pallets` was mapped to `pallet`.

## Model Training

A YOLO11n model was trained from `yolo11n.pt` using the merged dataset.

For the prototype, training was limited to **5 epochs** (suggested target
was 50) because the team's Colab free-tier compute ran out before more
was possible.

The trained model is stored at:

```text
cv-pipeline/models/warehouse_merged_5ep_best.pt
```

**⚠ Updated 2026-09-09: this model is not the one the pipeline actually
uses.** Real testing against demo footage showed detection confidence for
every class — including `person` and `box`, which the older model already
handled well — clustering at ~0.20-0.29, right at the inference threshold
(effectively noise). One test clip produced zero detections at all. This
isn't just "the new classes are undertrained" — it looks like training
started fresh from `yolo11n.pt` rather than continuing from the existing
working checkpoint, so 5 epochs wasn't enough to relearn `person`/`box`
either, let alone the new classes.

With no compute time left before the deadline, the pipeline's active
default reverted to the original `models/best.pt` (`box`, `forklift`,
`pallet`, `person` — confirmed working, real confidence spread up to
0.95+). `warehouse_merged_5ep_best.pt` is kept in the repo for future
work — pass `model_path=` to `run_cv()` to try it. See
`shared/cv_pipeline_schema.md` for the full comparison and what it means
for which behaviours the prototype can demonstrate (11 of 14).

**If more Colab compute becomes available before the deadline**: continue
training *from* `best.pt` rather than from `yolo11n.pt` — fine-tuning an
already-working checkpoint converges much faster than starting over, so
even 10-15 more epochs from that base could beat 5 epochs from scratch by
a wide margin.

## ByteTrack

ByteTrack was integrated with YOLO to maintain consistent `track_id` values between video frames.

Each detected object contains:

```json
{
  "track_id": 1,
  "class": "person",
  "bbox": [x1, y1, x2, y2]
}
```

ByteTrack was tested successfully on warehouse footage.

## MediaPipe Pose

MediaPipe Pose Landmarker was added to detect human pose.

Pose detection is performed **only for objects classified as `person`**.

Each person can contain 33 pose landmarks with:

```text
x
y
z
visibility
```

The MediaPipe Tasks API with `IMAGE` mode was used because the available environment had compatibility issues with the older `mp.solutions` API and `VIDEO` mode.

## Final Pipeline

The main script is:

```text
Member1_CV/pipeline/cv_pipeline.py
```

The pipeline:

1. Opens the input video.
2. Runs YOLO11 detection.
3. Uses ByteTrack for tracking.
4. Extracts bounding boxes and track IDs.
5. Runs MediaPipe Pose on detected people.
6. Stores all frame information in JSON.
7. Optionally creates an annotated MP4.

## Running the Pipeline

**Updated 2026-09-09**: fixed back to an importable function with paths
relative to the repo (the version briefly committed alongside the merged
model hardcoded Colab's `/content/...` paths and only ran as a CLI script
— broke every other module's integration with it). Both ways of running
it now call the same code, from anywhere the repo is checked out:

### As a function (what Member 2/3/4 should use)

```python
from pipeline.cv_pipeline import run_cv
run_cv("path/to/clip.mp4")                                  # -> cv-pipeline/outputs/<clip>_cv.json
run_cv("path/to/clip.mp4", model_path="models/warehouse_merged_5ep_best.pt")  # try the other model
```

### As a CLI (Colab-style)

```bash
python pipeline/cv_pipeline.py --video path/to/clip.mp4
python pipeline/cv_pipeline.py --video path/to/clip.mp4 --show   # also writes an annotated MP4
python pipeline/cv_pipeline.py --video path/to/clip.mp4 --model models/warehouse_merged_5ep_best.pt
```

Output JSON always goes to `cv-pipeline/outputs/<video_name>_cv.json`
unless `--output`/`output_json=` overrides it.

## Output Format

```json
{
  "frame_id": 0,
  "timestamp_ms": 0,
  "objects": [
    {
      "track_id": 1,
      "class": "person",
      "bbox": [100, 150, 300, 500],
      "confidence": 0.87,
      "pose": [
        {
          "x": 0.42,
          "y": 0.31,
          "z": -0.12,
          "visibility": 0.98
        }
      ]
    }
  ]
}
```

This provides Member 2 with:

* **What** is present → `class`
* **Where** it is → `bbox`
* **Which object** it is across frames → `track_id`
* **How confident the detection is** → `confidence`
* **When in the video** → `frame_id` / `timestamp_ms`
* **Human posture information** → `pose` (person only)

See `shared/cv_pipeline_schema.md` for the full contract (this is the
canonical version — keep both in sync if this changes again).

## Project Structure

```text
/content/
├── Dataset/
│   ├── Combined_Warehouse/
│   ├── LOCO/
│   └── Warehouse/
│
├── Videos/
│   ├── parcels_rack_test.mp4
│   ├── warehouse_shelves_test.mp4
│   └── warehouse_test.mp4
│
└── Member1_CV/
    ├── models/
    │   └── warehouse_merged_5ep_best.pt
    │
    ├── pose/
    │   └── pose_landmarker.task
    │
    ├── pipeline/
    │   └── cv_pipeline.py
    │
    └── outputs/
        ├── output.json
        └── output.mp4
```

## Current Status

**Completed:**

* Dataset collection
* Dataset merging
* Class mapping
* YOLO11 training
* Object detection testing
* ByteTrack integration
* MediaPipe Pose integration
* Combined pipeline
* JSON output
* Optional annotated MP4 output

The current system is a **5-epoch prototype** ready for integration and further testing with the team's sample warehouse videos.
