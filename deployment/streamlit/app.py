"""Streamlit front-end for the hybrid recommender

Run locally:
    streamlit run app.py --server.port 8501

Set environment variable RECO_API_URL to your Azure Function URL
(e.g. https://<func-name>.azurewebsites.net/api/HttpReco?code=<key>)
"""
from __future__ import annotations

import os
import pathlib
import random

import numpy as np
import requests
import streamlit as st

API_URL = os.getenv("RECO_API_URL") or os.getenv("FUNCTION_URL") or ""
MAX_USER = 65_535  # upper bound of user IDs
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

# --- pick list of random users each session ---------------------------------
# warm users (with ground-truth)
GT_USERS: list[int]
try:
    npy_path = pathlib.Path(__file__).parent.parent / "functions_reco" / "artifacts" / "gt_users.npy"
    GT_USERS = np.load(npy_path).astype(int).tolist() if npy_path.exists() else []
except Exception:
    GT_USERS = []

# fallback: if still empty, fill with a range so that bubbles show up in demo mode
if not GT_USERS:
    GT_USERS = list(range(100))  # first 100 user IDs as generic warm users

# cold users (no history)
COLD_USERS: list[int]
try:
    cold_path = pathlib.Path(__file__).parent.parent / "functions_reco" / "artifacts" / "cold_users.npy"
    COLD_USERS = np.load(cold_path).astype(int).tolist() if cold_path.exists() else []
except Exception:
    COLD_USERS = []
# fallback demo pool
if not COLD_USERS:
    COLD_USERS = list(range(1000, 1100))

if "sample_users" not in st.session_state:
    st.session_state.sample_users = random.sample(GT_USERS, min(RAND_COUNT, len(GT_USERS))) if GT_USERS else []
if "sample_cold" not in st.session_state:
    st.session_state.sample_cold = random.sample(COLD_USERS, min(RAND_COUNT, len(COLD_USERS))) if COLD_USERS else []
if "selected_uid" not in st.session_state:
    st.session_state.selected_uid = 0
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

# close warm wrapper
st.markdown("</div>", unsafe_allow_html=True)
# --- cold user bubbles -------------------------------------------------------
st.markdown("<div class='cold'>", unsafe_allow_html=True)
st.markdown("### 🔴 Cold users (no history)")
for i, uid in enumerate(st.session_state.sample_cold[:RAND_COUNT]):
    if i % NUM_COLS == 0:
        cols = st.columns(NUM_COLS)
    col = cols[i % NUM_COLS]
    if col.button(f"⭕️ {uid}", key=f"cold_{uid}"):
        st.session_state.selected_uid = uid
        st.session_state.manual_uid = uid

st.markdown("### Or enter a user ID")
# close cold wrapper
st.markdown("</div>", unsafe_allow_html=True)

manual_id = st.number_input("User ID", min_value=0, max_value=MAX_USER, step=1, key="manual_uid")
st.session_state.selected_uid = int(manual_id)
selected_uid = int(manual_id)

k = st.selectbox("How many recommendations?", [5, 10, 20], index=1)

# --- contextual fields for cold-start ---------------------------------------
with st.expander("Context (for cold users)"):
    device_group = st.selectbox("Device group", {"mobile":0,"desktop":1,"tablet":2}, index=1, key="dev_grp")
    os_id        = st.selectbox("OS", {"Android":0,"iOS":1,"Windows":2,"macOS":3,"Linux":4,"Other":5}, index=3, key="os_id")
    country      = st.text_input("Country code (ISO 2)", "US", max_chars=2)

if st.button("🔍 Get recommendations"):
    if not API_URL:
        st.error("API URL not configured.")
    else:
        with st.spinner("Calling backend …"):
            try:
                payload = {"user_id": selected_uid, "k": k, "env": {"device": device_group, "os": os_id, "country": country.upper()}}
                resp = requests.post(API_URL, json=payload, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                st.error(f"Request failed: {e}")
            else:
                st.success("Recommendations received!")
                user_type = "First-time user" if selected_uid in COLD_USERS else "Returning user"
                st.write(f"**User:** {selected_uid}  ·  *{user_type}*")
                if data.get('ground_truth') is not None:
                    st.write(f"**Ground-truth click:** {data.get('ground_truth')}")
                st.markdown("#### Top items")
                for rank, item in enumerate(data.get("recommendations", []), start=1):
                    st.write(f"{rank}. Article {item}")
