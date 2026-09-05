"""
Per-event explanation strings: "flagged because... correct practice is...".

This is what powers the assistant's "why was this event high risk?" answers
(root CLAUDE.md's assistant contract) and the doc's requirement for
explainability. Every template stays at "potential risk" language, per
behaviour-risk/CLAUDE.md: never assert confirmed damage without evidence.

Bad-practice / good-practice pairing follows the challenge doc's behaviour
list (docs/AI_Video_Intelligence_Project_Spec.md §3); exact doc-table
wording wasn't available to write against, so phrasing here is a
reasonable first pass — swap in the doc's literal text if the team has it.
"""

from __future__ import annotations

from typing import Callable, Dict


def _dropped(details: dict) -> str:
    return (
        "Product underwent a rapid, uncontrolled fall rather than being lowered under control. "
        "Potential risk: impact damage to the product or its contents. "
        "Correct practice: lift and lower cartons with a controlled, supported motion — never let them fall or drop from height."
    )


def _dragged(details: dict) -> str:
    return (
        "Product was dragged across the floor instead of being lifted clear of the ground. "
        "Potential risk: surface abrasion, seam damage, or contamination to the product. "
        "Correct practice: lift the product fully before moving it, using a trolley for longer distances."
    )


def _rough_handling(details: dict) -> str:
    return (
        "Product experienced a sudden, high-force impact while still being actively handled. "
        "Potential risk: internal or structural damage from excessive force. "
        "Correct practice: handle products with smooth, deliberate movements and avoid sudden jolts or impacts."
    )


def _stepping_on_product(details: dict) -> str:
    return (
        "A person stepped or stood on the product instead of handling it directly. "
        "Potential risk: crushing damage from applied body weight. "
        "Correct practice: never use product packaging as a step or support surface — use designated equipment."
    )


def _incorrect_stacking(details: dict) -> str:
    return (
        "Product was stacked with an unsupported overhang beyond the footprint of the carton below it. "
        "Potential risk: the stack toppling and damaging the product or surrounding stock. "
        "Correct practice: stack products fully within the footprint of the layer below, keeping stacks vertical and evenly supported."
    )


def _unstable_stacking(details: dict) -> str:
    return (
        "Product was stacked into a tall, narrow configuration relative to its base — top-heavy even without an overhang. "
        "Potential risk: the stack toppling under its own height. "
        "Correct practice: keep stacks low and wide relative to their base, and avoid building higher than the product's rated stacking limit."
    )


def _outside_designated_area(details: dict) -> str:
    return (
        "Product was placed to rest outside the bay's designated staging area. "
        "Potential risk: obstruction of the work area, misplaced inventory, or accidental damage from passing traffic or equipment. "
        "Correct practice: place products only within the marked designated area for this process."
    )


def _no_required_equipment(details: dict) -> str:
    return (
        "Product was carried a substantial distance by hand with no handling equipment used. "
        "Potential risk: strain-related mishandling or drops over a long manual carry. "
        "Correct practice: use a trolley or other designated equipment for moves beyond a short distance."
    )


def _pallet_incorrect_position(details: dict) -> str:
    return (
        "Product overhangs the footprint of the pallet it's resting on. "
        "Potential risk: the product or pallet becoming unstable during transport or storage. "
        "Correct practice: center products fully within the pallet's footprint, or use a larger pallet for oversized products."
    )


def _pushed_or_thrown(details: dict) -> str:
    return (
        "Product was moving at high speed with nobody in contact with it, consistent with being pushed or thrown rather than carried. "
        "Potential risk: impact damage on landing or collision with other stock. "
        "Correct practice: always carry or lower products by hand — never push or throw them to their destination."
    )


def _unsafe_loading_sequence(details: dict) -> str:
    return (
        "Multiple products were in motion at the same time, consistent with an uncoordinated, non-sequential handling process. "
        "Potential risk: collisions or drops from handling several items without a stable one-at-a-time plan. "
        "Correct practice: stage and move products one at a time in a planned sequence."
    )


def _fallback(details: dict) -> str:
    return (
        "An irregular handling pattern was detected for this behaviour type. "
        "Potential risk: possible product damage. "
        "Correct practice: follow standard handling procedure for this process."
    )


_TEMPLATES: Dict[str, Callable[[dict], str]] = {
    "dropped": _dropped,
    "dragged": _dragged,
    "rough_handling": _rough_handling,
    "stepping_on_product": _stepping_on_product,
    "incorrect_stacking": _incorrect_stacking,
    "unstable_stacking": _unstable_stacking,
    "outside_designated_area": _outside_designated_area,
    "no_required_equipment": _no_required_equipment,
    "pallet_incorrect_position": _pallet_incorrect_position,
    "pushed_or_thrown": _pushed_or_thrown,
    "unsafe_loading_sequence": _unsafe_loading_sequence,
}


def build_explanation(behaviour_type: str, details: dict) -> str:
    template = _TEMPLATES.get(behaviour_type, _fallback)
    return template(details)
