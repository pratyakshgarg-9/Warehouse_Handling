# Dashboard — Member 4 (Dashboard, Visualization & Demo)

Streamlit UI for Warehouse-AI: video playback with AI overlays, incident
replay, risk classification, event timeline, behaviour trends, risk heatmap,
and the assistant chat panel.

## Run it

```bash
pip install -r dashboard-requirements.txt          # streamlit, plotly, opencv, pandas

python test_data/generate_test_data.py             # one-time: build the SAMPLE dataset
streamlit run app.py                               # from inside dashboard/
```

The app auto-detects its data source:

| Situation | What you see |
| --- | --- |
| `backend-assistant/events.db` exists (Member 3's real store) | Live data, green **LIVE EVENT STORE** badge |
| Only the sample store exists | Sample data, loud red **SAMPLE DATA** badge on every page |
| Neither | An honest empty state with instructions — never fake data |

Force a mode with `DASHBOARD_TEST_MODE=1` (sample) or `=0` (real).

## Layout

```
app.py                     Overview: KPIs, risk mix, shift summary, recent events + evidence
pages/1_Video_Review.py    Annotated player (overlay toggle), event picker, incident replay
pages/2_Timeline_Trends.py Timeline, behaviour trends by shift, bay×hour heatmap, recurrence
pages/3_Assistant.py       Chat panel calling Member 3's assistant (honest state until connected)
config.py                  Data-source resolution + env overrides (no hardcoded paths)
data_access.py             READ-ONLY access to the event store + Member 1's detections
overlays.py                Bounding boxes, banners, risk colors (shared visual language)
assistant_client.py        Adapter to Member 3's assistant (HTTP or module)
ui.py                      Shared UI: sidebar, badges, empty states, KPI helpers
test_data/                 SAMPLE dataset generator (see below) — output is gitignored
```

## Sample dataset (`test_data/`)

`generate_test_data.py` deterministically produces (seed = 42):

- `demo_session.mp4` — 96 s synthetic bay footage, scripted to cover **all 10
  behaviour types** from the shared enum (one drop, one drag, one shove, a
  bad stack, an out-of-zone placement, a hand-drag past an unused trolley, a
  wobbling stack, a slam, an overhang, and a rapid unsafe sequence)
- `demo_session_detections.json` — per-frame detections in **Member 1's
  published format** (track ids, bboxes, confidences, person keypoints)
- `events.db` — SQLite `events` table in **the published event schema**:
  10 in-session events + 15 historical events across Sep 4–5, 3 bays,
  3 shifts — so trends, heatmap and recurrence have data
- `evidence/evt_XXXXX.jpg` — evidence frame per event
- `manifest.json` — video start time / fps / duration

The video's scripted moments are chosen so the demo tells a story: a normal
start (system correctly flags nothing), then escalating behaviours, ending
with the rapid unsafe sequence that the Overview and Trends pages summarize.

## Integration contract (how the real pipeline drops in)

Everything the dashboard reads is a published contract from `/shared`:

1. **Events** — SQLite `events` table, columns per the event schema in
   `root-CLAUDE.md`. Opened strictly read-only. When Member 3's store
   appears at `backend-assistant/events.db`, the dashboard uses it
   automatically — no code changes.
2. **Evidence frames** — resolved by convention `<evidence_dir>/<event_id>.jpg`
   first, then the event row's stored path.
3. **Per-frame detections** — Member 1's format; point
   `DASHBOARD_DETECTIONS_PATH` (and `DASHBOARD_VIDEO_PATH`,
   `DASHBOARD_VIDEO_START_UTC`) at the real session. Event timestamps map to
   video seek positions via `VIDEO_START_UTC` — worth standardizing in
   `/shared` once Member 1's output lands.
4. **Assistant** — set `ASSISTANT_URL` (HTTP: `POST {"question": ...}` →
   `{"answer": ...}`) or drop `assistant.py` with `ask(question) -> str` into
   `backend-assistant/`. Until then the chat page shows an honest
   not-connected state with the challenge doc's example queries.

## Demo script (for the 3–5 scenario submission requirement)

1. **Overview** — the shift at a glance: risk mix, riskiest bay, recent
   events with evidence frames and plain-language explanations.
2. **Video Review → "evt_00016 dropped"** — jump & replay: watch the carton
   fall, overlay banner + risk-colored highlight on the involved objects.
3. **Video Review → "evt_00025 unsafe_loading_sequence"** — the rapid
   sequence, then flip the overlay toggle off to show the raw footage the AI
   was working from.
4. **Timeline & Trends** — the same session in aggregate: heatmap shows
   where/when risk concentrates, recurrence table names the retraining
   candidates.
5. **Assistant** — (once Member 3 connects) ask "Which loading bay had the
   highest number of risky events?" and get an answer grounded in the store.

## Notes / decisions

- Sample data is always badged — the challenge doc's responsible-AI stance
  (never overclaim) applies to the demo itself.
- The dashboard computes nothing about risk or behaviour; it renders what
  Members 1–3 produced. Aggregations (counts, averages, recurrences) are
  computed live from the store with pandas.
- No hardcoded paths: everything resolves via `shared/config.py` + env
  overrides in `dashboard/config.py`.
