"""
shared/config.py

Single source of truth for paths and constants used across all four folders
(cv-pipeline, behaviour-risk, backend-assistant, dashboard). Import this
instead of hardcoding paths — see root-CLAUDE.md's "no hardcoded paths" rule.

Each member's code should do:
    from shared.config import EVENTS_DB_PATH, EVIDENCE_DIR, BEHAVIOUR_TYPES, RISK_LEVELS
"""

import os
from pathlib import Path

# Root of the repo (this file lives in /shared, so parent.parent is repo root)
REPO_ROOT = Path(__file__).resolve().parent.parent

# --- Shared storage paths -----------------------------------------------

# Member 3 owns the DB itself, but everyone needs to know where it lives
EVENTS_DB_PATH = os.environ.get(
    "EVENTS_DB_PATH", str(REPO_ROOT / "backend-assistant" / "events.db")
)

# Evidence frames written by Member 2, read by Member 3's assistant and
# Member 4's dashboard
EVIDENCE_DIR = os.environ.get("EVIDENCE_DIR", str(REPO_ROOT / "shared" / "evidence"))
Path(EVIDENCE_DIR).mkdir(parents=True, exist_ok=True)

# --- Shared enums (must match root-CLAUDE.md exactly) --------------------

BEHAVIOUR_TYPES = [
    "dropped",
    "dragged",
    "rough_handling",
    "stepping_on_product",
    "incorrect_stacking",
    "unstable_stacking",
    "outside_designated_area",
    "no_required_equipment",
    "pallet_incorrect_position",
    "pushed_or_thrown",
    "unsafe_loading_sequence",
    "rolling",
    "wrong_orientation",
    "strap_misuse",
]

RISK_LEVELS = ["Low", "Medium", "High", "Critical"]

# --- LLM / assistant config (Member 3) ------------------------------------

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq")  # or "gemini"
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")  # never commit real keys — use .env

# --- Helpers ---------------------------------------------------------------

def evidence_path_for(event_id: str) -> str:
    """Standard path for an event's evidence frame, per root-CLAUDE.md convention."""
    return str(Path(EVIDENCE_DIR) / f"{event_id}.jpg")
