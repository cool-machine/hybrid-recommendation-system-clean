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

# Initialize session state FIRST
if "sample_users" not in st.session_state:
    st.session_state.sample_users = random.sample(range(100), 12)
if "sample_cold" not in st.session_state:
    st.session_state.sample_cold = random.sample(range(1000, 1100), 12)
if "selected_uid" not in st.session_state:
    st.session_state.selected_uid = 0

# Let's go back to a working solution with proper CSS styling
st.markdown("""
<style>
/* Force circular buttons with animations */
div[data-testid="stButton"] > button {
    width: 100px !important;
    height: 100px !important;
    border-radius: 50% !important;
    font-size: 18px !important;
    font-weight: bold !important;
    color: white !important;
    text-shadow: 1px 1px 2px rgba(0,0,0,0.8) !important;
    animation: float 4s ease-in-out infinite !important;
    transition: transform 0.3s ease !important;
}

div[data-testid="stButton"] > button:hover {
    transform: scale(1.2) !important;
}

/* Animation keyframes */
@keyframes float {
    0%, 100% { transform: translateY(0px) rotate(0deg); }
    25% { transform: translateY(-10px) rotate(5deg); }
    50% { transform: translateY(-5px) rotate(-3deg); }
    75% { transform: translateY(-12px) rotate(3deg); }
}

/* Stagger the animations */
div[data-testid="stButton"]:nth-child(1) > button { animation-delay: 0s; }
div[data-testid="stButton"]:nth-child(2) > button { animation-delay: 0.5s; }
div[data-testid="stButton"]:nth-child(3) > button { animation-delay: 1s; }
div[data-testid="stButton"]:nth-child(4) > button { animation-delay: 1.5s; }
div[data-testid="stButton"]:nth-child(5) > button { animation-delay: 2s; }
div[data-testid="stButton"]:nth-child(6) > button { animation-delay: 2.5s; }
</style>

<script>
function styleButtons() {
    const buttons = document.querySelectorAll('button');
    buttons.forEach(button => {
        const text = button.textContent.trim();
        
        if (/^\d+$/.test(text)) {
            // Warm user button - blue
            button.style.background = 'linear-gradient(135deg, #4A90E2, #1e3c72)';
            button.style.border = '3px solid #357ABD';
        } else if (text.includes('⭕')) {
            // Cold user button - red  
            button.style.background = 'linear-gradient(135deg, #E74C3C, #8B0000)';
            button.style.border = '3px solid #C0392B';
        } else if (text.includes('Get recommendations')) {
            // Recommendation button - green, normal shape
            button.style.background = 'linear-gradient(135deg, #28a745, #155724)';
            button.style.border = '3px solid #20c997';
            button.style.borderRadius = '10px';
            button.style.width = 'auto';
            button.style.height = 'auto';
            button.style.animation = 'none';
        }
    });
}

// Run styling function
styleButtons();
setInterval(styleButtons, 1000);

// Watch for new buttons
const observer = new MutationObserver(styleButtons);
observer.observe(document.body, {childList: true, subtree: true});
</script>
""", unsafe_allow_html=True)

# Show current selection
if st.session_state.selected_uid > 0:
    user_type = "🔥 Warm user" if st.session_state.selected_uid < 1000 else "🔴 Cold user"
    st.success(f"🎯 Selected: User {st.session_state.selected_uid} ({user_type})")
else:
    st.info("👆 Select a user to get recommendations")

# Add selection buttons below the floating balls for functionality
st.markdown("### 🔥 Warm Users (Blue Balls)")
warm_cols = st.columns(6)
for i, uid in enumerate(st.session_state.sample_users[:6]):
    if warm_cols[i].button(f"{uid}", key=f"warm_select_{uid}"):
        st.session_state.selected_uid = uid
        st.rerun()

st.markdown("### 🔴 Cold Users (Red Balls)")  
cold_cols = st.columns(6)
for i, uid in enumerate(st.session_state.sample_cold[:6]):
    if cold_cols[i].button(f"⭕{uid}", key=f"cold_select_{uid}"):
        st.session_state.selected_uid = uid
        st.rerun()

# Manual input
st.markdown("### Or enter a user ID")
manual_id = st.number_input("User ID", min_value=0, max_value=MAX_USER, step=1, 
                           value=st.session_state.selected_uid)
st.session_state.selected_uid = int(manual_id)

# Recommendations settings
k = st.selectbox("How many recommendations?", [5, 10, 20], index=1)

# Context settings with validation
with st.expander("Context (for cold users)"):
    device_group = st.selectbox("Device Type", ["Mobile", "Desktop", "Tablet"], index=1)
    
    # Create OS options based on device type
    if device_group == "Mobile":
        os_options = ["Android", "iOS", "Other Mobile"]
        default_os = "Android"
    elif device_group == "Desktop":
        os_options = ["Windows", "macOS", "Linux", "Other Desktop"]
        default_os = "Windows"
    elif device_group == "Tablet":
        os_options = ["Android", "iOS", "Windows", "Other Tablet"]
        default_os = "iOS"
    
    os_selection = st.selectbox("Operating System", os_options, 
                               index=os_options.index(default_os))
    
    # Map to original numeric values
    device_mapping = {"Mobile": 0, "Desktop": 1, "Tablet": 2}
    os_mapping = {
        "Android": 0, "iOS": 1, "Windows": 2, "macOS": 3, 
        "Linux": 4, "Other Mobile": 5, "Other Desktop": 5, "Other Tablet": 5
    }
    
    device_group_val = device_mapping[device_group]
    os_id = os_mapping[os_selection]
    
    country = st.text_input("Country code (ISO 2)", "US", max_chars=2)
    
    # Show validation info
    st.caption(f"📱 Selected: {device_group} device running {os_selection}")
    
    # Validation warnings
    if device_group == "Desktop" and os_selection in ["Android", "iOS"]:
        st.error("❌ Invalid combination: Desktop devices don't run mobile operating systems")
    elif device_group == "Mobile" and os_selection in ["Windows", "macOS", "Linux"]:
        st.warning("⚠️ Unusual combination: Mobile devices rarely run desktop operating systems")

# Get recommendations
if st.button("🔍 Get recommendations", type="primary"):
    if st.session_state.selected_uid == 0:
        st.warning("⚠️ Please select a user first!")
    else:
        payload = {
            "user_id": st.session_state.selected_uid, 
            "k": k, 
            "env": {"device": device_group_val, "os": os_id, "country": country.upper()}
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