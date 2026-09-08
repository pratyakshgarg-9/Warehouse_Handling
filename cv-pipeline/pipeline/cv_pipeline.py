"""
Member 1 — Computer Vision Pipeline.

Turns a warehouse video into structured per-frame JSON: what's in each
frame (YOLO11 + ByteTrack), and human pose for detected people (MediaPipe).

Importable as a function (`run_cv(...)`) so the rest of the team can call
it directly, and runnable as a CLI script for Colab-style usage
(`python cv_pipeline.py --video path/to/clip.mp4`).

2026-09-09: restored to an importable function + repo-relative paths.
The previous version (committed alongside the 5-epoch merged-dataset
model) hardcoded Colab's `/content/Member1_CV/...` paths and ran argparse
at import time, which broke every integration outside that one Colab
session. Also restored `timestamp_ms` and `confidence` on each object —
both present in earlier versions of this pipeline and needed downstream
(behaviour-risk's velocity/duration math needs `timestamp_ms`; its
confidence floor needs `confidence`) — the version this replaces had
dropped both.

Default model is `models/best.pt` (person/box/forklift/pallet, the
original working checkpoint), not `models/warehouse_merged_5ep_best.pt`.
The merged model exists in this repo for future work, but 5 epochs from
yolo11n.pt on a freshly-merged 9-class dataset isn't usable yet — real
per-clip testing showed detection confidence clustering at the 0.20-0.29
noise floor (barely above the inference threshold) across every class,
including person and box, which the older checkpoint had already learned
well. There was no more Colab compute budget left to keep training before
the submission deadline, so the working 3(-well,4-)class model is what the
prototype actually uses; see cv-pipeline/README.md and the root
CLAUDE.md's status line for the full writeup of that decision.
"""

from __future__ import annotations

import argparse
import json
import os

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision
from ultralytics import YOLO

# ============================================================
# PATHS — relative to this file, so this works from any machine/checkout,
# not just the exact Colab session it was written in.
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_MODEL_PATH = os.path.join(BASE_DIR, "models", "best.pt")
DEFAULT_POSE_MODEL_PATH = os.path.join(BASE_DIR, "pose", "pose_landmarker.task")
DEFAULT_OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

_model_cache: dict = {}


def _get_model(model_path: str) -> YOLO:
    if model_path not in _model_cache:
        _model_cache[model_path] = YOLO(model_path)
    return _model_cache[model_path]


def _get_pose_landmarker(pose_model_path: str):
    base_options = mp_python.BaseOptions(model_asset_path=pose_model_path)
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.IMAGE,
        num_poses=1,
    )
    return vision.PoseLandmarker.create_from_options(options)


def run_cv(
    video_path: str,
    output_json: str | None = None,
    model_path: str = DEFAULT_MODEL_PATH,
    pose_model_path: str = DEFAULT_POSE_MODEL_PATH,
    show: bool = False,
    max_frames: int | None = None,
) -> str:
    """Process `video_path` frame by frame and write per-frame JSON.

    Returns the path the JSON was written to. Pass `model_path` to try a
    different checkpoint (e.g. the merged-dataset model once it's been
    trained further) without editing this file.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"YOLO model not found: {model_path}")
    if not os.path.exists(pose_model_path):
        raise FileNotFoundError(f"Pose model not found: {pose_model_path}")

    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
    if output_json is None:
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        output_json = os.path.join(DEFAULT_OUTPUT_DIR, f"{video_name}_cv.json")
    os.makedirs(os.path.dirname(output_json) or ".", exist_ok=True)

    model = _get_model(model_path)
    pose_landmarker = _get_pose_landmarker(pose_model_path)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 25
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames_to_process = min(max_frames, total_frames) if max_frames is not None else total_frames
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    video_writer = None
    output_video = os.path.splitext(output_json)[0] + "_annotated.mp4"
    if show:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(output_video, fourcc, fps, (width, height))

    print("================================")
    print("STARTING CV PIPELINE")
    print("================================")
    print("Video:", video_path)
    print("Model:", model_path)
    print("Classes:", model.names)
    print("FPS:", fps, "| Total frames:", total_frames, "| Processing:", frames_to_process)
    print()

    all_frames = []
    for frame_id in range(frames_to_process):
        ok, frame = cap.read()
        if not ok:
            break

        timestamp_ms = int((frame_id / fps) * 1000)

        results = model.track(
            frame,
            tracker="bytetrack.yaml",
            conf=0.20,
            imgsz=640,
            persist=True,
            verbose=False,
        )[0]

        frame_objects = []
        boxes = results.boxes
        if boxes is not None and len(boxes) > 0:
            classes = boxes.cls.cpu().tolist()
            confidences = boxes.conf.cpu().tolist()
            coordinates = boxes.xyxy.cpu().tolist()
            track_ids = boxes.id.cpu().tolist() if boxes.id is not None else [-1] * len(classes)

            for cls, conf, bbox, track_id in zip(classes, confidences, coordinates, track_ids):
                class_name = model.names[int(cls)]
                x1, y1, x2, y2 = (int(v) for v in bbox)

                object_data = {
                    "track_id": int(track_id),
                    "class": class_name,
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(float(conf), 4),
                }

                if class_name == "person":
                    h, w = frame.shape[:2]
                    xc1, yc1 = max(0, x1), max(0, y1)
                    xc2, yc2 = min(w, x2), min(h, y2)
                    person_crop = frame[yc1:yc2, xc1:xc2]

                    pose_landmarks = []
                    if person_crop.size > 0:
                        rgb_crop = cv2.cvtColor(person_crop, cv2.COLOR_BGR2RGB)
                        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_crop)
                        pose_result = pose_landmarker.detect(mp_image)
                        if pose_result.pose_landmarks:
                            pose_landmarks = [
                                {"x": lm.x, "y": lm.y, "z": lm.z, "visibility": lm.visibility}
                                for lm in pose_result.pose_landmarks[0]
                            ]
                    object_data["pose"] = pose_landmarks

                frame_objects.append(object_data)

                if show:
                    color = (0, 255, 0)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    label = f"{class_name} ID:{int(track_id)} {conf:.2f}"
                    cv2.putText(frame, label, (x1, max(y1 - 10, 20)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        all_frames.append({
            "frame_id": frame_id,
            "timestamp_ms": timestamp_ms,
            "objects": frame_objects,
        })

        if show:
            video_writer.write(frame)

        if (frame_id + 1) % 100 == 0:
            print(f"Processed {frame_id + 1}/{frames_to_process} frames...")

    cap.release()
    if video_writer is not None:
        video_writer.release()

    with open(output_json, "w") as f:
        json.dump(all_frames, f, indent=2)

    print()
    print("================================")
    print("CV PIPELINE COMPLETE")
    print("================================")
    print("Frames processed:", len(all_frames))
    print("JSON:", output_json)
    if show:
        print("Video:", output_video)

    return output_json


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Member 1 Computer Vision Pipeline")
    parser.add_argument("--video", required=True, help="Input video path")
    parser.add_argument("--output", default=None, help="JSON output path")
    parser.add_argument("--model", default=DEFAULT_MODEL_PATH, help="YOLO model path")
    parser.add_argument("--show", action="store_true", help="Save annotated MP4 too")
    args = parser.parse_args()

    run_cv(args.video, output_json=args.output, model_path=args.model, show=args.show)
