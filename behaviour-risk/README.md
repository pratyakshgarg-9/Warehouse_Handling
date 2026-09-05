# behaviour-risk (Member 2)

Turns Member 1's per-frame detections into named behaviours and
risk-classified events. See `CLAUDE.md` in this folder for role/timeline
context, and the repo root `CLAUDE.md` for the shared schema contract.

## Status (2026-09-05, Sep 5 milestone)

Runs standalone end-to-end against synthetic sample data (Member 1 hasn't
published a real stream yet — `/cv-pipeline` is still just a
requirements.txt). 4 of 10 behaviours implemented and tested, matching the
roadmap's Sep 5 target exactly:

| Behaviour | Status |
| --- | --- |
| `dropped` | done |
| `dragged` | done |
| `rough_handling` (covers "stepping on cartons" — see note below) | done |
| `incorrect_stacking` | done |
| `unstable_stacking`, `outside_designated_area`, `no_required_equipment`, `pallet_incorrect_position`, `pushed_or_thrown`, `unsafe_loading_sequence` | not started — Sep 7 target per the roadmap |

Risk scoring (v1 formula) and explanation strings are implemented for all
four working behaviours. Thresholds throughout are first-pass guesses, not
tuned against real footage — expect to retune once Member 1's live stream
and real sample videos are available (Sep 6-9 per the roadmap).

## Layout

```
behaviour_risk_engine/
  models.py           DetectedObject / RawDetection / Event — mirrors the shared schema
  constants.py        class-name sets (person/carton/pallet/trolley)
  geometry.py         bbox helpers (overlap, resting-on, overhang)
  track_store.py       rolling per-track history (velocity, displacement, duration)
  behaviours/          one BehaviourDetector per behaviour_type
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
- **Person keypoints**: the "stepping on product" rule approximates a
  person's feet as the bottom 15% of their bbox (`geometry.bottom_strip`)
  rather than real pose keypoints, since the per-frame schema doesn't
  document keypoint index/ordering (e.g. MediaPipe's landmark order) yet.
  Worth revisiting with Member 1 once that's documented.
- **"Stepping on cartons" enum gap**: the challenge doc lists this as its
  own bad practice, but the shared `behaviour_type` enum in the root
  CLAUDE.md has no dedicated slot for it — it's folded into
  `rough_handling` here. If the team wants a dedicated category, that's an
  enum change and needs to go through `/shared` first.
