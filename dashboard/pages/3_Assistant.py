"""
dashboard/pages/3_Assistant.py — Member 4.

Chat panel for the AI Operations Assistant (Member 3's service). The
dashboard only calls Member 3's interface — it never generates answers
itself. Until the service is connected, this page shows an honest
placeholder with the query types the challenge doc requires.
"""

from __future__ import annotations

import sys
from pathlib import Path

_PAGES = Path(__file__).resolve().parent
_DASH = _PAGES.parent
for _p in (str(_DASH), str(_DASH.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import streamlit as st

import assistant_client
import ui

st.set_page_config(page_title="Assistant — Warehouse-AI", page_icon="🧠", layout="centered")

df = ui.require_events()
source = ui.sidebar()

st.title("🧠 AI Operations Assistant")
st.caption("Ask questions about detected events — answers come only from the event store, never invented.")

MESSAGES_KEY = "assistant_messages"

# --- try connecting ----------------------------------------------------------
connected, unavailable = True, None
try:
    # cheap availability probe: asking for a trivial fact exercises the same
    # path a real question takes, without displaying the result
    assistant_client.ask("How many events are in the store?")
except assistant_client.AssistantUnavailable as exc:
    connected, unavailable = False, exc
except Exception as exc:  # service present but failing -> honest state, no crash
    connected, unavailable = False, assistant_client.AssistantUnavailable(
        f"Assistant service is present but returned an error: {exc}"
    )

if not connected:
    st.info(
        f"**Assistant not connected yet.**\n\n{unavailable.reason}\n\n"
        "Once Member 3's service is published, this panel answers questions "
        "grounded strictly in detected events. The challenge doc's example "
        "queries will be supported:",
        icon="🔌",
    )
    for q in assistant_client.AssistantUnavailable.SUGGESTIONS:
        st.markdown(f"- *“{q}”*")
    st.caption(
        "Integration (dashboard side is already wired): set `ASSISTANT_URL` to the "
        "assistant's HTTP endpoint, or drop `assistant.py` with `ask(question)` "
        "into `backend-assistant/`."
    )
    st.stop()

# --- chat ---------------------------------------------------------------------
if MESSAGES_KEY not in st.session_state:
    st.session_state[MESSAGES_KEY] = [
        {"role": "assistant", "content": "Ask me anything about the detected handling events."}
    ]

for msg in st.session_state[MESSAGES_KEY]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

question = st.chat_input("e.g. Which loading bay had the highest number of risky events?")
if question:
    st.session_state[MESSAGES_KEY].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        try:
            with st.spinner("Thinking…"):
                answer = assistant_client.ask(question)
        except assistant_client.AssistantUnavailable as exc:
            answer = f"⚠️ The assistant service became unavailable: {exc.reason}"
        except Exception as exc:
            answer = f"⚠️ The assistant service returned an error: {exc}"
        st.write(answer)
    st.session_state[MESSAGES_KEY].append({"role": "assistant", "content": answer})
