"""
dashboard/pages/2_Timeline_Trends.py — Member 4.

Prevention & learning views over the event store:
  - Event timeline (when things happened, colored by risk)
  - Behaviour trends over time (per shift)
  - Risk heatmap by bay × hour (high-risk locations/processes)
  - Recurring-behaviour tracking (repeat behaviours -> retraining candidates)
"""

from __future__ import annotations

import sys
from pathlib import Path

_PAGES = Path(__file__).resolve().parent
_DASH = _PAGES.parent
for _p in (str(_DASH), str(_DASH.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import plotly.express as px
import streamlit as st

import config
import data_access
import ui

st.set_page_config(page_title="Timeline & Trends — Warehouse-AI", page_icon="📊", layout="wide")

df = ui.require_events()
ui.sidebar()

st.title("📊 Timeline, Trends & Prevention")
st.caption("Aggregated views for supervisors and logistics managers — where, when, and how often risk concentrates.")

# ------------------------------------------------------------------ filters --
f1, f2, f3 = st.columns([2, 2, 2])
with f1:
    bays = ["All"] + sorted(df["bay"].dropna().unique().tolist())
    bay = st.selectbox("Loading bay", bays)
with f2:
    behaviours = ["All"] + sorted(df["behaviour_type"].unique().tolist())
    behaviour = st.selectbox("Behaviour type", behaviours)
with f3:
    risks = st.multiselect("Risk levels", config.RISK_ORDER, default=config.RISK_ORDER)

view = df.copy()
if bay != "All":
    view = view[view["bay"] == bay]
if behaviour != "All":
    view = view[view["behaviour_type"] == behaviour]
if risks:
    view = view[view["risk_level"].isin(risks)]

if view.empty:
    st.info("No events match the current filters — adjust them above.", icon="🔍")
    st.stop()

view = view.copy()
view["_shift"] = view["timestamp"].apply(data_access.shift_of)
view["_hour"] = view["timestamp"].dt.hour
view["_day"] = view["timestamp"].dt.strftime("%Y-%m-%d")

RISK_COLORS = {"Low": "#22c55e", "Medium": "#eab308", "High": "#f97316", "Critical": "#ef4444"}

# ------------------------------------------------------------------ timeline --
st.subheader("Event timeline")
fig = px.scatter(
    view, x="timestamp", y="risk_level", color="risk_level",
    color_discrete_map=RISK_COLORS,
    category_orders={"risk_level": config.RISK_ORDER},
    hover_name="event_id",
    hover_data={"behaviour_type": True, "bay": True, "risk_level": False, "timestamp": "|%H:%M:%S"},
)
fig.update_traces(marker=dict(size=11, line=dict(width=1, color="#333")))
fig.update_layout(
    height=300, margin=dict(t=10, b=10, l=10, r=10),
    yaxis_title="", xaxis_title="",
    legend=dict(orientation="h", y=1.15),
)
st.plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------- trends --
t_col, h_col = st.columns(2)

with t_col:
    st.subheader("Behaviour trends by shift")
    trend = view.pivot_table(
        index="_day", columns="_shift", values="event_id", aggfunc="count", fill_value=0, observed=True
    )
    fig = px.bar(
        trend, barmode="group",
        category_orders={"_shift": [s for s, _ in config.SHIFTS]},
        labels={"value": "events", "_day": "", "_shift": "shift"},
        color_discrete_sequence=["#38bdf8", "#818cf8", "#c084fc"],
    )
    fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10), legend_title=None)
    st.plotly_chart(fig, use_container_width=True)

with h_col:
    st.subheader("Risk heatmap — bay × hour")
    heat = view.pivot_table(
        index="bay", columns="_hour", values="risk_score", aggfunc="mean"
    )
    heat = heat.reindex(columns=range(24)).T  # hours as rows for a natural read
    fig = px.imshow(
        heat.T, aspect="auto", color_continuous_scale="RdYlGn_r",
        labels=dict(x="hour of day (UTC)", y="bay", color="avg risk score"),
        text_auto=".2f",
    )
    fig.update_layout(height=300, margin=dict(t=10, b=10, l=10, r=10))
    st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------------- recurrence --
st.subheader("Recurring behaviours — retraining candidates")
st.caption("Behaviours repeating ≥3 times are the strongest candidates for targeted operator retraining (prevention loop).")

rec = (
    view.groupby("behaviour_type", observed=True)
    .agg(
        occurrences=("event_id", "count"),
        avg_risk=("risk_score", "mean"),
        high_or_critical=("risk_level", lambda s: int(s.isin(["High", "Critical"]).sum())),
        last_seen=("timestamp", "max"),
    )
    .sort_values("occurrences", ascending=False)
    .reset_index()
)
rec["behaviour_type"] = rec["behaviour_type"].str.replace("_", " ")
rec["avg_risk"] = rec["avg_risk"].round(2)
rec["last_seen"] = rec["last_seen"].dt.strftime("%Y-%m-%d %H:%M")
rec["status"] = rec["occurrences"].apply(lambda n: "🔁 recurring" if n >= 3 else "occasional")
st.dataframe(
    rec.rename(columns={
        "behaviour_type": "Behaviour", "occurrences": "Count",
        "avg_risk": "Avg risk score", "high_or_critical": "High/Critical",
        "last_seen": "Last seen", "status": "Status",
    }),
    use_container_width=True, hide_index=True,
)

# ------------------------------------------------------------ per-bay drill --
st.subheader("Risk by loading bay")
bay_stats = (
    view.groupby("bay", observed=True)
    .agg(events=("event_id", "count"), high=("risk_level", lambda s: int(s.isin(["High", "Critical"]).sum())), avg=("risk_score", "mean"))
    .sort_values("events", ascending=False)
)
worst = bay_stats.index[0]
st.markdown(
    f"**`{worst}`** currently concentrates the most risk — "
    f"{int(bay_stats.loc[worst, 'events'])} events, "
    f"{int(bay_stats.loc[worst, 'high'])} of them High/Critical. "
    "This is the bay to inspect first."
)
st.dataframe(bay_stats.round(2), use_container_width=True)
