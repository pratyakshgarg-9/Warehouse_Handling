"""
Class-name and geometry constants shared across behaviour detectors.

Pilot scope (per docs/AI_Video_Intelligence_Project_Spec.md) is 1 product
category, so PRODUCT_CLASSES is just "carton" for now. If the pilot's product
category changes, update here rather than in each detector.
"""

PERSON_CLASS = "person"
PRODUCT_CLASSES = {"carton"}
SUPPORT_CLASSES = {"pallet"}
EQUIPMENT_CLASSES = {"trolley"}
