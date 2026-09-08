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

For the prototype, training was limited to **5 epochs** to avoid system crashes.

The trained model is stored at:

```text
Member1_CV/models/warehouse_merged_5ep_best.pt
```

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

### JSON only

```bash
python /content/Member1_CV/pipeline/cv_pipeline.py --video /content/Videos/parcels_rack_test.mp4
```

Output:

```text
Member1_CV/outputs/output.json
```

### JSON + annotated video

```bash
python /content/Member1_CV/pipeline/cv_pipeline.py --video /content/Videos/parcels_rack_test.mp4 --show
```

Outputs:

```text
Member1_CV/outputs/output.json
Member1_CV/outputs/output.mp4
```

The JSON is **always generated**, while `--show` enables creation of the annotated MP4.

## Output Format

Example:

```json
{
  "frame": 0,
  "objects": [
    {
      "track_id": 1,
      "class": "person",
      "bbox": [100, 150, 300, 500],
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
* **Human posture information** → `pose`

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
