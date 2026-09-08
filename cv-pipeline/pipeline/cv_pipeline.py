import cv2
import json
import argparse
import os
import mediapipe as mp

from ultralytics import YOLO
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


# ============================================================
# ARGUMENTS
# ============================================================

parser = argparse.ArgumentParser(
    description="Member 1 Computer Vision Pipeline"
)

parser.add_argument(
    "--video",
    required=True,
    help="Input video path"
)

parser.add_argument(
    "--output",
    default="/content/Member1_CV/outputs/output.json",
    help="JSON output path"
)

parser.add_argument(
    "--show",
    action="store_true",
    help="Save and display annotated MP4"
)

args = parser.parse_args()

VIDEO_PATH = args.video
OUTPUT_JSON = args.output
SHOW_VIDEO = args.show


# ============================================================
# MODEL PATHS
# ============================================================

YOLO_MODEL = "/content/Member1_CV/models/warehouse_merged_5ep_best.pt"
POSE_MODEL = "/content/Member1_CV/pose/pose_landmarker.task"


# ============================================================
# CHECK FILES
# ============================================================

if not os.path.exists(VIDEO_PATH):
    raise FileNotFoundError(
        f"Video not found: {VIDEO_PATH}"
    )

if not os.path.exists(YOLO_MODEL):
    raise FileNotFoundError(
        f"YOLO model not found: {YOLO_MODEL}"
    )

if not os.path.exists(POSE_MODEL):
    raise FileNotFoundError(
        f"Pose model not found: {POSE_MODEL}"
    )

os.makedirs(
    os.path.dirname(OUTPUT_JSON),
    exist_ok=True
)


# ============================================================
# LOAD YOLO
# ============================================================

print("Loading YOLO...")

model = YOLO(YOLO_MODEL)

print("YOLO loaded!")
print("Classes:", model.names)


# ============================================================
# LOAD MEDIAPIPE
# ============================================================

print("Loading MediaPipe Pose...")

base_options = python.BaseOptions(
    model_asset_path=POSE_MODEL
)

pose_options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.IMAGE,
    num_poses=1
)

pose_landmarker = vision.PoseLandmarker.create_from_options(
    pose_options
)

print("MediaPipe loaded!")


# ============================================================
# OPEN VIDEO
# ============================================================

print("Opening video:")
print(VIDEO_PATH)

cap = cv2.VideoCapture(VIDEO_PATH)

if not cap.isOpened():
    raise RuntimeError(
        f"Could not open video: {VIDEO_PATH}"
    )


# ============================================================
# VIDEO INFORMATION
# ============================================================

fps = cap.get(cv2.CAP_PROP_FPS)

if fps <= 0:
    fps = 25

width = int(
    cap.get(cv2.CAP_PROP_FRAME_WIDTH)
)

height = int(
    cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
)


# ============================================================
# VIDEO WRITER
# ============================================================

video_writer = None

OUTPUT_VIDEO = os.path.splitext(OUTPUT_JSON)[0] + ".mp4"

if SHOW_VIDEO:

    fourcc = cv2.VideoWriter_fourcc(
        *"mp4v"
    )

    video_writer = cv2.VideoWriter(
        OUTPUT_VIDEO,
        fourcc,
        fps,
        (width, height)
    )

    print("Annotated video will be saved to:")
    print(OUTPUT_VIDEO)


# ============================================================
# PROCESS VIDEO
# ============================================================

all_frames = []
frame_number = 0

while cap.isOpened():

    success, frame = cap.read()

    if not success:
        break

    frame_objects = []


    # ========================================================
    # YOLO + BYTETRACK
    # ========================================================

    results = model.track(
        frame,
        tracker="bytetrack.yaml",
        conf=0.20,
        imgsz=640,
        persist=True,
        verbose=False
    )

    boxes = results[0].boxes


    if boxes is not None and len(boxes) > 0:

        for i in range(len(boxes)):

            # ------------------------------------------------
            # BOUNDING BOX
            # ------------------------------------------------

            x1, y1, x2, y2 = map(
                int,
                boxes.xyxy[i].cpu().tolist()
            )


            # ------------------------------------------------
            # CLASS
            # ------------------------------------------------

            class_id = int(
                boxes.cls[i].cpu().item()
            )

            class_name = model.names[class_id]


            # ------------------------------------------------
            # TRACK ID
            # ------------------------------------------------

            if boxes.id is not None:

                track_id = int(
                    boxes.id[i].cpu().item()
                )

            else:

                track_id = -1


            # ------------------------------------------------
            # OBJECT DATA
            # ------------------------------------------------

            object_data = {
                "track_id": track_id,
                "class": class_name,
                "bbox": [
                    x1,
                    y1,
                    x2,
                    y2
                ]
            }


            # =================================================
            # MEDIAPIPE POSE
            # =================================================

            if class_name == "person":

                h, w = frame.shape[:2]

                x1_crop = max(0, x1)
                y1_crop = max(0, y1)
                x2_crop = min(w, x2)
                y2_crop = min(h, y2)

                person_crop = frame[
                    y1_crop:y2_crop,
                    x1_crop:x2_crop
                ]


                if person_crop.size > 0:

                    rgb_crop = cv2.cvtColor(
                        person_crop,
                        cv2.COLOR_BGR2RGB
                    )

                    mp_image = mp.Image(
                        image_format=mp.ImageFormat.SRGB,
                        data=rgb_crop
                    )

                    pose_result = pose_landmarker.detect(
                        mp_image
                    )

                    pose_landmarks = []


                    if pose_result.pose_landmarks:

                        landmarks = (
                            pose_result.pose_landmarks[0]
                        )

                        for landmark in landmarks:

                            pose_landmarks.append({
                                "x": landmark.x,
                                "y": landmark.y,
                                "z": landmark.z,
                                "visibility": landmark.visibility
                            })


                    object_data["pose"] = pose_landmarks


            # ------------------------------------------------
            # ADD OBJECT
            # ------------------------------------------------

            frame_objects.append(
                object_data
            )


            # =================================================
            # DRAW ANNOTATIONS
            # =================================================

            if SHOW_VIDEO:

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2
                )

                label = (
                    f"{class_name} ID:{track_id}"
                )

                cv2.putText(
                    frame,
                    label,
                    (x1, max(y1 - 10, 20)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )


    # ========================================================
    # SAVE FRAME DATA
    # ========================================================

    all_frames.append({
        "frame": frame_number,
        "objects": frame_objects
    })


    # ========================================================
    # SAVE ANNOTATED FRAME TO MP4
    # ========================================================

    if SHOW_VIDEO:

        video_writer.write(frame)


    frame_number += 1


    # ========================================================
    # PROGRESS
    # ========================================================

    if frame_number % 100 == 0:

        print(
            f"Processed {frame_number} frames..."
        )


# ============================================================
# CLEANUP
# ============================================================

cap.release()

if video_writer is not None:
    video_writer.release()


# ============================================================
# SAVE JSON
# ============================================================

with open(
    OUTPUT_JSON,
    "w"
) as f:

    json.dump(
        all_frames,
        f,
        indent=2
    )


# ============================================================
# COMPLETE
# ============================================================

print()
print("==========================================")
print("        MEMBER 1 PIPELINE COMPLETE")
print("==========================================")

print(
    f"Frames processed: {frame_number}"
)

print(
    f"JSON output: {OUTPUT_JSON}"
)

if SHOW_VIDEO:

    print(
        f"Video output: {OUTPUT_VIDEO}"
    )

else:

    print(
        "Video output: disabled"
    )

print("==========================================")
