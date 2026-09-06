import cv2
import json
import os
import mediapipe as mp
from ultralytics import YOLO

from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision


# ============================================================
# PATHS
# ============================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODEL_PATH = os.path.join(
    BASE_DIR,
    "models",
    "best.pt"
)

POSE_MODEL = os.path.join(
    BASE_DIR,
    "pose",
    "pose_landmarker.task"
)

OUTPUT_DIR = os.path.join(
    BASE_DIR,
    "outputs"
)

os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# LOAD MODELS ONCE
# ============================================================

model = YOLO(MODEL_PATH)

names = model.names

PERSON_CLASS_ID = next(
    int(k)
    for k, v in names.items()
    if v.lower() == "person"
)


# ============================================================
# MEDIAPIPE POSE
# ============================================================

base_options = mp_python.BaseOptions(
    model_asset_path=POSE_MODEL
)

options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.IMAGE
)

pose_landmarker = vision.PoseLandmarker.create_from_options(
    options
)


print("YOLO loaded")
print("Classes:", names)
print("Person class ID:", PERSON_CLASS_ID)
print("MediaPipe Pose loaded")


# ============================================================
# REUSABLE CV PIPELINE
# ============================================================

def run_cv(video_path, max_frames=None):

    if not os.path.exists(video_path):
        raise FileNotFoundError(
            f"Video not found: {video_path}"
        )

    # --------------------------------------------------------
    # OUTPUT FILE NAMES
    # --------------------------------------------------------

    video_name = os.path.splitext(
        os.path.basename(video_path)
    )[0]

    json_path = os.path.join(
        OUTPUT_DIR,
        f"{video_name}_cv.json"
    )

    video_output = os.path.join(
        OUTPUT_DIR,
        f"{video_name}_annotated.mp4"
    )

    # --------------------------------------------------------
    # OPEN VIDEO
    # --------------------------------------------------------

    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        raise RuntimeError(
            f"Could not open video: {video_path}"
        )

    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(
        cap.get(cv2.CAP_PROP_FRAME_COUNT)
    )

    if fps <= 0:
        fps = 25

    frames_to_process = total_frames

    if max_frames is not None:
        frames_to_process = min(
            max_frames,
            total_frames
        )

    width = int(
        cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    )

    height = int(
        cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    )

    # --------------------------------------------------------
    # VIDEO WRITER
    # --------------------------------------------------------

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    writer = cv2.VideoWriter(
        video_output,
        fourcc,
        fps,
        (width, height)
    )

    output = []

    print("\n================================")
    print("STARTING CV PIPELINE")
    print("================================")
    print("Video:", video_path)
    print("FPS:", fps)
    print("Total frames:", total_frames)
    print("Processing:", frames_to_process)
    print()

    # ========================================================
    # PROCESS FRAMES
    # ========================================================

    for frame_id in range(frames_to_process):

        ret, frame = cap.read()

        if not ret:
            break

        timestamp_ms = int(
            (frame_id / fps) * 1000
        )

        # ----------------------------------------------------
        # YOLO + BYTE TRACK
        # ----------------------------------------------------

        result = model.track(
            frame,
            tracker="bytetrack.yaml",
            persist=True,
            conf=0.25,
            imgsz=640,
            verbose=False
        )[0]

        frame_objects = []

        if result.boxes is not None and len(result.boxes) > 0:

            boxes = result.boxes

            classes = boxes.cls.cpu().numpy()
            confidences = boxes.conf.cpu().numpy()
            coordinates = boxes.xyxy.cpu().numpy()

            if boxes.id is not None:
                track_ids = (
                    boxes.id.cpu()
                    .numpy()
                    .astype(int)
                )
            else:
                track_ids = [-1] * len(classes)

            # ------------------------------------------------
            # PROCESS EACH DETECTED OBJECT
            # ------------------------------------------------

            for cls, conf, bbox, track_id in zip(
                classes,
                confidences,
                coordinates,
                track_ids
            ):

                cls_id = int(cls)
                class_name = names[cls_id]

                x1, y1, x2, y2 = map(
                    int,
                    bbox
                )

                obj = {
                    "track_id": int(track_id),
                    "class_id": cls_id,
                    "class_name": class_name,
                    "confidence": float(conf),
                    "bbox": [x1, y1, x2, y2],
                    "pose": None
                }

                # ==========================================
                # MEDIAPIPE POSE FOR PERSON
                # ==========================================

                if cls_id == PERSON_CLASS_ID:

                    # Keep bounding box inside frame
                    x1 = max(
                        0,
                        min(x1, width - 1)
                    )

                    x2 = max(
                        0,
                        min(x2, width)
                    )

                    y1 = max(
                        0,
                        min(y1, height - 1)
                    )

                    y2 = max(
                        0,
                        min(y2, height)
                    )

                    if x2 > x1 and y2 > y1:

                        person_crop = frame[
                            y1:y2,
                            x1:x2
                        ]

                        rgb_crop = cv2.cvtColor(
                            person_crop,
                            cv2.COLOR_BGR2RGB
                        )

                        mp_image = mp.Image(
                            image_format=mp.ImageFormat.SRGB,
                            data=rgb_crop
                        )

                        pose_result = (
                            pose_landmarker.detect(
                                mp_image
                            )
                        )

                        if pose_result.pose_landmarks:

                            landmarks = []

                            for landmark_id, lm in enumerate(
                                pose_result.pose_landmarks[0]
                            ):

                                landmarks.append({
                                    "id": landmark_id,
                                    "x": float(lm.x),
                                    "y": float(lm.y),
                                    "z": float(lm.z),
                                    "visibility": float(
                                        lm.visibility
                                    )
                                })

                            obj["pose"] = {
                                "landmarks": landmarks
                            }

                # ------------------------------------------------
                # SAVE OBJECT
                # ------------------------------------------------

                frame_objects.append(obj)

                # ================================================
                # DRAW DETECTION BOX
                # ================================================

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    (0, 255, 0),
                    2
                )

                label = (
                    f"{class_name} "
                    f"ID:{int(track_id)} "
                    f"{float(conf):.2f}"
                )

                cv2.putText(
                    frame,
                    label,
                    (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2
                )

                # ================================================
                # DRAW POSE LANDMARKS
                # ================================================

                if (
                    cls_id == PERSON_CLASS_ID
                    and obj["pose"] is not None
                ):

                    landmarks = obj["pose"]["landmarks"]

                    points = []

                    for lm in landmarks:

                        px = int(
                            x1 + lm["x"] * (x2 - x1)
                        )

                        py = int(
                            y1 + lm["y"] * (y2 - y1)
                        )

                        points.append(
                            (px, py)
                        )

                        cv2.circle(
                            frame,
                            (px, py),
                            3,
                            (255, 0, 0),
                            -1
                        )

                    # MediaPipe pose connections
                    connections = [
                        (11, 12),
                        (11, 13),
                        (13, 15),
                        (12, 14),
                        (14, 16),
                        (11, 23),
                        (12, 24),
                        (23, 24),
                        (23, 25),
                        (25, 27),
                        (24, 26),
                        (26, 28)
                    ]

                    for a, b in connections:

                        if (
                            a < len(points)
                            and b < len(points)
                        ):

                            cv2.line(
                                frame,
                                points[a],
                                points[b],
                                (255, 0, 0),
                                2
                            )

        # ========================================================
        # SAVE FRAME DATA
        # ========================================================

        output.append({
            "frame_id": frame_id,
            "timestamp_ms": timestamp_ms,
            "objects": frame_objects
        })

        # Save annotated frame
        writer.write(frame)

        if (frame_id + 1) % 25 == 0:

            print(
                f"Processed "
                f"{frame_id + 1}/"
                f"{frames_to_process} frames"
            )

    # ========================================================
    # CLEAN UP
    # ========================================================

    cap.release()
    writer.release()

    # ========================================================
    # SAVE JSON
    # ========================================================

    with open(json_path, "w") as f:

        json.dump(
            output,
            f,
            indent=2
        )

    print("\n================================")
    print("CV PIPELINE COMPLETE")
    print("================================")
    print("Frames processed:", len(output))
    print("JSON:", json_path)
    print("Video:", video_output)

    return json_path, video_output
