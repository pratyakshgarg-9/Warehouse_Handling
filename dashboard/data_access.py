"""
dashboard/data_access.py — Member 4's READ-ONLY view of the event store.

Everything here treats Member 3's SQLite DB (`events` table, schema published
in root-CLAUDE.md) and Member 1's per-frame detections as contracts:
  - connections are opened read-only (mode=ro) — we can never write to them
  - nothing is invented: if the store is empty or a query returns nothing,
    callers get an honest empty result and render an empty state
  - unexpected schemas surface as clear errors instead of silent fallbacks
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd

import config  # dashboard/config.py


# --- event store ---------------------------------------------------------------

def _connect_ro(db_path: str) -> sqlite3.Connection:
    """Open the event store strictly read-only.

    Uses a file: URI so the path is properly percent-encoded (repo paths may
    contain spaces) and SQLite refuses to create/modify the file.
    """
    uri = Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def load_events(db_path: str) -> pd.DataFrame:
    """Load all events into a typed DataFrame.

    Raises sqlite3.Error / ValueError upward — the UI layer converts these
    into honest error messages rather than showing partial or made-up data.
    """
    conn = _connect_ro(db_path)
    try:
        df = pd.read_sql_query("SELECT * FROM events", conn)
    finally:
        conn.close()

    missing = [c for c in config.EVENT_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Event store is missing expected column(s): {', '.join(missing)}. "
            "The dashboard is built against the event schema in root-CLAUDE.md — "
            "flag any schema change to the team."
        )

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
    df["object_ids"] = df["object_ids"].apply(_parse_object_ids)
    df["risk_level"] = pd.Categorical(
        df["risk_level"], categories=config.RISK_ORDER, ordered=True
    )
    return df.sort_values("timestamp").reset_index(drop=True)


def _parse_object_ids(raw) -> list:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    if isinstance(raw, (list, tuple)):
        return list(raw)
    try:
        parsed = json.loads(str(raw))
        return parsed if isinstance(parsed, list) else [parsed]
    except (json.JSONDecodeError, TypeError):
        return []


def events_in_window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """Events whose timestamp falls in [start, end] — used to link events to
    the session video's timeline."""
    if df.empty:
        return df
    mask = (df["timestamp"] >= start) & (df["timestamp"] <= end)
    return df[mask]


def shift_of(ts: pd.Timestamp) -> str:
    """Map a UTC timestamp to its shift name (config.SHIFTS windows)."""
    h = ts.hour
    for name, (a, b) in config.SHIFTS:
        if a < b and a <= h < b:      # e.g. Morning 06-14
            return name
        if a > b and (h >= a or h < b):  # e.g. Night 22-06 wraps midnight
            return name
    return "Unknown"


def resolve_evidence_path(row, evidence_dir: str) -> Path | None:
    """Find an event's evidence frame: try the shared evidence dir by
    convention first (<evidence_dir>/<event_id>.jpg), then the path stored
    in the event row (relative to the repo root)."""
    by_convention = Path(evidence_dir) / f"{row['event_id']}.jpg"
    if by_convention.exists():
        return by_convention
    stored = row.get("evidence_frame_path")
    if isinstance(stored, str) and stored:
        candidates = [
            config.REPO_ROOT / stored,
            Path(stored) if Path(stored).is_absolute() else None,
        ]
        for c in candidates:
            if c and c.exists():
                return c
    return None


# --- per-frame detections (Member 1's published format) ------------------------

def load_detections(detections_path: str) -> dict[int, dict]:
    """Load per-frame detections JSON into {frame_id: frame_dict}.

    Expected frame shape (root-CLAUDE.md):
      {"frame_id": 1042, "timestamp": "...", "objects": [{track_id, class,
       bbox, confidence, keypoints?}]}
    """
    data = json.loads(Path(detections_path).read_text(encoding="utf-8"))
    frames = data["frames"] if isinstance(data, dict) else data
    return {int(f["frame_id"]): f for f in frames}


def detections_at(detections: dict[int, dict], frame_id: int) -> dict:
    """Detections for the nearest available frame at or before `frame_id`
    (tracks are persistent, so the most recent frame is the right context)."""
    if not detections:
        return {"frame_id": frame_id, "timestamp": None, "objects": []}
    ids = [fid for fid in detections if fid <= frame_id]
    return detections[max(ids)] if ids else detections[min(detections)]


def read_video_frame(video_path: str, frame_id: int) -> "object | None":
    """Decode a single frame by index without loading the whole video."""
    import cv2  # local import so pages that don't need video skip cv2 startup

    cap = cv2.VideoCapture(video_path)
    try:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
        ok, frame = cap.read()
        return frame if ok else None
    finally:
        cap.release()


def video_meta(video_path: str) -> dict:
    """fps / frame count / resolution of the session video."""
    import cv2

    cap = cv2.VideoCapture(video_path)
    try:
        return {
            "fps": cap.get(cv2.CAP_PROP_FPS) or 15.0,
            "frames": int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0),
            "w": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            "h": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
        }
    finally:
        cap.release()
