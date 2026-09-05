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

sample_data/generate_sample_frames.py   synthetic per-frame stream standing in for Member 1's real one
demo.py                                  run the engine over sample data, print resulting events
tests/test_behaviours.py                 pytest: each behaviour fires, events match schema, no "confirmed damage" language
```

## Running it

```bash
pip install -r behaviour-risk-requirements.txt
python demo.py          # prints every event produced from synthetic sample frames
pytest tests/           # run from within behaviour-risk/
```

## Integration points (things that will need to change later)

- **Member 1's real stream**: `sample_data/generate_sample_frames.py` is a
  stand-in. Once `/cv-pipeline` publishes a real per-frame stream, whatever
  drives it just needs to call `BehaviourEngine.process_frame(frame_dict)`
  per frame — nothing inside `behaviour_risk_engine/` needs to change.
- **Timestamp precision**: the sample generator emits millisecond-precision
  timestamps (`...T10:00:00.033Z`) because velocity/duration math needs
  sub-second resolution at 30fps. The root CLAUDE.md's schema example only
  shows whole seconds — confirm Member 1's real stream has sub-second
  precision too (flagged, not assumed silently).
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
