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

# Inject powerful CSS with higher specificity and JavaScript for dynamic styling
import streamlit.components.v1 as components

components.html("""
<style>
/* FORCE OVERRIDE ALL STREAMLIT BUTTON STYLES */
div[data-testid="stButton"] > button,
button[kind="secondary"],
button[kind="primary"],
.stButton > button,
.stButton button {
    width: 110px !important;
    height: 110px !important;
    border-radius: 50% !important;
    font-size: 20px !important;
    font-weight: 700 !important;
    color: #ffffff !important;
    line-height: 1.2 !important;
    cursor: pointer !important;
    border: 3px solid #4A90E2 !important;
    background: linear-gradient(135deg, #4A90E2 0%, #357ABD 100%) !important;
    box-shadow: 0 8px 16px rgba(0,0,0,0.2), inset 0 1px 0 rgba(255,255,255,0.3) !important;
    transition: all 0.3s ease !important;
    transform-style: preserve-3d !important;
    animation: float3d 15s ease-in-out infinite !important;
}

/* Hover effects */
div[data-testid="stButton"] > button:hover,
.stButton > button:hover {
    transform: scale(1.15) translateY(-5px) !important;
    box-shadow: 0 12px 24px rgba(0,0,0,0.3) !important;
}

/* 3D Animation Keyframes */
@keyframes float3d {
    0% { transform: translate3d(0px, 0px, 0px) rotateX(0deg) rotateY(0deg); }
    25% { transform: translate3d(10px, -15px, 20px) rotateX(10deg) rotateY(-10deg); }
    50% { transform: translate3d(-12px, 10px, -25px) rotateX(-8deg) rotateY(8deg); }
    75% { transform: translate3d(15px, 8px, 22px) rotateX(12deg) rotateY(-12deg); }
    100% { transform: translate3d(0px, 0px, 0px) rotateX(0deg) rotateY(0deg); }
}

/* Different animation delays for staggered effect */
div[data-testid="stButton"]:nth-of-type(2n) > button { animation-delay: 2s; animation-direction: reverse; }
div[data-testid="stButton"]:nth-of-type(3n) > button { animation-delay: 4s; animation-direction: alternate; }
div[data-testid="stButton"]:nth-of-type(4n) > button { animation-delay: 6s; animation-duration: 20s; }
div[data-testid="stButton"]:nth-of-type(5n) > button { animation-delay: 8s; }
</style>

<script>
// JavaScript to dynamically style buttons based on content
function styleButtons() {
    // Find all buttons
    const buttons = document.querySelectorAll('button');
    
    buttons.forEach(button => {
        const text = button.textContent.trim();
        
        // Style warm user buttons (numbers without ⭕️)
        if (/^\\d+$/.test(text)) {
            button.style.background = 'linear-gradient(135deg, #4A90E2 0%, #357ABD 100%)';
            button.style.border = '3px solid #357ABD';
            button.style.boxShadow = '0 8px 16px rgba(74,144,226,0.4), inset 0 1px 0 rgba(255,255,255,0.3)';
        }
        // Style cold user buttons (with ⭕️)
        else if (text.includes('⭕')) {
            button.style.background = 'linear-gradient(135deg, #E74C3C 0%, #C0392B 100%)';
            button.style.border = '3px solid #C0392B';
            button.style.boxShadow = '0 8px 16px rgba(231,76,60,0.4), inset 0 1px 0 rgba(255,255,255,0.3)';
        }
        // Style the recommendation button
        else if (text.includes('Get recommendations')) {
            button.style.width = 'auto';
            button.style.height = 'auto';
            button.style.borderRadius = '12px';
            button.style.background = 'linear-gradient(135deg, #28a745 0%, #20c997 100%)';
            button.style.border = '3px solid #20c997';
            button.style.animation = 'none';
            button.style.padding = '12px 24px';
        }
        
        // Ensure all buttons have white text
        button.style.color = '#ffffff';
        button.style.fontWeight = '700';
        button.style.textShadow = '1px 1px 2px rgba(0,0,0,0.8)';
    });
}

// Run immediately and on DOM changes
styleButtons();

// Watch for new buttons being added
const observer = new MutationObserver(function(mutations) {
    mutations.forEach(function(mutation) {
        if (mutation.type === 'childList') {
            setTimeout(styleButtons, 100);
        }
    });
});

observer.observe(document.body, {
    childList: true,
    subtree: true
});

// Also run periodically to catch any missed updates
setInterval(styleButtons, 1000);
</script>
""", height=0)

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