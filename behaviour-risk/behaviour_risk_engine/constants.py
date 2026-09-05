"""
Class-name and geometry constants shared across behaviour detectors.

Updated 2026-09-06 (Member 2): the real demo footage (see the Google Drive
input-videos folder in the challenge doc) shows mattresses, cupboards, and
"KD packets" being handled, not just cartons — broadened PRODUCT_CLASSES to
match. This is a placeholder guess at Member 1's eventual class names:
their roadmap only planned to label person/carton/pallet/trolley in
Roboflow, which doesn't cover what's actually in the videos. Flagging to
the team — confirm real class names once Member 1 publishes labels.
"""

PERSON_CLASS = "person"
PRODUCT_CLASSES = {"carton", "mattress", "cupboard", "packet"}
SUPPORT_CLASSES = {"pallet"}
EQUIPMENT_CLASSES = {"trolley"}
STRAP_CLASSES = {"strap"}  # doesn't exist in any labeling plan yet — see strap_misuse.py

# Subset of PRODUCT_CLASSES that has a meaningful "this should be upright"
# expectation — a carton doesn't care about orientation, but a cupboard or
# mattress does. Used by wrong_orientation.py.
ORIENTATION_SENSITIVE_CLASSES = {"cupboard", "mattress"}
