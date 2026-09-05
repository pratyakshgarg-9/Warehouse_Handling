"""
Risk scoring formula (v1), per docs/AI_Video_Intelligence_Project_Spec.md §6:

    risk_score = severity(behaviour_type) + impact_estimate(...)
                 + duration_factor + repeat_factor + location_factor

All weights below are first-pass guesses, not calibrated against real
footage yet — expected to be tuned during Sep 7-9 (finalize risk thresholds /
tune against false positives) per the roadmap. Keep the four-term shape
intact when tuning so the formula stays traceable to the spec.

Every score is capped to [0, 1] and bucketed into the doc's four risk
levels. Nothing here ever asserts confirmed damage — only a risk level for
a potential-risk event, per behaviour-risk/CLAUDE.md's explicit rule.
"""

from __future__ import annotations

from typing import Dict

# Base severity per behaviour_type — how bad this class of event is before
# looking at the specifics of this instance. Matches the shared enum in the
# root CLAUDE.md exactly; unlisted types are handled with a safe default.
BASE_SEVERITY: Dict[str, float] = {
    "dropped": 0.35,
    "dragged": 0.20,
    "rough_handling": 0.30,
    "stepping_on_product": 0.30,
    "incorrect_stacking": 0.30,
    "unstable_stacking": 0.30,
    "outside_designated_area": 0.15,
    "no_required_equipment": 0.20,
    "pallet_incorrect_position": 0.20,
    "pushed_or_thrown": 0.35,
    "unsafe_loading_sequence": 0.25,
    "rolling": 0.25,
    "wrong_orientation": 0.20,
    "strap_misuse": 0.20,
}
DEFAULT_SEVERITY = 0.20

# Per-bay risk adjustment. Pilot scope is a single bay, so this is a no-op
# hook today — kept as a lookup (not a constant) so a later bay can be
# weighted without touching the formula's shape.
BAY_LOCATION_FACTOR: Dict[str, float] = {
    "bay_1": 0.0,
}
DEFAULT_LOCATION_FACTOR = 0.0

DURATION_FACTOR_WEIGHT = 0.15
DURATION_FACTOR_SATURATION_S = 5.0  # duration at/above this gets the full weight

REPEAT_FACTOR_WEIGHT = 0.10
REPEAT_FACTOR_SATURATION_COUNT = 5  # repeat count at/above this gets the full weight


def _impact_estimate(behaviour_type: str, details: dict) -> float:
    """Behaviour-specific proxy for "how much force/instability was
    involved", normalized to [0, 0.4]. No camera calibration in the pilot
    (no known pixels-per-metre), so these stay pixel/ratio-based proxies
    rather than real-world units — revisit once Member 1 publishes a
    calibrated scale.
    """
    if behaviour_type == "dropped":
        px = details.get("drop_displacement_px", 0.0)
        return min(px / 200.0, 1.0) * 0.4
    if behaviour_type in ("incorrect_stacking", "unstable_stacking"):
        ratio = details.get("overhang_ratio", 0.0)
        return min(ratio / 1.0, 1.0) * 0.4
    if behaviour_type == "rough_handling":
        speed = details.get("peak_speed_px_s", 0.0)
        return min(speed / 1000.0, 1.0) * 0.4
    if behaviour_type == "stepping_on_product":
        return 0.15  # consistent, moderate impact estimate for applied body weight
    if behaviour_type == "dragged":
        distance = details.get("distance_px", 0.0)
        return min(distance / 300.0, 1.0) * 0.4
    if behaviour_type == "unstable_stacking":
        ratio = details.get("height_to_width_ratio", 0.0)
        return min(ratio / 3.0, 1.0) * 0.4
    if behaviour_type == "outside_designated_area":
        return 0.1  # placement violation; no distance-from-zone signal yet to grade severity further
    if behaviour_type == "no_required_equipment":
        distance = details.get("distance_px", 0.0)
        return min(distance / 400.0, 1.0) * 0.4
    if behaviour_type == "pallet_incorrect_position":
        ratio = details.get("overhang_ratio", 0.0)
        return min(ratio / 1.0, 1.0) * 0.4
    if behaviour_type == "pushed_or_thrown":
        speed = details.get("peak_speed_px_s", 0.0)
        return min(speed / 800.0, 1.0) * 0.4
    if behaviour_type == "unsafe_loading_sequence":
        count = details.get("concurrent_count", 0)
        return min(count / 6.0, 1.0) * 0.4
    if behaviour_type == "rolling":
        wobble = details.get("aspect_ratio_wobble", 0.0)
        return min(wobble / 1.0, 1.0) * 0.4
    if behaviour_type == "wrong_orientation":
        ratio = details.get("width_to_height_ratio", 0.0)
        return min(max(ratio - 1.0, 0.0) / 2.0, 1.0) * 0.4
    if behaviour_type == "strap_misuse":
        return 0.15  # consistent moderate estimate; no strength/force signal available
    return 0.1


def _duration_factor(details: dict) -> float:
    duration_s = details.get("duration_s") or details.get("fall_duration_s") or 0.0
    return min(duration_s / DURATION_FACTOR_SATURATION_S, 1.0) * DURATION_FACTOR_WEIGHT


def _repeat_factor(repeat_count: int) -> float:
    return min(repeat_count / REPEAT_FACTOR_SATURATION_COUNT, 1.0) * REPEAT_FACTOR_WEIGHT


def compute_risk_score(behaviour_type: str, details: dict, bay: str, repeat_count: int) -> float:
    severity = BASE_SEVERITY.get(behaviour_type, DEFAULT_SEVERITY)
    impact = _impact_estimate(behaviour_type, details)
    duration = _duration_factor(details)
    repeat = _repeat_factor(repeat_count)
    location = BAY_LOCATION_FACTOR.get(bay, DEFAULT_LOCATION_FACTOR)

    return max(0.0, min(1.0, severity + impact + duration + repeat + location))


def bucket(score: float) -> str:
    if score < 0.25:
        return "Low"
    if score < 0.5:
        return "Medium"
    if score < 0.75:
        return "High"
    return "Critical"
