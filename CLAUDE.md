# WAREHOUSE-AI — Root Project Context

## What this is
AI Video Intelligence for Warehouse Handling — analyses warehouse loading/unloading
footage, detects damage-causing behaviours, assigns a risk level per event, and
exposes both a dashboard and a conversational assistant over the results.
Hackathon project, 6-day build (4-10 September 2026), 4-person team.

Scope is exactly what's defined in `docs/AI_Video_Intelligence_Project_Spec.md` —
no features beyond the challenge document get added mid-build.

## Who's building what
Each member owns exactly one folder. Read/reference other folders freely, but
only the owning member edits inside them unless they explicitly ask for help.

| Member | Folder | Owns |
| --- | --- | --- |
| Member 1 | `/cv-pipeline` | Detection, tracking, pose estimation |
| Member 2 | `/behaviour-risk` | Behaviour state machine, risk scoring |
| Member 3 | `/backend-assistant` | Event store, conversational assistant |
| Member 4 | `/dashboard` | Streamlit UI, overlays, replay, demo assets |

## Repo layout
```
/cv-pipeline        <- Member 1
/behaviour-risk     <- Member 2
/backend-assistant  <- Member 3
/dashboard          <- Member 4
/shared             <- schemas, conventions, evidence frames — source of truth
/docs               <- roadmap + member specs
```

## Shared contract — do not change without updating `/shared` and telling the team

### Behaviour type enum (Member 2 produces, everyone else reads)
```
dropped | dragged | rough_handling | stepping_on_product | incorrect_stacking |
unstable_stacking | outside_designated_area | no_required_equipment |
pallet_incorrect_position | pushed_or_thrown | unsafe_loading_sequence |
rolling | wrong_orientation | strap_misuse
```
Updated 2026-09-06 (Member 2): added `stepping_on_product` — the doc's
"stepping or standing on cartons" behaviour had no dedicated slot (the
original 10 entries covered only 9 of the doc's 10 required behaviours,
since stacking was split into two). Nothing downstream was built against
the old list yet, so this was a safe time to fix it. `shared/config.py`'s
`BEHAVIOUR_TYPES` has been updated to match — re-import from there rather
than hardcoding the list elsewhere.

Updated 2026-09-06 (Member 2), second pass: added `rolling`,
`wrong_orientation`, and `strap_misuse` after checking the actual input
videos (Google Drive folder linked from the challenge doc). The real demo
footage includes "Rolling and dragging on wet floor", "Rolling and
dropping carton", "...vertical product kept horizontally...", and
"...using strap to hold" — none of which any prior behaviour covered. It
also shows mattresses, cupboards, and "KD packets" being handled, not just
cartons — `behaviour_risk_engine/constants.py`'s `PRODUCT_CLASSES` was
broadened to match. **This affects Member 1's labeling plan**: the
roadmap only planned to label person/carton/pallet/trolley in Roboflow,
which doesn't cover mattress/cupboard/packet/strap — worth confirming
real class names with Member 1 once their detector is running on the
actual footage.

### Risk level enum
```
Low | Medium | High | Critical
```

### Per-frame detection/tracking output (Member 1 produces, Member 2 consumes)
```json
{
  "frame_id": 1042,
  "timestamp": "2026-09-06T10:15:03Z",
  "objects": [
    {
      "track_id": 7,
      "class": "carton",
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.91
    },
    {
      "track_id": 3,
      "class": "person",
      "bbox": [x1, y1, x2, y2],
      "confidence": 0.95,
      "keypoints": [[x, y, conf], "..."]
    }
  ]
}
```
**⚠ This example was never real — it's what Member 2 originally assumed
before Member 1's pipeline existed.** The actual, confirmed schema is now
published at [`shared/cv_pipeline_schema.md`](shared/cv_pipeline_schema.md)
— treat that file as the source of truth for this contract, not the JSON
above. Short version: real frames use `class_name` not `class`,
`timestamp_ms` (int, frame-relative) not `timestamp` (ISO string),
`pose: {landmarks: [...]}` not `keypoints`, `track_id: -1` for untracked
detections, and the trained model only produces `person`/`box`/`forklift`.
**Member 4**: `dashboard/data_access.py`'s `load_detections()` is written
against the schema shown above, not the real one — see the shared schema
doc's "who needs to know this" section.

### Event schema (Member 2 produces, Member 3 stores, Member 4 reads)
```json
{
  "event_id": "evt_00042",
  "timestamp": "2026-09-06T10:15:04Z",
  "behaviour_type": "dropped",
  "risk_level": "High",
  "risk_score": 0.78,
  "bay": "bay_1",
  "object_ids": [7, 3],
  "evidence_frame_path": "shared/evidence/evt_00042.jpg",
  "explanation": "Product dropped from approximately 1 metre during unloading. Recommended action: inspect product and review unloading practice."
}
```
Written to the SQLite event store owned by Member 3 (`/backend-assistant/events.db`,
table `events`) via the insert function Member 3 publishes — Member 2 calls that
function rather than writing to the DB directly.

### Assistant contract (Member 3's service — Member 4's dashboard calls it)
Input: a natural-language question. Output: an answer generated only from rows in
the `events` table — never invented information, per the challenge doc's requirement.

### Evidence frames
Stored under `/shared/evidence/<event_id>.jpg`. Any component that needs to show
"what the camera saw" for an event reads from this path — don't duplicate frame
storage elsewhere.

### Conventions
- Timestamps: ISO 8601, UTC.
- Event IDs: `evt_` + zero-padded sequence number.
- No hardcoded file paths outside what's defined in `/shared` — use a shared
  config (`shared/config.py` or `.env`) for the SQLite path and evidence folder.

## Current status (update as the project moves — each member updates only their own line)
- [ ] `/cv-pipeline` producing stable per-frame output (Member 1)
- [x] `/behaviour-risk` producing events for all 14 behaviours (see the enum above) — tested standalone against synthetic sample data. **Wired to Member 1's real published output 2026-09-07**: their actual per-frame JSON diverges from the schema documented above (`class_name` not `class`, `timestamp_ms` int not `timestamp` ISO string, `pose.landmarks` not `keypoints`, `track_id: -1` for untracked detections) — bridged via `behaviour-risk/behaviour_risk_engine/cv_pipeline_adapter.py`, see its docstring for the full mapping and rationale. First run against the 2 generic files already in `cv-pipeline/outputs/` produced 0 events, correctly (neither contains a real product incident). **Then ran Member 1's actual pipeline on 2 real Drive demo clips** ("Rolling and dragging on wet floor", "Rolling and dropping carton") — this surfaced and fixed a real bug: a naive 2-3 frame velocity window crossed threshold on pure bbox jitter from the real (noisy, prototype) detector, producing 21 false-positive events from one 6-second clip. Fixed in `pushed_or_thrown.py`/`rough_handling.py` (wider averaging window + consecutive-frame requirement + a contact-cooldown so a real jolt doesn't get double-counted after release) — now 3-4 clean events per clip, synthetic suite still green. `rolling` still didn't fire on either "rolling" clip — the one `carton` detection in both is a suspiciously huge box (~660×486px), likely a Member 1 detection-quality issue worth a look, not something tunable on this side. **Real trained model (`best.pt`) only detects person/box/forklift** — `pallet_incorrect_position`, `strap_misuse`, and `wrong_orientation` cannot fire against it until Member 1 retrains with a richer class set. **Ran all remaining 5 Drive clips too (all 7 now covered) — surfaced the real root cause for why `dragged` and other longer-threshold behaviours never fire on real footage: track identity fragmentation, not thresholds.** ByteTrack reassigns a brand-new track_id almost every time contact resumes on a real clip (confirmed: one clip produced 56 distinct carton track_ids in 451 frames) — every behaviour here is keyed by track_id, so duration/distance can't accumulate across an identity change. This is a Member 1 tracking-quality issue (or a future track re-identification feature — a real, riskier build, not a quick fix), not something tunable from this side. Full breakdown per clip in `behaviour-risk/README.md`. (Member 2)
- [ ] `/backend-assistant` event store + assistant answering doc's example queries (Member 3)
- [ ] `/dashboard` reading real events end-to-end (Member 4)

## When in doubt
If a task would require changing the event schema, the behaviour enum, or the
per-frame output format, stop and flag it to the whole team before proceeding —
three other components are built directly against these shapes.
