"""Streamlit front-end for the hybrid recommender

Run locally:
    streamlit run app.py --server.port 8501

Set environment variable RECO_API_URL to your Azure Function URL
(e.g. https://<func-name>.azurewebsites.net/api/HttpReco?code=<key>)
"""
from __future__ import annotations

import os

import requests
import streamlit as st

API_URL = os.getenv("RECO_API_URL") or os.getenv("FUNCTION_URL") or ""
MAX_USER = 65_535
RAND_COUNT = 12

st.set_page_config(page_title="Article Recommender Demo", page_icon="📰")
st.title("📰 Hybrid Recommender Showcase")
st.markdown(
    """
    <style>
    /* Single source of truth for bubble styles */
    .stButton>button {
        width: 110px;
        height: 110px;
        border-radius: 50%;
        font-size: 22px;
        font-weight: 600;
        line-height: 1;
        color: #ffffff !important;
        border: 2px solid rgba(255,255,255,0.35);
        background: #4A90E2;
        cursor: pointer;
        transition: transform .2s ease-in-out;
        will-change: transform;
    }
    .stButton>button:hover {
        transform: scale(1.08);
    }
    .warm .stButton>button {
        background: linear-gradient(135deg, #4A90E2 0%, #357ABD 100%) !important;
        border-color: #357ABD !important;
    }
    .cold .stButton>button {
        background: linear-gradient(135deg, #E74C3C 0%, #C0392B 100%) !important;
        border-color: #C0392B !important;
    }
    .stNumberInput input, .stSelectbox select, .stTextInput input {
        color: inherit !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if not API_URL:
    st.warning("Set RECO_API_URL as env var to enable backend calls.")

# --- fixed demo users (verified against live API) ----------------------------
# Warm users: 4 hits in top-10 (2 at position 1), 8 misses → ~33% recall@10
WARM_USERS: list[int] = [
    1351, 7269,                                          # hit pos 1
    7772,                                                # hit pos 2
    39193,                                               # hit pos 6
    32824, 3668, 582, 3696, 52305, 42204, 49076, 48519,  # misses
]

# Cold-start demo: 3 hits in top-10 (1 at position 1), 9 misses → ~25% recall@10
# Uses pop_list.npy (global popularity from training data).
COLD_USERS: list[int] = [
    24184,                                               # hit pos 1
    701,                                                 # hit pos 3
    571,                                                 # hit pos 6
    2052, 3305, 17610, 20538, 277, 2931, 3535, 6442, 6987,  # misses
]

if "sample_users" not in st.session_state:
    st.session_state.sample_users = WARM_USERS[:]
if "sample_cold" not in st.session_state:
    st.session_state.sample_cold = COLD_USERS[:]
if "selected_uid" not in st.session_state:
    st.session_state.selected_uid = 0
if "force_cold" not in st.session_state:
    st.session_state.force_cold = False
if "manual_uid" not in st.session_state:
    st.session_state.manual_uid = int(st.session_state.selected_uid)

st.markdown("<div class='warm'>", unsafe_allow_html=True)
st.markdown("### 🔥 Warm users (have ground-truth)")
NUM_COLS = 4  # bubbles per row
# --- warm user bubbles -------------------------------------------------------
for i, uid in enumerate(st.session_state.sample_users[:RAND_COUNT]):
    if i % NUM_COLS == 0:
        cols = st.columns(NUM_COLS)
    col = cols[i % NUM_COLS]
    if col.button(str(uid), key=f"warm_{uid}"):
        st.session_state.selected_uid = uid
        st.session_state.manual_uid = uid
        st.session_state.force_cold = False

# close warm wrapper
st.markdown("</div>", unsafe_allow_html=True)
# --- cold user bubbles -------------------------------------------------------
st.markdown("<div class='cold'>", unsafe_allow_html=True)
st.markdown("### 🔴 Cold-start demo (context-only prediction)")
for i, uid in enumerate(st.session_state.sample_cold[:RAND_COUNT]):
    if i % NUM_COLS == 0:
        cols = st.columns(NUM_COLS)
    col = cols[i % NUM_COLS]
    if col.button(f"⭕️ {uid}", key=f"cold_{uid}"):
        st.session_state.selected_uid = uid
        st.session_state.manual_uid = uid
        st.session_state.force_cold = True

st.markdown("### Or enter a user ID")
# close cold wrapper
st.markdown("</div>", unsafe_allow_html=True)

manual_id = st.number_input("User ID", min_value=0, max_value=MAX_USER, step=1, key="manual_uid")
st.session_state.selected_uid = int(manual_id)
selected_uid = int(manual_id)

k = st.selectbox("How many recommendations?", [5, 10, 20], index=1)

if st.button("🔍 Get recommendations"):
    if not API_URL:
        st.error("API URL not configured.")
    else:
        with st.spinner("Calling backend …"):
            try:
                payload: dict = {"user_id": selected_uid, "k": k}
                if st.session_state.force_cold:
                    payload["force_cold"] = True
                resp = requests.post(API_URL, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                st.error(f"Request failed: {e}")
            else:
                st.success("Recommendations received!")
                is_cold_demo = st.session_state.force_cold
                user_type = "Cold-start (context only)" if is_cold_demo else "Warm (hybrid model)"
                st.write(f"**User:** {selected_uid}  ·  *{user_type}*")

                profile = data.get("user_profile", {}).get("used", {})
                if profile:
                    st.caption(f"Context used → OS: {profile.get('os')}, "
                               f"Device: {profile.get('device')}, "
                               f"Country: {profile.get('country')}")

                gt = data.get("ground_truth")
                recs = data.get("recommendations", [])
                if gt is not None:
                    hit = gt in recs
                    pos = recs.index(gt) + 1 if hit else None
                    if hit:
                        st.write(f"**Ground-truth click:** {gt}  ✅ found at position {pos}/{len(recs)}")
                    else:
                        st.write(f"**Ground-truth click:** {gt}  ❌ not in top-{len(recs)}")
                st.markdown("#### Top items")
                for rank, item in enumerate(recs, start=1):
                    marker = " ⬅️" if gt is not None and item == gt else ""
                    st.write(f"{rank}. Article {item}{marker}")
