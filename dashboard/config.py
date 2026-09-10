"""
dashboard/config.py — Member 4 dashboard configuration.

Resolves where the dashboard reads data from, using shared/config.py as the
single source of truth (per root-CLAUDE.md's no-hardcoded-paths rule).

Data source resolution (in order):
  1. DASHBOARD_TEST_MODE=1  -> force the generated sample dataset
  2. DASHBOARD_TEST_MODE=0  -> force the real event store (empty state if absent)
  3. otherwise              -> real event store if backend-assistant/events.db
                               exists, else the sample dataset if present.

Whenever the sample dataset is active the UI shows a loud "SAMPLE DATA" badge —
we never present generated data as real pipeline output.

Optional env overrides (all default to the sample assets when they exist):
  DASHBOARD_VIDEO_PATH       path to the session video (mp4)
  DASHBOARD_DETECTIONS_PATH  path to per-frame detections JSON (Member 1 format)
  DASHBOARD_VIDEO_START_UTC  ISO-8601 UTC timestamp of video frame 0
  ASSISTANT_URL              HTTP endpoint for Member 3's assistant
                             (POST {"question": ...} -> {"answer": ...})
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# --- make `shared.config` and the dashboard's own modules importable -------
DASH_DIR = Path(__file__).resolve().parent
REPO_ROOT = DASH_DIR.parent
for _p in (str(REPO_ROOT), str(DASH_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from shared.config import EVENTS_DB_PATH, EVIDENCE_DIR  # noqa: E402

# --- layout constants --------------------------------------------------------

TEST_DATA_DIR = DASH_DIR / "test_data"
TEST_DB_PATH = TEST_DATA_DIR / "events.db"
TEST_EVIDENCE_DIR = TEST_DATA_DIR / "evidence"
TEST_MANIFEST_PATH = TEST_DATA_DIR / "manifest.json"

def _resolve_repo_path(value: str) -> str:
    """A relative DASHBOARD_VIDEO_PATH / DASHBOARD_DETECTIONS_PATH is only
    correct if Streamlit happens to be launched from the exact repo root —
    launched from anywhere else (a subfolder, a different terminal tab), the
    plain Path(value).exists() check below silently fails and the whole
    Video Review page falls back to "no session video available" with
    nothing else rendered (confirmed reproducing this on two machines,
    2026-09-10). Resolve relative paths against REPO_ROOT instead of the
    process cwd so the page works regardless of where it was launched from."""
    if not value:
        return value
    p = Path(value)
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    return str(p)


RISK_ORDER = ["Low", "Medium", "High", "Critical"]

# Shift windows (UTC hours) used for shift summaries — matches a standard
# 3-shift warehouse rota. Only used for *grouping*, never for detection.
SHIFTS = [
    ("Morning", (6, 14)),
    ("Evening", (14, 22)),
    ("Night", (22, 6)),
]

# Columns the dashboard expects in Member 3's `events` table (the published
# event schema in root-CLAUDE.md — the dashboard is read-only against it).
EVENT_COLUMNS = [
    "event_id",
    "timestamp",
    "behaviour_type",
    "risk_level",
    "risk_score",
    "bay",
    "object_ids",
    "evidence_frame_path",
    "explanation",
]


# --- data source resolution --------------------------------------------------

def resolve_data_source() -> dict:
    """Decide which event store / evidence folder the dashboard reads this run.

    Returns a dict with: db_path, evidence_dir, is_sample, reason, available.
    """
    forced = os.environ.get("DASHBOARD_TEST_MODE", "").strip().lower()
    real_db = Path(EVENTS_DB_PATH)

    if forced == "1":
        return _sample_source("forced by DASHBOARD_TEST_MODE=1")
    if forced == "0":
        return _real_source()

    if real_db.exists():
        return _real_source()
    if TEST_DB_PATH.exists():
        return _sample_source(
            "real event store not found (backend-assistant/events.db) — "
            "showing generated sample data"
        )
    return {
        "db_path": str(real_db),
        "evidence_dir": EVIDENCE_DIR,
        "is_sample": False,
        "reason": "no event store found (neither real nor sample)",
        "available": False,
    }


def _real_source() -> dict:
    return {
        "db_path": EVENTS_DB_PATH,
        "evidence_dir": EVIDENCE_DIR,
        "is_sample": False,
        "reason": f"reading real event store at {EVENTS_DB_PATH}",
        "available": Path(EVENTS_DB_PATH).exists(),
    }


def _sample_source(reason: str) -> dict:
    return {
        "db_path": str(TEST_DB_PATH),
        "evidence_dir": str(TEST_EVIDENCE_DIR),
        "is_sample": True,
        "reason": reason,
        "available": TEST_DB_PATH.exists(),
    }


# --- session video / detections (for the Video Review page) ------------------

def resolve_session_media() -> dict:
    """Resolve the demo video, its per-frame detections, and the UTC time of
    frame 0 (needed to map event timestamps -> video seek positions).

    Defaults to the generated sample session; every piece is overridable via
    env vars so Member 1's real output drops in without code changes.
    """
    manifest = {}
    if TEST_MANIFEST_PATH.exists():
        manifest = json.loads(TEST_MANIFEST_PATH.read_text(encoding="utf-8"))

    video_path = _resolve_repo_path(os.environ.get(
        "DASHBOARD_VIDEO_PATH", str(TEST_DATA_DIR / manifest.get("video", ""))
        if manifest.get("video") else ""
    ))
    detections_path = _resolve_repo_path(os.environ.get(
        "DASHBOARD_DETECTIONS_PATH",
        str(TEST_DATA_DIR / "demo_session_detections.json"),
    ))
    video_start_utc = os.environ.get(
        "DASHBOARD_VIDEO_START_UTC", manifest.get("video_start_utc", "")
    )

    return {
        "video_path": video_path,
        "video_exists": bool(video_path) and Path(video_path).exists(),
        "detections_path": detections_path,
        "detections_exist": Path(detections_path).exists() if detections_path else False,
        "video_start_utc": video_start_utc,
        "fps": manifest.get("fps"),
        "duration_s": manifest.get("duration_s"),
        "bay": manifest.get("session_bay"),
    }
