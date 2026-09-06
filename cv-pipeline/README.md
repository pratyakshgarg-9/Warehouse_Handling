# Computer Vision Pipeline

## 1. Purpose

The `cv-pipeline` module is responsible for converting raw warehouse video into structured information that can be used by the Behaviour Risk module.

The pipeline answers three basic questions:

1. What objects are present in the video?
2. Where are those objects and how do they move?
3. What is the posture of a detected person?

The pipeline uses YOLO11 for object detection, ByteTrack for object tracking, and MediaPipe Pose for human pose estimation.

## 2. Pipeline

The processing flow is:

Warehouse Video → YOLO11 Object Detection → ByteTrack Tracking → MediaPipe Pose Estimation → Per-frame JSON Output → Behaviour Risk Module

YOLO11 identifies objects in each frame. ByteTrack assigns tracking IDs so the same detected object can be followed across multiple frames. MediaPipe Pose is applied to detected people to obtain pose landmarks. The final information is stored as structured JSON.

## 3. Project Structure

The `cv-pipeline` folder contains the following:

models/best.pt
- Fine-tuned YOLO11 model used for object detection.

pose/pose_landmarker.task
- MediaPipe Pose Landmarker model used for human pose estimation.

pipeline/cv_pipeline.py
- Main Python implementation of the computer vision pipeline.

outputs/cv_output.json
- Generated CV output data from testing.

outputs/warehouse_scanning_test_cv.json
- CV output generated from the warehouse scanning test video.

README.md
- Documentation for the CV pipeline.

The test videos are kept separately because of their large file sizes and are not included in the Git repository.

## 4. Object Detection

The pipeline uses a fine-tuned YOLO11 model stored at:

models/best.pt

The model detects the object classes available in the prototype training dataset.

The current model is a prototype model, so detection performance is not expected to be perfect. During testing, some objects were detected with relatively low confidence or were missed completely. The model can be improved later by training with a larger and more representative warehouse dataset.

The detection model can be replaced in the future without redesigning the rest of the pipeline. The new model can simply be placed at the expected model path.

## 5. Object Tracking

ByteTrack is used to track detected objects across consecutive video frames.

Each tracked object can receive a `track_id`. For example, if the same forklift is detected across several frames, ByteTrack can maintain the same ID:

Frame 10 → forklift → track_id 2
Frame 11 → forklift → track_id 2
Frame 12 → forklift → track_id 2

This is important for the Behaviour Risk module because it allows the system to analyze movement over time instead of treating every detection as a new object.

A `track_id` of `-1` means that ByteTrack did not assign a persistent tracking ID to that detection.

## 6. Human Pose Estimation

MediaPipe Pose is applied to detected person regions.

The pose model is stored at:

pose/pose_landmarker.task

For a person detection, the pipeline attempts to generate pose landmarks. For non-person objects, the pose value is set to `null`.

The pose landmarks are currently generated from the detected person's cropped image. Therefore, their coordinates are relative to the person crop unless they are converted back to full-frame coordinates.

## 7. Per-frame JSON Output

The pipeline produces structured information for every processed frame.

A simplified example is:

{
  "frame_id": 1,
  "timestamp_ms": 40,
  "objects": [
    {
      "track_id": 2,
      "class_id": 6,
      "class_name": "person",
      "confidence": 0.31,
      "bbox": [120, 80, 300, 520],
      "pose": {
        "landmarks": []
      }
    }
  ]
}

The fields have the following meaning:

`frame_id`
The frame number in the video.

`timestamp_ms`
The timestamp of the frame in milliseconds.

`objects`
The list of objects detected in that frame.

`track_id`
The ID assigned by ByteTrack to follow an object across frames.

`class_id`
The numerical class ID assigned by YOLO.

`class_name`
The name of the detected object class.

`confidence`
The confidence score produced by YOLO for the detection.

`bbox`
The bounding box of the detected object in the format `[x1, y1, x2, y2]`.

`pose`
MediaPipe pose information for a detected person. This is `null` for non-person objects.

## 8. Main Pipeline File

The main implementation is:

pipeline/cv_pipeline.py

The main function is:

run_cv(video_path)

The function takes a video path as input and processes the video frame by frame.

For each frame, it performs object detection, object tracking, and pose estimation where applicable. It then stores the results in JSON and creates an annotated video showing the detections and tracking information.

## 9. Running the Pipeline

Required Python packages include:

- ultralytics
- mediapipe
- opencv-python

The pipeline can be imported using:

from pipeline.cv_pipeline import run_cv

Then run:

run_cv("path/to/warehouse_scanning_test.mp4")

The generated files are saved in the `outputs` folder.

For example:

outputs/warehouse_scanning_test_cv.json
outputs/warehouse_scanning_test_annotated.mp4

The JSON file contains the structured CV information. The annotated MP4 is used to visually verify the detections, tracking IDs, and pose estimation.

## 10. Prototype Testing

The pipeline was tested using:

warehouse_scanning_test.mp4

The test video contains 452 frames and runs at approximately 25 FPS.

The complete pipeline successfully processed the video and generated the required JSON output and annotated video.

During prototype testing, the model produced detections for objects such as forklift, box, and person. However, detections were relatively sparse. This is considered a limitation of the current prototype model rather than a failure of the CV pipeline itself.

The current implementation therefore demonstrates the complete end-to-end CV workflow while leaving model accuracy improvements for later development.

## 11. Behaviour Risk Integration

The CV pipeline is the perception layer of the overall system.

Its output is intended to be consumed by the Behaviour Risk module.

The Behaviour Risk module can use the following information:

- Object class
- Object confidence
- Bounding box
- Track ID
- Frame ID
- Timestamp
- Person pose landmarks

This information can then be used to identify movement patterns and potential safety-related behaviours.

The intended flow is:

Video → CV Pipeline → Per-frame JSON → Behaviour Risk Analysis → Risk Events / Risk Scores

## 12. Current Limitations

This is a prototype implementation.

The current limitations include:

- Object detection accuracy depends on the quality and variety of the training data.
- Some objects may have low confidence scores.
- Some objects may not be detected in every frame.
- Individual boxes may not always be detected correctly.
- Short-lived or weak detections may not receive a persistent tracking ID.
- Pose coordinates are currently based on the detected person crop.
- Performance may vary depending on lighting, camera angle, object size, occlusion, and warehouse environment.

These limitations can be addressed during future model training and system refinement.

## 13. Future Improvements

Possible improvements include:

- Training with a larger and more diverse warehouse dataset.
- Adding more representative warehouse footage to the training data.
- Improving cardboard box detection.
- Improving person and object detection accuracy.
- Tuning YOLO confidence and ByteTrack parameters.
- Improving tracking during object occlusion.
- Improving pose estimation robustness.
- Testing the pipeline on multiple full-length warehouse videos.
- Optimizing inference speed for real-time or near-real-time processing.

## 14. Member 1 Responsibility

Member 1 is responsible for the Computer Vision Pipeline.

The final responsibility is:

Raw Warehouse Video → Object Detection → Object Tracking → Human Pose Estimation → Structured Per-frame JSON

The resulting JSON acts as the interface between the Computer Vision module and the downstream Behaviour Risk module.
