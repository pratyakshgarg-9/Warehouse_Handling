"""
Class-name and geometry constants shared across behaviour detectors.

Updated 2026-09-06 (Member 2): the real demo footage (see the Google Drive
input-videos folder in the challenge doc) shows mattresses, cupboards, and
"KD packets" being handled, not just cartons — broadened PRODUCT_CLASSES to
match. This was a placeholder guess at Member 1's eventual class names.

Updated 2026-09-07 (Member 2), now that Member 1 has published a real
pipeline + output (cv-pipeline/models/best.pt, cv-pipeline/outputs/*.json):
the actual trained model only detects "person", "box", and "forklift" —
confirmed by inspecting the real output JSON. It was never trained on
pallet, trolley, strap, cupboard, or mattress. cv_pipeline_adapter.py maps
"box" to "carton" so PRODUCT_CLASSES below still matches; the sets stay
broad (forward-compatible) in case Member 1 trains a richer model later,
but as of today, **pallet_incorrect_position, strap_misuse, and
wrong_orientation cannot produce any events against real detections** —
every class they depend on is simply never in the model's vocabulary. See
cv_pipeline_adapter.py's module docstring for the full mapping.
"""

PERSON_CLASS = "person"
PRODUCT_CLASSES = {"carton", "mattress", "cupboard", "packet"}
SUPPORT_CLASSES = {"pallet"}
EQUIPMENT_CLASSES = {"trolley"}
STRAP_CLASSES = {"strap"}  # not in the trained model's vocabulary yet — see strap_misuse.py
VEHICLE_CLASSES = {"forklift"}  # detected by the real model but not used by any behaviour yet

# Subset of PRODUCT_CLASSES that has a meaningful "this should be upright"
# expectation — a carton doesn't care about orientation, but a cupboard or
# mattress does. Used by wrong_orientation.py. Neither class is in the real
# trained model's vocabulary yet (see module docstring).
ORIENTATION_SENSITIVE_CLASSES = {"cupboard", "mattress"}
