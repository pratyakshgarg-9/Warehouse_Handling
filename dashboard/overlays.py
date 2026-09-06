"""
dashboard/overlays.py — draws AI-detected objects and behaviour events on video
frames (Member 4's core visual layer).

Colors are fixed per risk level / object class so every surface in the app
(player, inspector, evidence, timeline) reads as one system.
"""

from __future__ import annotations

import cv2

# BGR tuples for OpenCV drawing.
RISK_COLORS = {
    "Low": (94, 197, 34),        # green
    "Medium": (11, 179, 234),    # amber
    "High": (22, 115, 249),      # orange
    "Critical": (68, 68, 239),   # red
}

CLASS_COLORS = {
    "person": (255, 191, 128),   # light blue
    "carton": (51, 170, 219),    # warm orange-brown
    "pallet": (255, 94, 224),    # purple
    "trolley": (255, 229, 170),  # cyan
}

DEFAULT_CLASS_COLOR = (200, 200, 200)

BEHAVIOUR_LABELS = {
    "dropped": "DROPPED",
    "dragged": "DRAGGED",
    "rough_handling": "ROUGH HANDLING",
    "incorrect_stacking": "INCORRECT STACKING",
    "unstable_stacking": "UNSTABLE STACKING",
    "outside_designated_area": "OUTSIDE DESIGNATED AREA",
    "no_required_equipment": "NO REQUIRED EQUIPMENT",
    "pallet_incorrect_position": "PALLET INCORRECT POSITION",
    "pushed_or_thrown": "PUSHED / THROWN",
    "unsafe_loading_sequence": "UNSAFE LOADING SEQUENCE",
}


def _label(img, text, x, y, color, thickness=1):
    """Draw a filled label chip with text at (x, y) — keeps text legible on
    any background."""
    (tw, th), baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, thickness)
    y = max(y, th + 6)
    cv2.rectangle(img, (x, y - th - 6), (x + tw + 8, y + baseline), (25, 25, 25), -1)
    cv2.putText(img, text, (x + 4, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, thickness, cv2.LINE_AA)


def draw_objects(img, objects, highlight_tracks=None, show_confidence=True, show_keypoints=True):
    """Draw tracked-object bounding boxes in class colors.

    highlight_tracks: {track_id: (label, color)} — objects involved in the
    currently selected event get the event's risk color + behaviour label.
    """
    highlight_tracks = highlight_tracks or {}
    for obj in objects:
        x1, y1, x2, y2 = [int(v) for v in obj["bbox"]]
        track_id, cls = obj.get("track_id"), obj.get("class", "object")
        is_hot = track_id in highlight_tracks
        color = highlight_tracks[track_id][1] if is_hot else CLASS_COLORS.get(cls, DEFAULT_CLASS_COLOR)
        thickness = 3 if is_hot else 1

        cv2.rectangle(img, (x1, y1), (x2, y2), color, thickness)

        parts = [f"{cls} #{track_id}"]
        if show_confidence and obj.get("confidence") is not None:
            parts.append(f"{obj['confidence']:.2f}")
        text = " ".join(parts)
        if is_hot:
            text = f"{highlight_tracks[track_id][0]} | {text}"
        _label(img, text, x1, y1, color, thickness=1 if not is_hot else 2)

        if show_keypoints and obj.get("keypoints"):
            for kp in obj["keypoints"]:
                kx, ky = int(kp[0]), int(kp[1])
                cv2.circle(img, (kx, ky), 3, (60, 60, 255), -1)


def draw_event_banner(img, event_row, ts_text=""):
    """Top-of-frame banner: behaviour label + risk chip + timestamp."""
    h, w = img.shape[:2]
    risk = event_row.get("risk_level", "Low")
    color = RISK_COLORS.get(risk, DEFAULT_CLASS_COLOR)
    label = BEHAVIOUR_LABELS.get(event_row.get("behaviour_type", ""), "EVENT")

    cv2.rectangle(img, (0, 0), (w, 46), (25, 25, 25), -1)
    cv2.rectangle(img, (0, 0), (10, 46), color, -1)
    cv2.putText(img, f"{label}  —  RISK: {risk.upper()}", (22, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    if ts_text:
        (tw, _), _ = cv2.getTextSize(ts_text, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.putText(img, ts_text, (w - tw - 16, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (230, 230, 230), 1, cv2.LINE_AA)


def draw_zone(img, zone, label="DESIGNATED AREA"):
    """Dashed outline of the designated handling zone (static scene context)."""
    x1, y1, x2, y2 = zone
    dash, gap = 18, 10
    color = (0, 220, 220)  # yellow (BGR)
    for edge in (
        [(x1, y1, x2, y1), (x1, y2, x2, y2)],  # horizontals
        [(x1, y1, x1, y2), (x2, y1, x2, y2)],  # verticals
    ):
        for ex1, ey1, ex2, ey2 in edge:
            if ey1 == ey2:  # horizontal
                x = ex1
                while x < ex2:
                    cv2.line(img, (x, ey1), (min(x + dash, ex2), ey2), color, 2)
                    x += dash + gap
            else:           # vertical
                y = ey1
                while y < ey2:
                    cv2.line(img, (ex1, y), (ex2, min(y + dash, ey2)), color, 2)
                    y += dash + gap
    _label(img, label, x1, y1 - 4, color)


def bgr_to_rgb(img):
    import cv2  # noqa: F401  (kept for symmetry; conversion is pure numpy below)
    return img[:, :, ::-1]
