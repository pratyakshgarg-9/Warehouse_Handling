"""
dashboard/app.py — Member 4: Overview page + multipage shell.

Run from the dashboard folder:
    streamlit run app.py

Pages (sidebar):
  Overview            <- this file: KPIs, risk mix, recent events w/ evidence
  1_Video_Review      <- playback, overlays, incident replay
  2_Timeline_Trends   <- timeline, behaviour trends, bay×hour heatmap
  3_Assistant         <- Member 3's assistant, chat panel
"""

from __future__ import annotations

import sys
from pathlib import Path

_DASH = Path(__file__).resolve().parent
for _p in (str(_DASH), str(_DASH.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd
import plotly.express as px
import streamlit as st

import config
import data_access
import ui

st.set_page_config(
    page_title="Warehouse-AI Dashboard",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

df = ui.require_events()
ui.sidebar()

st.title("Operations Overview")
st.caption(
    "Everything on this page is computed live from the event store — "
    "observed behaviours and potential risks, never claimed damage without evidence."
)

# ------------------------------------------------------------------ KPI row --
latest_ts = df["timestamp"].max()
day_df = df[df["timestamp"].dt.date == latest_ts.date()]
high_mask = df["risk_level"].isin(["High", "Critical"])
high_today = day_df["risk_level"].isin(["High", "Critical"])

top_behaviour = (
    df["behaviour_type"].value_counts().idxmax().replace("_", " ")
    if not df.empty else "—"
)
riskiest_bay = (
    df[high_mask].groupby("bay", observed=True).size().idxmax()
    if df[high_mask].shape[0] else df["bay"].mode().iat[0] if not df.empty else "—"
)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total events", len(df))
c2.metric("High + Critical", int(high_mask.sum()))
c3.metric("Events today", len(day_df), f"{int(high_today.sum())} high/critical")
c4.metric("Top behaviour", top_behaviour)
c5.metric("Riskiest bay", riskiest_bay)
st.caption(f"Data through {latest_ts:%Y-%m-%d %H:%M:%S} UTC")

# ------------------------------------------------------------ risk / behaviour --
t1, t2 = st.columns(2)

with t1:
    st.subheader("Risk classification")
    counts = df["risk_level"].value_counts().reindex(config.RISK_ORDER).fillna(0)
    fig = px.pie(
        names=[str(c) for c in counts.index], values=counts.values, hole=0.55,
        color=[str(c) for c in counts.index],
        color_discrete_map={
            "Low": "#22c55e", "Medium": "#eab308", "High": "#f97316", "Critical": "#ef4444"
        },
        category_orders={"color": config.RISK_ORDER},
    )
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280)
    st.plotly_chart(fig, use_container_width=True)

with t2:
    st.subheader("Events by behaviour type")
    bcounts = df["behaviour_type"].value_counts()
    fig = px.bar(
        x=bcounts.values, y=bcounts.index, orientation="h",
        labels={"x": "events", "y": ""},
        color=bcounts.values, color_continuous_scale="OrRd",
    )
    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=280, showlegend=False)
    fig.update_yaxes(ticktext=[b.replace("_", " ") for b in bcounts.index], tickvals=bcounts.index)
    st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------- shift summary --
st.subheader("Shift summary")
df["_shift"] = df["timestamp"].apply(data_access.shift_of)
shift_summary = (
    df.assign(day=df["timestamp"].dt.strftime("%b %d"))
    .pivot_table(index="day", columns="_shift", values="event_id", aggfunc="count", fill_value=0, observed=True)
)
high_summary = (
    df[high_mask].assign(day=df[high_mask]["timestamp"].dt.strftime("%b %d"))
    .pivot_table(index="day", columns="_shift", values="event_id", aggfunc="count", fill_value=0, observed=True)
)
s1, s2 = st.columns(2)
with s1:
    st.markdown("**All events**")
    st.dataframe(shift_summary, use_container_width=True)
with s2:
    st.markdown("**High + Critical only**")
    st.dataframe(high_summary, use_container_width=True)

# ------------------------------------------------------ recent events + evidence --
st.subheader("Recent events")
st.caption("Each row is one detected behaviour — the evidence frame shows what the camera saw.")

recent = df.sort_values("timestamp", ascending=False).head(8)
for _, row in recent.iterrows():
    with st.container(border=True):
        left, right = st.columns([1, 3])
        with left:
            ev_path = data_access.resolve_evidence_path(
                row, st.session_state[ui.SOURCE_KEY]["evidence_dir"]
            )
            if ev_path is not None:
                st.image(str(ev_path), use_container_width=True)
            else:
                st.markdown(
                    "<div style='border:1px dashed #888;border-radius:4px;"
                    "padding:24% 8%;text-align:center;color:#888;font-size:0.8em'>"
                    "no evidence frame</div>",
                    unsafe_allow_html=True,
                )
        with right:
            st.markdown(
                f"**`{row['event_id']}`** &nbsp; {ui.risk_pill(row['risk_level'])} "
                f"&nbsp; `risk_score {row['risk_score']:.2f}` &nbsp; "
                f"**{row['behaviour_type'].replace('_', ' ').title()}** &nbsp; "
                f"`{row['bay']}` &nbsp; {row['timestamp']:%Y-%m-%d %H:%M:%S} UTC"
            )
            st.write(row["explanation"])
