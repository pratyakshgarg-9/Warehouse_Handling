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
    if details.get("cause") == "stepping_on_product":
        return (
            "A person stepped or stood on the product instead of handling it directly. "
            "Potential risk: crushing damage from applied body weight. "
            "Correct practice: never use product packaging as a step or support surface — use designated equipment."
        )
    return (
        "Product experienced a sudden, high-force impact consistent with rough handling. "
        "Potential risk: internal or structural damage from excessive force. "
        "Correct practice: handle products with smooth, deliberate movements and avoid sudden jolts or impacts."
    )


def _incorrect_stacking(details: dict) -> str:
    return (
        "Product was stacked with an unsupported overhang beyond the footprint of the carton below it. "
        "Potential risk: the stack toppling and damaging the product or surrounding stock. "
        "Correct practice: stack products fully within the footprint of the layer below, keeping stacks vertical and evenly supported."
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
    "incorrect_stacking": _incorrect_stacking,
}


def build_explanation(behaviour_type: str, details: dict) -> str:
    template = _TEMPLATES.get(behaviour_type, _fallback)
    return template(details)
