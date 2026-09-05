# Member 2 — Behaviour Intelligence & Risk Scoring — CLAUDE.md

This file is auto-loaded by Claude Code whenever you work inside `/behaviour-risk`.
It's loaded together with the repo's root `CLAUDE.md` (shared contract) — you
don't need to paste either into your prompts.

## Folder scope
You own `/behaviour-risk`. Never read, edit, or refactor files outside this
folder and `/shared` unless the owning member explicitly asks you to.

## Role summary
You turn Member 1's per-frame detections into named behaviours and
risk-classified events — this is the core "intelligence" the challenge doc
asks for: Object Detection + Tracking + Behaviour Recognition + Risk
Classification working together, not just object detection alone.

## What you own (produce)
- The rule-based state machine covering all 11 target behaviours: dropped,
  dragged, rough_handling, stepping_on_product, incorrect_stacking,
  unstable_stacking, outside_designated_area, no_required_equipment,
  pallet_incorrect_position, pushed_or_thrown, unsafe_loading_sequence.
  (`stepping_on_product` added 2026-09-06 — the doc's "stepping or standing
  on cartons" behaviour had no dedicated enum slot before; see the root
  CLAUDE.md's changelog note on the enum.)
- The risk scoring formula (behaviour type, product involved, drop height,
  duration, stacking configuration, repeat frequency, location), mapped to
  Low/Medium/High/Critical.
- The explanation string per event (bad practice → correct practice, drawn
  from the challenge doc's table) — this is what powers the assistant's
  "why was this flagged?" answers.
- Events written via Member 3's insert function, matching the event schema
  in the root `CLAUDE.md` exactly.

## What you consume
- Member 1's per-frame output stream (format defined in the root `CLAUDE.md`).
- Member 3's event-insert function (call it — never write to the DB directly).

## Timeline

| Day | Tasks |
| --- | --- |
| Sep 4 | Review the 10 behaviours and the good/bad practice table; sketch state machine logic for each. |
| Sep 5 | Build the state machine skeleton against Member 1's format; implement the 3-4 easiest behaviours (drop, drag, stepping-on-carton, incorrect stacking). |
| Sep 6 | Wire to Member 1's live stream; get first 4-5 behaviours producing real events; implement the risk scoring formula. |
| Sep 7 | Implement remaining behaviours to reach all 10; finalize risk thresholds; write explanation strings. |
| Sep 8-9 | Tune against false positives/negatives found in testing; support demo scenario selection. |

## Integration checkpoints
- **Sep 6:** first real events must land in Member 3's event store, matching the schema exactly — this is the whole team's first integration checkpoint.
- **Sep 7:** all 10 behaviours producing events, so Member 4's dashboard has real data to build against for the rest of the week.

## Rules
- Don't touch `/cv-pipeline`, `/backend-assistant`, or `/dashboard` code.
- Never write risk levels as "confirmed damage" — the doc requires the distinction Observed behaviour → Potential risk → Confirmed damage. Stay at "potential risk" unless there's clear evidence.
- Any change to the event schema goes through `/shared` and gets flagged to the whole team first — don't change it silently just because it's convenient for your own logic.
- No feature outside the challenge doc's scope gets added, even if it seems easy to bolt on — flag ideas instead of building them.
