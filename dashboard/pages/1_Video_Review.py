"""
dashboard/pages/1_Video_Review.py — Member 4.

Session video review:
  - Annotated player: original footage with AI-detected object overlays,
    behaviour labels, risk-colored event highlights, play/pause/speed.
  - Overlay toggle: compare the AI's view against the raw footage instantly.
  - Incident replay: jump to any flagged event and replay the moment.
  - Event markers strip under the player.

Overlays come from Member 1's per-frame detections; event moments come from
the event store. If either is missing, the page says so honestly.

Frames are rendered through st.image rather than an <video> element so the
overlays stay perfectly in sync with the playhead (and no codec dependency).
"""

from __future__ import annotations

import sys
from pathlib import Path

_PAGES = Path(__file__).resolve().parent
_DASH = _PAGES.parent
for _p in (str(_DASH), str(_DASH.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import config
import data_access
import overlays
import ui

st.set_page_config(page_title="Video Review — Warehouse-AI", page_icon="🎥", layout="wide")

df = ui.require_events()
source = ui.sidebar()

media = config.resolve_session_media()
if not media["video_exists"] or not media["detections_exist"]:
    st.title("🎥 Video Review")
    st.info(
        "**No session video / detections available yet.**\n\n"
        "This page plays the session footage with AI-detected overlays drawn "
        "from Member 1's per-frame detections and flags event moments from the "
        "event store.\n\n"
        "Set `DASHBOARD_VIDEO_PATH` and `DASHBOARD_DETECTIONS_PATH` to a real "
        "clip and its matching JSON before launching Streamlit, e.g.:\n"
        "```\n"
        '$env:DASHBOARD_VIDEO_PATH = "C:\\path\\to\\dock_level_dragging_cupboard.mp4"\n'
        '$env:DASHBOARD_DETECTIONS_PATH = "cv-pipeline/outputs/dock_level_dragging_cupboard_cv.json"\n'
        '$env:DASHBOARD_VIDEO_START_UTC = "2026-09-08T08:15:00Z"\n'
        "streamlit run dashboard/app.py\n"
        "```\n"
        "See the team's \"Clone, Setup & Run Guide\" document for the full list "
        "of clips and their matching start times.",
        icon="🎥",
    )
    st.stop()

video_start = pd.Timestamp(media["video_start_utc"])
if video_start.tzinfo is None:
    video_start = video_start.tz_localize("UTC")
meta = data_access.video_meta(media["video_path"])
fps = media["fps"] or meta["fps"]
duration = media["duration_s"] or (meta["frames"] / fps if meta["frames"] else 0)


@st.cache_data(show_spinner=False)
def _load_detections_cached(path: str):
    return data_access.load_detections(path)


detections = _load_detections_cached(media["detections_path"])

# Events that fall inside this video session — only these can be replayed.
session_events = data_access.events_in_window(
    df, video_start, video_start + pd.Timedelta(seconds=duration)
).reset_index(drop=True)


def event_time(row) -> float:
    """Seconds into the video when this event was flagged."""
    return (row["timestamp"] - video_start).total_seconds()


def active_event(t: float):
    """Event whose flag moment is within ±1.5 s of playhead t (nearest wins)."""
    best, best_d = None, 1.5
    for _, row in session_events.iterrows():
        d = abs(event_time(row) - t)
        if d <= best_d:
            best, best_d = row, d
    return best


def render_frame(t: float, selected_event=None, draw_overlays=True):
    """Decode the frame at time t; optionally draw AI overlays on it."""
    frame_id = int(round(t * fps))
    frame = data_access.read_video_frame(media["video_path"], frame_id)
    if frame is None or not draw_overlays:
        return frame

    det = data_access.detections_at(detections, frame_id)
    highlight = {}

    banner_event = selected_event if selected_event is not None else active_event(t)
    if banner_event is not None:
        for tid in banner_event["object_ids"]:
            highlight[tid] = (
                overlays.BEHAVIOUR_LABELS.get(banner_event["behaviour_type"], "EVENT"),
                overlays.RISK_COLORS.get(banner_event["risk_level"], (255, 255, 255)),
            )

    overlays.draw_objects(frame, det["objects"], highlight_tracks=highlight)
    if banner_event is not None:
        ts_text = f"{banner_event['event_id']}  {banner_event['timestamp']:%H:%M:%S} UTC"
        overlays.draw_event_banner(frame, banner_event, ts_text)
    return frame


# ------------------------------------------------------------------ layout --
st.title("🎥 Video Review")
st.caption(
    f"Session: `{media.get('bay', '—')}` · starts {video_start:%Y-%m-%d %H:%M:%S} UTC · "
    f"{duration:.0f} s @ {fps:.0f} fps · {len(session_events)} events fall inside this session"
)

pick_col, player_col = st.columns([1, 3], gap="large")

with pick_col:
    st.markdown("**Flagged events in this session**")
    if session_events.empty:
        st.success("No events flagged inside this session — nothing to replay.", icon="✅")
    options = [
        f"{r['event_id']} · {r['risk_level']:7s} · {r['behaviour_type'].replace('_', ' ')}"
        for _, r in session_events.iterrows()
    ]
    chosen = st.radio("Select an event", options, label_visibility="collapsed") if options else None
    selected_event = session_events.iloc[options.index(chosen)] if chosen else None

    jump = st.button("⏭ Jump & replay this event", disabled=selected_event is None, type="primary")
    if jump and selected_event is not None:
        t0 = max(0.0, event_time(selected_event) - 1.5)
        st.session_state["t_now"] = t0
        st.session_state["scrub"] = t0
        st.session_state["playing"] = True
        st.session_state["play_window"] = (t0, min(duration, t0 + 4.5))

    if selected_event is not None:
        with st.container(border=True):
            st.markdown(ui.risk_pill(selected_event["risk_level"]) + " · "
                        + selected_event["behaviour_type"].replace("_", " ").title())
            st.caption(f"`{selected_event['bay']}` · objects {list(selected_event['object_ids'])} "
                       f"· risk_score {selected_event['risk_score']:.2f}")
            st.write(selected_event["explanation"])

with player_col:
    if "t_now" not in st.session_state:
        st.session_state["t_now"] = 0.0

    show_overlays = st.toggle(
        "Show AI overlays", value=True,
        help="Off = the raw footage exactly as the camera recorded it. "
             "On = detected objects, behaviour labels and risk highlights.",
    )

    @st.fragment(run_every=0.1)
    def player():
        t = st.session_state.get("t_now", 0.0)
        playing = st.session_state.get("playing", False)

        ctrl, spd, tbox = st.columns([1, 1, 2])
        with ctrl:
            if playing:
                if st.button("⏸ Pause", use_container_width=True):
                    st.session_state["playing"] = False
                    st.session_state["play_window"] = None
            else:
                if st.button("▶ Play", use_container_width=True):
                    st.session_state["playing"] = True
        with spd:
            speed = st.select_slider("speed", options=[0.5, 1, 2], value=1.0)
        with tbox:
            st.markdown(
                f"<div style='padding-top:8px;font-family:monospace'>"
                f"t = {t:6.1f} s / {duration:.0f} s &nbsp; {'▶ playing' if playing else '⏸ paused'}"
                f"</div>",
                unsafe_allow_html=True,
            )

        frame = render_frame(t, selected_event, draw_overlays=show_overlays)
        if frame is None:
            st.warning(f"Could not decode a frame at t={t:.1f}s.")
            return
        st.image(frame[:, :, ::-1], use_container_width=True)

        if not playing:
            # scrubber only while paused — dragging a slider that resets
            # every playback tick is miserable UX
            st.slider(
                "Timeline (s)", 0.0, float(duration), step=1.0 / fps,
                key="scrub", label_visibility="collapsed",
            )
            if abs(st.session_state["scrub"] - t) > 1e-9:
                st.session_state["t_now"] = float(st.session_state["scrub"])
        else:
            st.session_state["t_now"] = min(duration, t + 0.1 * speed)
            window = st.session_state.get("play_window")
            if st.session_state["t_now"] >= duration or (
                window and st.session_state["t_now"] >= window[1]
            ):
                st.session_state["playing"] = False
                st.session_state["play_window"] = None
                st.session_state["scrub"] = st.session_state["t_now"]

    player()

    # --- event markers strip under the player -----------------------------
    if not session_events.empty:
        fig = go.Figure()
        risk_colors = {"Low": "#22c55e", "Medium": "#eab308", "High": "#f97316", "Critical": "#ef4444"}
        for level in config.RISK_ORDER:
            sub = session_events[session_events["risk_level"] == level]
            if sub.empty:
                continue
            fig.add_trace(go.Scatter(
                x=[event_time(r) for _, r in sub.iterrows()],
                y=[level] * len(sub),
                mode="markers",
                marker=dict(size=14, color=risk_colors[level], line=dict(width=1, color="#333")),
                name=level,
                text=[f"{r['event_id']} · {r['behaviour_type']}" for _, r in sub.iterrows()],
                hovertemplate="%{text}<br>t = %{x:.1f}s<extra></extra>",
            ))
        fig.update_layout(
            height=160, margin=dict(t=20, b=10, l=10, r=10),
            xaxis=dict(title="seconds", range=[0, duration]),
            yaxis=dict(categoryorder="array", categoryarray=config.RISK_ORDER),
            legend=dict(orientation="h", y=1.15),
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
