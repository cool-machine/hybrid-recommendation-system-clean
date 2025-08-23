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

# Constants
MAX_USER = 65_535

st.set_page_config(page_title="Article Recommender Demo", page_icon="📰")
st.title("📰 Hybrid Recommender Showcase")

# Add the beautiful 3D bubble CSS and animations
st.markdown("""
<style>
/* Base bubble styling with 3D animations */
.stButton>button {
    width: 110px !important;
    height: 110px !important;
    border-radius: 50% !important;
    font-size: 22px !important;
    font-weight: 600 !important;
    color: #ffffff !important;
    line-height: 1 !important;
    cursor: pointer !important;
    border: 2px solid rgba(255,255,255,0.4) !important;
    backdrop-filter: blur(4px) !important;
    background: transparent !important;
    perspective: 1000px !important;
    transform-style: preserve-3d !important;
    animation: float3d 18s ease-in-out infinite !important;
    transition: transform 0.25s !important;
    will-change: transform !important;
}

.stButton>button:hover {
    transform: scale(1.15) !important;
}

/* Warm user buttons - blue gradient */
.warm .stButton>button {
    background: linear-gradient(135deg, #4A90E2 0%, #357ABD 100%) !important;
    border: 2px solid #357ABD !important;
    color: #ffffff !important;
    box-shadow: inset -2px -2px 8px rgba(255,255,255,0.3), inset 2px 2px 8px rgba(0,0,0,0.2), 0 0 12px rgba(74,144,226,0.4) !important;
}

/* Cold user buttons - red gradient */  
.cold .stButton>button {
    background: linear-gradient(135deg, #E74C3C 0%, #C0392B 100%) !important;
    border: 2px solid #C0392B !important;
    color: #ffffff !important;
    box-shadow: inset -2px -2px 8px rgba(255,255,255,0.3), inset 2px 2px 8px rgba(0,0,0,0.2), 0 0 12px rgba(231,76,60,0.4) !important;
}

/* 3D floating animation */
@keyframes float3d {
    0% { transform: translate3d(0,0,0) rotateX(0deg) rotateY(0deg); }
    25% { transform: translate3d(18px,-25px,30px) rotateX(15deg) rotateY(-15deg); }
    50% { transform: translate3d(-22px,18px,-35px) rotateX(-12deg) rotateY(12deg); }
    75% { transform: translate3d(20px,12px,32px) rotateX(18deg) rotateY(-18deg); }
    100% { transform: translate3d(0,0,0) rotateX(0deg) rotateY(0deg); }
}

/* Stagger animations so bubbles don't move in sync */
.stButton>button:nth-of-type(2n) { animation-delay: 3s; animation-direction: reverse; }
.stButton>button:nth-of-type(3n) { animation-delay: 6s; animation-direction: alternate; }
.stButton>button:nth-of-type(4n) { animation-delay: 9s; animation-duration: 24s; }

/* Additional depth effect */
.warm .stButton>button::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    border-radius: 50%;
    background: radial-gradient(circle at 30% 35%, rgba(120,170,255,0.70) 0%, rgba(120,170,255,0.35) 55%, rgba(120,170,255,0.15) 100%);
    z-index: -1;
}

.cold .stButton>button::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    border-radius: 50%;
    background: radial-gradient(circle at 30% 35%, rgba(240,90,90,0.70) 0%, rgba(240,90,90,0.35) 55%, rgba(240,90,90,0.15) 100%);
    z-index: -1;
}

/* Ensure text is always visible */
.stButton>button {
    color: #ffffff !important;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.7) !important;
}

/* Get recommendations button styling */
.stButton>button:not([data-testid*="warm"]):not([data-testid*="cold"]) {
    background: linear-gradient(135deg, #28a745 0%, #20c997 100%) !important;
    border: 2px solid #20c997 !important;
    width: auto !important;
    height: auto !important;
    border-radius: 10px !important;
    animation: none !important;
}
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "sample_users" not in st.session_state:
    st.session_state.sample_users = random.sample(range(100), 12)
if "sample_cold" not in st.session_state:
    st.session_state.sample_cold = random.sample(range(1000, 1100), 12)
if "selected_uid" not in st.session_state:
    st.session_state.selected_uid = 0

# Show current selection with beautiful styling
if st.session_state.selected_uid > 0:
    st.success(f"🎯 Selected: User {st.session_state.selected_uid}")
else:
    st.info("👆 Click on a user bubble to select them")

# Warm users section with beautiful floating bubbles
st.markdown("<div class='warm'>", unsafe_allow_html=True)
st.markdown("### 🔥 Warm users (have history)")

cols = st.columns(4)
for i, uid in enumerate(st.session_state.sample_users):
    col = cols[i % 4]
    if col.button(str(uid), key=f"warm_{uid}"):
        st.session_state.selected_uid = uid
        st.rerun()

st.markdown("</div>", unsafe_allow_html=True)

# Cold users section with beautiful floating bubbles
st.markdown("<div class='cold'>", unsafe_allow_html=True)
st.markdown("### 🔴 Cold users (no history)")

cols = st.columns(4)
for i, uid in enumerate(st.session_state.sample_cold):
    col = cols[i % 4]
    if col.button(f"⭕️ {uid}", key=f"cold_{uid}"):
        st.session_state.selected_uid = uid
        st.rerun()

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
if st.button("🔍 Get recommendations", type="primary"):
    if st.session_state.selected_uid == 0:
        st.warning("⚠️ Please select a user first!")
    else:
        payload = {
            "user_id": st.session_state.selected_uid, 
            "k": k, 
            "env": {"device": device_group, "os": os_id, "country": country.upper()}
        }
        
        with st.spinner("🤖 Getting sophisticated recommendations..."):
            try:
                response = requests.post(API_URL, json=payload, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                st.success("✅ Recommendations received!")
                
                # Show user info with better formatting
                user_type = "🔥 Warm user (has history)" if st.session_state.selected_uid < 1000 else "🔴 Cold user (no history)"
                st.info(f"**User {st.session_state.selected_uid}** • {user_type}")
                
                # Show user profile if available
                if 'user_profile' in data:
                    profile = data['user_profile']
                    if profile.get('stored'):
                        st.write(f"📱 **Profile:** Device: {profile['stored'].get('device')}, OS: {profile['stored'].get('os')}, Country: {profile['stored'].get('country')}")
                
                # Show ground truth
                if data.get('ground_truth'):
                    st.write(f"🎯 **Ground truth click:** Article {data['ground_truth']}")
                
                # Show recommendations with beautiful formatting
                recommendations = data.get("recommendations", [])
                if recommendations:
                    st.markdown("### 🎯 Recommended Articles")
                    
                    # Create beautiful recommendation cards
                    for rank, item in enumerate(recommendations, 1):
                        if rank == 1:
                            st.markdown(f"🥇 **{rank}. Article {item}** ⭐")
                        elif rank == 2:
                            st.markdown(f"🥈 **{rank}. Article {item}**")
                        elif rank == 3:
                            st.markdown(f"🥉 **{rank}. Article {item}**")
                        else:
                            st.write(f"{rank}. Article {item}")
                else:
                    st.warning("No recommendations returned")
                    
            except requests.exceptions.Timeout:
                st.error("⏰ Request timed out - API might be slow")
            except requests.exceptions.ConnectionError:
                st.error("🔌 Cannot reach API - please check connection")  
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                with st.expander("🔧 Debug info"):
                    st.code(traceback.format_exc())