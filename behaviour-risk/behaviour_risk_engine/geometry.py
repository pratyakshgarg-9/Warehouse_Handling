"""
Bounding-box geometry helpers shared by behaviour detectors. Pure functions
over [x1, y1, x2, y2] boxes — no track history or timing here (see
track_store.py for that).
"""

from __future__ import annotations

from .models import DetectedObject


def bboxes_overlap(a: list, b: list, pad: float = 0.0) -> bool:
    """True if box a (expanded by `pad` on every side) intersects box b."""
    ax1, ay1, ax2, ay2 = a[0] - pad, a[1] - pad, a[2] + pad, a[3] + pad
    bx1, by1, bx2, by2 = b
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def horizontal_overlap_ratio(a: list, b: list) -> float:
    """Overlap of a's and b's x-ranges as a fraction of the narrower box's width."""
    overlap = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    narrower_width = min(a[2] - a[0], b[2] - b[0])
    if narrower_width <= 0:
        return 0.0
    return overlap / narrower_width


def is_resting_on(
    top: DetectedObject,
    base: DetectedObject,
    max_gap_px: float = 15.0,
    min_horizontal_overlap: float = 0.2,
) -> bool:
    """True if `top`'s bottom edge sits close to `base`'s top edge with enough
    horizontal overlap to plausibly be stacked on it (not just side-by-side)."""
    vertical_gap = abs(top.y2 - base.y1)
    if vertical_gap > max_gap_px:
        return False
    return horizontal_overlap_ratio(top.bbox, base.bbox) >= min_horizontal_overlap


def overhang_ratio(top: DetectedObject, base: DetectedObject) -> float:
    """Fraction of `base`'s width that `top` overhangs past either edge.
    0 = fully supported within base's footprint; higher = more unsupported span."""
    if base.width <= 0:
        return 0.0
    left_overhang = max(0.0, base.x1 - top.x1)
    right_overhang = max(0.0, top.x2 - base.x2)
    return (left_overhang + right_overhang) / base.width


def bottom_strip(obj: DetectedObject, fraction: float = 0.15) -> list:
    """The bottom `fraction` of an object's bbox — used as a rough stand-in
    for "feet" when checking if a person is stepping on something, since the
    per-frame schema doesn't document keypoint index semantics yet (no
    confirmed mapping to e.g. MediaPipe's ankle landmarks). Revisit once
    Member 1 documents keypoint ordering in /shared."""
    strip_height = obj.height * fraction
    return [obj.x1, obj.y2 - strip_height, obj.x2, obj.y2]
