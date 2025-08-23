"""Streamlit front-end for the hybrid recommender"""
from __future__ import annotations

import os
import pathlib
import random

import pandas as pd
import requests
import streamlit as st

# Configure API URL for Streamlit Cloud
try:
    API_URL = st.secrets.get("RECO_API_URL", "")
except:
    API_URL = os.getenv("RECO_API_URL") or os.getenv("FUNCTION_URL") or ""

if not API_URL:
    API_URL = "https://ocp9funcapp-recsys.azurewebsites.net/api/reco"

MAX_USER = 65_535
RAND_COUNT = 12

st.set_page_config(page_title="Article Recommender Demo", page_icon="📰")

st.title("📰 Hybrid Recommender Showcase")


# Simple styling - no complex CSS animations to avoid conflicts
st.markdown("""
<style>
.warm .stButton>button {
    background-color: #4A90E2 !important;
    color: white !important;
    border: 2px solid #357ABD !important;
    border-radius: 50%;
    width: 80px;
    height: 80px;
}
.cold .stButton>button {
    background-color: #E74C3C !important;
    color: white !important;
    border: 2px solid #C0392B !important;
    border-radius: 50%;
    width: 80px;
    height: 80px;
}
</style>
""", unsafe_allow_html=True)

# Create sample users for demo
if "sample_users" not in st.session_state:
    st.session_state.sample_users = random.sample(range(100), 8)
if "sample_cold" not in st.session_state:
    st.session_state.sample_cold = random.sample(range(1000, 1100), 8)
if "selected_uid" not in st.session_state:
    st.session_state.selected_uid = 0

# Warm users section
st.markdown("<div class='warm'>", unsafe_allow_html=True)
st.markdown("### 🔥 Warm users (have history)")

cols = st.columns(4)
for i, uid in enumerate(st.session_state.sample_users):
    col = cols[i % 4]
    if col.button(str(uid), key=f"warm_{uid}"):
        st.session_state.selected_uid = uid

st.markdown("</div>", unsafe_allow_html=True)

# Cold users section
st.markdown("<div class='cold'>", unsafe_allow_html=True)
st.markdown("### 🔴 Cold users (no history)")

cols = st.columns(4)
for i, uid in enumerate(st.session_state.sample_cold):
    col = cols[i % 4]
    if col.button(f"⭕ {uid}", key=f"cold_{uid}"):
        st.session_state.selected_uid = uid

st.markdown("</div>", unsafe_allow_html=True)

# Manual input
st.markdown("### Or enter a user ID")
manual_id = st.number_input("User ID", min_value=0, max_value=MAX_USER, step=1, 
                           value=st.session_state.selected_uid)
st.session_state.selected_uid = int(manual_id)

# Recommendations settings
k = st.selectbox("How many recommendations?", [5, 10, 20], index=1)

# Context settings
with st.expander("Context (for cold users)"):
    device_group = st.selectbox("Device", {"mobile": 0, "desktop": 1, "tablet": 2}, index=1)
    os_id = st.selectbox("OS", {"Android": 0, "iOS": 1, "Windows": 2, "macOS": 3, "Linux": 4, "Other": 5}, index=3)
    country = st.text_input("Country code", "US", max_chars=2)

# Get recommendations
if st.button("🔍 Get recommendations"):
    with st.spinner("Getting recommendations..."):
        try:
            payload = {
                "user_id": st.session_state.selected_uid, 
                "k": k, 
                "env": {"device": device_group, "os": os_id, "country": country.upper()}
            }
            response = requests.post(API_URL, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            st.success("✅ Recommendations received!")
            st.write(f"**User:** {st.session_state.selected_uid}")
            
            if data.get('ground_truth'):
                st.write(f"**Ground truth:** {data['ground_truth']}")
            
            st.markdown("#### 📋 Recommended articles:")
            for rank, item in enumerate(data.get("recommendations", []), 1):
                st.write(f"{rank}. Article {item}")
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")