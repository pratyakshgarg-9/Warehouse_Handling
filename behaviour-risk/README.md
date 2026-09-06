# behaviour-risk (Member 2)

Turns Member 1's per-frame detections into named behaviours and
risk-classified events. See `CLAUDE.md` in this folder for role/timeline
context, and the repo root `CLAUDE.md` for the shared schema contract.

## Status (2026-09-06)

Runs standalone end-to-end against synthetic sample data (Member 1 hasn't
published a real stream yet — `/cv-pipeline` is still just a
requirements.txt). 14 behaviours implemented and tested — beyond the
roadmap's Sep 7 "all 10 behaviours" target, because the real input videos
(see below) turned out to need 4 more than the doc's generic behaviour
list implied:

| Behaviour | Status |
| --- | --- |
| `dropped` | done |
| `dragged` | done |
| `rough_handling` (sudden jolt while being actively handled) | done |
| `stepping_on_product` (a person standing/stepping on a carton) | done |
| `incorrect_stacking` (unsupported overhang) | done |
| `unstable_stacking` (tall/narrow stack, toppling risk) | done |
| `outside_designated_area` | done |
| `no_required_equipment` (long manual carry, no trolley) | done |
| `pallet_incorrect_position` (product overhangs its pallet) | done |
| `pushed_or_thrown` (high speed, nobody in contact) | done |
| `unsafe_loading_sequence` (several products moving at once) | done |
| `rolling` (rolled instead of carried — bbox aspect-ratio wobble) | done |
| `wrong_orientation` (upright product kept lying on its side) | done |
| `strap_misuse` (lifted/pulled by its packaging strap) | done |

Risk scoring (v1 formula) and explanation strings are implemented for all
fourteen. Thresholds throughout are first-pass guesses, not tuned against
real footage — expect to retune once Member 1's live stream and real
sample videos are available (Sep 6-9 per the roadmap). Remaining work is
tuning against false positives/negatives and wiring to Member 1's real
stream once it's published, not new behaviours.

**Checked the actual input videos (2026-09-06)**: the challenge doc (`AI
Video Intelligence for Warehouse Handling.docx`) links a Google Drive
folder of the real demo footage — 7 clips: "Dock level, dragging
cupboard", "KD packets dragged, heavy box kept on other packets", "Rolling
and dragging on wet floor", "Rolling and dropping carton", "Stepping on
cartons, vertical product kept horizontally, heavy product kept on top",
"Throwing Mattresses", "Throwing seating cartons, using strap to hold".
Cross-checking those filenames against the first 11 behaviours surfaced
`rolling`, `wrong_orientation`, and `strap_misuse` as real gaps — now
fixed. It also showed the product mix is mattresses/cupboards/packets,
not just cartons, hence the `PRODUCT_CLASSES` broadening in
`constants.py` (see that file's note) — **this affects Member 1's
labeling plan**, which only covered person/carton/pallet/trolley.

## Layout

```
behaviour_risk_engine/
  models.py           DetectedObject / RawDetection / Event — mirrors the shared schema
  constants.py        class-name sets (person/carton/mattress/cupboard/pallet/trolley/strap)
  geometry.py         bbox helpers (overlap, resting-on, overhang, bottom_strip)
  track_store.py       rolling per-track history (velocity, displacement, duration)
  pair_debounce.py     shared "hold for N seconds, fire once" helper used by several detectors
  behaviours/          one BehaviourDetector per behaviour_type (14 files)
  risk_scoring.py      the spec's risk_score formula + Low/Medium/High/Critical buckets
  explanations.py      bad-practice -> good-practice text per behaviour_type
  event_sink.py        where finished events go (see "Integration" below)
  engine.py            BehaviourEngine — wires everything above together
  cv_pipeline_adapter.py  translates Member 1's REAL output format into what engine.py expects

sample_data/generate_sample_frames.py   synthetic per-frame stream standing in for Member 1's real one
demo.py                                  run the engine over synthetic sample data, print resulting events
run_on_cv_output.py                      run the engine over Member 1's REAL published output, print resulting events
tests/test_behaviours.py                 pytest: each behaviour fires, events match schema, no "confirmed damage" language
```

## Running it

```bash
pip install -r behaviour-risk-requirements.txt
python demo.py                    # prints every event produced from synthetic sample frames
python run_on_cv_output.py        # prints every event produced from Member 1's real published output
pytest tests/                     # run from within behaviour-risk/
```

## Wired to Member 1's real output (2026-09-07)

`/cv-pipeline` published a real pipeline + output (`models/best.pt`,
`pipeline/cv_pipeline.py`, `outputs/*.json`) on 2026-09-06/07. Their actual
per-frame JSON diverges from the schema documented in the root CLAUDE.md
(which both this module and `dashboard/data_access.py` were built
against) — see `cv_pipeline_adapter.py`'s docstring for the full mapping:
`class_name` not `class`, `timestamp_ms` (int, frame-relative) not
`timestamp` (ISO string), `pose.landmarks` not `keypoints`, `track_id: -1`
for untracked detections (dropped, not merged into one fake track), and a
`MIN_CONFIDENCE` floor for the prototype model's noisier detections.

**First pass — `run_on_cv_output.py` against both real files already in
`cv-pipeline/outputs/` — 0 events from either, correctly.** Checked why:
both files are generic pipeline-validation walkthroughs (person + forklift
moving around a warehouse), not runs of the actual challenge-doc demo
videos. The only `box`-class track across either file lasts 6 frames with
~37px of movement — nowhere near any behaviour's threshold, correctly.

Also surfaced: the real trained model (`best.pt`) only detects `person`,
`box`, and `forklift` (confirmed from the output JSON) — nowhere near the
doc's full product/equipment vocabulary. Concretely, `pallet_incorrect_position`,
`strap_misuse`, and `wrong_orientation` **cannot produce events against
this model** until Member 1 trains on pallet/strap/cupboard/mattress too
— not a bug in those detectors, a model-vocabulary gap (already called out
in `cv-pipeline/README.md`'s own limitations section).

**Second pass (2026-09-07) — ran Member 1's actual pipeline on 2 real
demo clips**: downloaded "Rolling and dragging on wet floor.mp4" (6.7 MB)
and "Rolling and dropping carton.mp4" (10.1 MB) from the challenge doc's
Drive folder and ran `cv_pipeline.run_cv()` on both (outputs landed in
`cv-pipeline/outputs/` per that function's own design — the generated
annotated MP4s were deleted after inspection, just the `*_cv.json` per-
frame data was kept). This produced real events for the first time —
`rough_handling` and `stepping_on_product` fired — but the first run also
exposed a real robustness bug:

- **Bbox jitter false-positives**: a real detector's box edges wobble a
  few px frame-to-frame even when nothing is moving. At 30fps that's
  enough to cross a naive 2-3 frame velocity threshold constantly — one
  clip produced 41 spurious speed-spikes on a single mostly-stationary
  track, cascading into **21 events from 6 seconds of video**, 11 of them
  the same `pushed_or_thrown` false-positive repeating. Fixed in
  `pushed_or_thrown.py` and `rough_handling.py`'s jerk sub-rule: widened
  the speed-averaging window (2-3 → 6 frames) and require the elevated
  speed to hold for 2 consecutive frames, not one instant. That alone
  collapsed the noise into 3 clean, physically-plausible clusters.
- **Window-widening's own side effect**: a wider window means a real
  jolt's velocity reading lingers for a few frames after the fact — long
  enough to outlast contact ending, which made `pushed_or_thrown` also
  fire for the exact same jolt `rough_handling` had already correctly
  captured while contact was active. Fixed with a small cooldown:
  `pushed_or_thrown` won't evaluate a track's speed until contact has
  been over for a full window's worth of frames.
- **After both fixes: 3 events for the wet-floor clip, 4 for the
  dropping-carton clip** — `rough_handling` and `stepping_on_product`
  only, no duplicates. Full synthetic test suite (14 scripted scenarios)
  still passes unchanged.
- **Still not investigated**: neither clip produced a `rolling` event,
  despite that being literally the filmed behaviour. The one `carton`-
  class track in both clips is suspiciously huge (~660×486px, over half
  the 1280×720 frame) — likely a low-quality prototype-model box rather
  than a real, tightly-fit product detection, which would also explain
  why `stepping_on_product` fires just from a person being anywhere near
  that region. This looks like a detection-quality issue for Member 1
  (README's own "Improving cardboard box detection" limitation), not
  something tunable from the behaviour-risk side — worth Member 1 looking
  at the annotated video for these two clips to confirm what's actually
  being boxed.
- **The real remaining next step still needs Member 1**: run the pipeline
  on the rest of the Drive clips (dock/dragging, throwing, straps,
  stacking) for broader validation, and ideally retrain with a broader
  labeled dataset so the 3 dead behaviours above have a chance to fire.

**Third pass (2026-09-07) — ran the remaining 5 Drive clips** ("Dock
level, dragging cupboard", "KD packets dragged, heavy box kept on other
packets", "Stepping on cartons, vertical product kept horizontally, heavy
product kept on top", "Throwing Mattresses", "Throwing seating cartons,
using strap to hold" — all 7 clips now covered). Results, after the fixes
above:

| Clip | Events | Notable |
| --- | --- | --- |
| Dock level, dragging cupboard (31s) | 8 | `dropped`, `stepping_on_product`, 3x `pushed_or_thrown`, 2x `no_required_equipment` |
| KD packets dragged, heavy box... (34s) | 4 | 4x `pushed_or_thrown` on 4 different tracks |
| Stepping on cartons... (49s) | 1 | 1x `pushed_or_thrown` |
| Throwing Mattresses (42s) | 1 | 1x `pushed_or_thrown`, at 00:00:39 — plausible timing for a single throw near the end |
| Throwing seating cartons, strap (15s) | 8 | 2x `stepping_on_product`, 6x `pushed_or_thrown` across 56 (!) distinct carton track_ids |

`throwing_mattresses` is the cleanest validation so far — one event,
sensibly timed. But `dragged` still never fired on either clip literally
named for dragging, which led to the real finding of this pass:

- **Root cause isn't thresholds, it's track identity fragmentation.**
  Instrumented `dragged.py` directly against `kd_packets_dragged_heavy_box`:
  every time person-carton contact was detected, it was under a **brand
  new track_id** (117 → 106 → 185 → 199 → 219 → 240 → 272...) — ByteTrack
  loses the object and reassigns a fresh id almost every time, because
  detections are too sparse to bridge the gaps (confirmed separately: one
  carton track had a 29-frame gap mid-track; `throwing_seating_strap`
  produced **56 distinct carton track_ids in just 451 frames**). Every
  behaviour here is keyed by track_id, so a duration/distance requirement
  can never accumulate across an identity change — `dragged` needs 0.4s +
  60px on one id and never got close (elapsed capped at ~0.33s, distance
  under 20px, in every fragment). This is a tracking-quality issue on
  Member 1's side (ByteTrack losing tracks, or the detector's confidence
  being too unstable for it to hold one), not a tunable parameter here.
- Added a grace period to `dragged.py` anyway (ages out an episode based
  on frames since last *confirmed* contact, tolerating momentary gaps on
  an otherwise-continuous track) — correct and worth keeping, but it
  didn't fix this specific clip because the gap here isn't momentary, it's
  a full identity change. A real fix needs either better tracking
  continuity upstream, or a track re-identification layer (matching a new
  id to a just-lost one by proximity/class/timing) — a real feature, not
  a quick patch, and one with its own false-merge risks; flagging it as a
  team decision rather than building it under time pressure.
- This also explains the earlier pattern: **shorter-threshold behaviours
  survive fragmentation, longer ones don't.** `stepping_on_product` (0.3s)
  and the jerk/throw rules (2 consecutive frames) fired across real clips;
  `dragged`, `incorrect_stacking`/`unstable_stacking`, `pallet_incorrect_position`,
  and `unsafe_loading_sequence` (all 0.4-1.0s+ sustained) never did, across
  any of the 7 clips. Worth keeping in mind when tuning further: thresholds
  aren't the only lever, track continuity upstream matters just as much.

**Flagged to Member 4**: `dashboard/data_access.py`'s `load_detections()`
is written against the same documented-but-not-real schema (its own
docstring says so) — it'll hit the identical mismatch once it loads
Member 1's actual output. Worth reusing this adapter's mapping rather than
writing a second, possibly-inconsistent translation.

## Integration points (things that will need to change later)

- **Timestamp precision / reference**: `cv_pipeline_adapter.py` converts
  Member 1's frame-relative `timestamp_ms` into an ISO timestamp using an
  arbitrary reference time by default — it's NOT real wall-clock time
  unless a `video_start_utc` is passed in. `dashboard/config.py` already
  has the identical problem and solves it with a `DASHBOARD_VIDEO_START_UTC`
  env var — worth the whole team agreeing on one video-start-time
  convention rather than each module picking its own default.
- **Member 3's insert function**: not published yet. `event_sink.py`
  currently falls back to a local JSONL log
  (`behaviour-risk/output/events_log.jsonl`, gitignored) and has a guessed
  import (`backend_assistant.db.insert_event`) that will silently no-op
  until that path is real. Update that one import once Member 3 publishes
  the actual function — nothing in `engine.py` or the detectors changes.
- **Person keypoints**: the `stepping_on_product` rule approximates a
  person's feet as the bottom 15% of their bbox (`geometry.bottom_strip`)
  rather than real pose keypoints, since the per-frame schema doesn't
  document keypoint index/ordering (e.g. MediaPipe's landmark order) yet.
  Worth revisiting with Member 1 once that's documented.
- **Designated-area / pallet-zone coordinates**: `outside_designated_area.py`'s
  `DESIGNATED_AREA_BBOX` is a placeholder pixel rectangle with no camera
  calibration behind it yet — needs real values once Member 1's camera
  setup/framing is known.
- **Enum changes (2026-09-06)**: `stepping_on_product`, then `rolling` /
  `wrong_orientation` / `strap_misuse`, were added to the shared
  `behaviour_type` enum (root CLAUDE.md and `shared/config.py`) — see that
  file's changelog notes. Flagging this since Member 3/4 build against
  that enum; nothing was built against the old list yet, so this was a
  safe time to fix it.
- **Product class taxonomy**: `constants.PRODUCT_CLASSES` was broadened
  from just `{"carton"}` to `{"carton", "mattress", "cupboard", "packet"}`
  after checking the real input videos, and `STRAP_CLASSES = {"strap"}`
  was added for `strap_misuse.py`. These are placeholder guesses at
  Member 1's eventual label names — their roadmap only planned
  person/carton/pallet/trolley, which doesn't cover what's actually
  filmed. `strap_misuse` in particular will never fire on real data until
  Member 1's detector recognizes a strap class. Worth confirming actual
  class names with Member 1 once their labeling is done.
