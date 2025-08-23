"""Streamlit front-end for the hybrid recommender - DEBUG VERSION"""
import os
import random
import requests
import streamlit as st
import traceback

# Configure API URL
try:
    API_URL = st.secrets.get("RECO_API_URL", "")
except:
    API_URL = os.getenv("RECO_API_URL", "")

if not API_URL:
    API_URL = "https://ocp9funcapp-recsys.azurewebsites.net/api/reco"

st.set_page_config(page_title="Article Recommender Demo", page_icon="📰")
st.title("📰 Hybrid Recommender Showcase")

# Debug info
st.sidebar.subheader("🔍 Debug Info")
st.sidebar.write(f"API URL: {API_URL}")
st.sidebar.write(f"Session state keys: {list(st.session_state.keys())}")


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

# Initialize session state
if "sample_users" not in st.session_state:
    st.session_state.sample_users = random.sample(range(100), 8)
if "sample_cold" not in st.session_state:
    st.session_state.sample_cold = random.sample(range(1000, 1100), 8)
if "selected_uid" not in st.session_state:
    st.session_state.selected_uid = 0
if "debug_clicks" not in st.session_state:
    st.session_state.debug_clicks = 0

# Debug current state
st.sidebar.write(f"Selected UID: {st.session_state.selected_uid}")
st.sidebar.write(f"Debug clicks: {st.session_state.debug_clicks}")

# Test basic button first
if st.button("🧪 Test Basic Button"):
    st.session_state.debug_clicks += 1
    st.success(f"✅ Basic button works! Clicks: {st.session_state.debug_clicks}")

# Show current selection
if st.session_state.selected_uid > 0:
    st.info(f"🎯 Currently selected: User {st.session_state.selected_uid}")

# Warm users section
st.markdown("### 🔥 Warm users (have history)")

try:
    cols = st.columns(4)
    for i, uid in enumerate(st.session_state.sample_users):
        col = cols[i % 4]
        if col.button(str(uid), key=f"warm_{uid}"):
            st.session_state.selected_uid = uid
            st.session_state.debug_clicks += 1
            st.success(f"Selected warm user: {uid}")
            # Force rerun to show selection immediately
            st.rerun()
except Exception as e:
    st.error(f"Error in warm users section: {str(e)}")
    st.code(traceback.format_exc())

# Cold users section  
st.markdown("### 🔴 Cold users (no history)")

try:
    cols = st.columns(4)
    for i, uid in enumerate(st.session_state.sample_cold):
        col = cols[i % 4]
        if col.button(f"⭕ {uid}", key=f"cold_{uid}"):
            st.session_state.selected_uid = uid
            st.session_state.debug_clicks += 1
            st.success(f"Selected cold user: {uid}")
            # Force rerun to show selection immediately
            st.rerun()
except Exception as e:
    st.error(f"Error in cold users section: {str(e)}")
    st.code(traceback.format_exc())

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

# Get recommendations - with detailed debugging
if st.button("🔍 Get recommendations"):
    st.write("🔍 Starting recommendation request...")
    
    # Show request details
    payload = {
        "user_id": st.session_state.selected_uid, 
        "k": k, 
        "env": {"device": device_group, "os": os_id, "country": country.upper()}
    }
    
    st.write("📤 Request payload:", payload)
    st.write("🌐 API URL:", API_URL)
    
    with st.spinner("Getting recommendations..."):
        try:
            st.write("📡 Sending request...")
            response = requests.post(API_URL, json=payload, timeout=30)
            
            st.write(f"📨 Response status: {response.status_code}")
            st.write(f"📨 Response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                st.error(f"❌ API error {response.status_code}: {response.text}")
            else:
                data = response.json()
                st.write("📥 Raw response:", data)
                
                st.success("✅ Recommendations received!")
                st.write(f"**User:** {st.session_state.selected_uid}")
                
                if data.get('ground_truth'):
                    st.write(f"**Ground truth:** {data['ground_truth']}")
                
                recommendations = data.get("recommendations", [])
                if recommendations:
                    st.markdown("#### 📋 Recommended articles:")
                    for rank, item in enumerate(recommendations, 1):
                        st.write(f"{rank}. Article {item}")
                else:
                    st.warning("No recommendations returned")
                    
        except requests.exceptions.Timeout:
            st.error("❌ Request timed out - API might be slow or unavailable")
        except requests.exceptions.ConnectionError:
            st.error("❌ Connection error - cannot reach API")  
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Request error: {str(e)}")
        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")
            st.code(traceback.format_exc())