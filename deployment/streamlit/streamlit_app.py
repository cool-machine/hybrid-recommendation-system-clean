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

# Custom floating ball interface using HTML5 Canvas
import streamlit.components.v1 as components

# Create floating balls component with initialized session state
floating_balls_html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        .ball-container {{
            position: relative;
            width: 100%;
            height: 400px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 20px;
            overflow: hidden;
            margin: 20px 0;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        .ball {{
            position: absolute;
            width: 80px;
            height: 80px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 18px;
            cursor: pointer;
            transition: transform 0.2s;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }}
        .ball:hover {{
            transform: scale(1.2) !important;
            z-index: 100;
        }}
        .warm-ball {{
            background: radial-gradient(circle at 30% 30%, #87CEEB, #4A90E2, #1e3c72);
            border: 3px solid #357ABD;
        }}
        .cold-ball {{
            background: radial-gradient(circle at 30% 30%, #FF6B6B, #E74C3C, #8B0000);
            border: 3px solid #C0392B;
        }}
        .section-title {{
            color: white;
            font-size: 24px;
            font-weight: bold;
            text-align: center;
            margin: 10px 0;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }}
        #selectedUser {{
            position: absolute;
            top: 10px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <div class="ball-container" id="ballContainer">
        <div id="selectedUser">Click on a floating ball to select a user</div>
    </div>
    
    <script>
        let selectedUserId = 0;
        let balls = [];
        
        // Sample user data
        const warmUsers = {str(st.session_state.sample_users).replace('[', '').replace(']', '')};
        const coldUsers = {str(st.session_state.sample_cold).replace('[', '').replace(']', '')};
        
        class FloatingBall {{
            constructor(userId, isWarm, container) {{
                this.userId = userId;
                this.isWarm = isWarm;
                this.container = container;
                this.element = this.createElement();
                this.container.appendChild(this.element);
                
                // Random starting position
                this.x = Math.random() * (container.offsetWidth - 80);
                this.y = Math.random() * (container.offsetHeight - 80);
                
                // Random velocity
                this.vx = (Math.random() - 0.5) * 2;
                this.vy = (Math.random() - 0.5) * 2;
                
                // Floating animation
                this.time = Math.random() * Math.PI * 2;
                this.floatSpeed = 0.02 + Math.random() * 0.02;
                this.floatAmplitude = 10 + Math.random() * 20;
                
                this.updatePosition();
                this.animate();
            }}
            
            createElement() {{
                const ball = document.createElement('div');
                ball.className = `ball ${{this.isWarm ? 'warm-ball' : 'cold-ball'}}`;
                ball.textContent = this.isWarm ? this.userId : `⭕${{this.userId}}`;
                ball.addEventListener('click', () => this.select());
                return ball;
            }}
            
            select() {{
                selectedUserId = this.userId;
                document.getElementById('selectedUser').textContent = `Selected User: ${{this.userId}} (${{this.isWarm ? 'Warm' : 'Cold'}} user)`;
                
                // Send selection back to Streamlit
                window.parent.postMessage({{
                    type: 'ballClick',
                    userId: this.userId
                }}, '*');
                
                // Add selection effect
                this.element.style.boxShadow = '0 0 30px rgba(255,255,0,0.8), 0 5px 15px rgba(0,0,0,0.3)';
                setTimeout(() => {{
                    this.element.style.boxShadow = '0 5px 15px rgba(0,0,0,0.3)';
                }}, 1000);
            }}
            
            updatePosition() {{
                this.element.style.left = this.x + 'px';
                this.element.style.top = this.y + 'px';
            }}
            
            animate() {{
                // Floating motion
                this.time += this.floatSpeed;
                const floatX = Math.sin(this.time) * this.floatAmplitude * 0.5;
                const floatY = Math.cos(this.time * 1.2) * this.floatAmplitude;
                
                // Boundary bouncing
                this.x += this.vx;
                this.y += this.vy;
                
                if (this.x <= 0 || this.x >= this.container.offsetWidth - 80) {{
                    this.vx *= -1;
                }}
                if (this.y <= 0 || this.y >= this.container.offsetHeight - 80) {{
                    this.vy *= -1;
                }}
                
                // Keep within bounds
                this.x = Math.max(0, Math.min(this.container.offsetWidth - 80, this.x));
                this.y = Math.max(0, Math.min(this.container.offsetHeight - 80, this.y));
                
                // Apply floating effect
                this.element.style.left = (this.x + floatX) + 'px';
                this.element.style.top = (this.y + floatY) + 'px';
                
                // Continue animation
                requestAnimationFrame(() => this.animate());
            }}
        }}
        
        // Initialize balls
        function initBalls() {{
            const container = document.getElementById('ballContainer');
            
            // Create warm user balls
            warmUsers.forEach(userId => {{
                balls.push(new FloatingBall(userId, true, container));
            }});
            
            // Create cold user balls  
            coldUsers.forEach(userId => {{
                balls.push(new FloatingBall(userId, false, container));
            }});
        }}
        
        // Start the animation when DOM is ready
        document.addEventListener('DOMContentLoaded', initBalls);
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', initBalls);
        }} else {{
            initBalls();
        }}
    </script>
</body>
</html>
"""

components.html(floating_balls_html, height=450)

# Instructions and current selection
st.markdown("### 🌟 Interactive Floating Ball Interface")
st.markdown("**Blue balls** = Warm users (with history) | **Red balls** = Cold users (no history)")

# Show current selection
if st.session_state.selected_uid > 0:
    user_type = "🔥 Warm user" if st.session_state.selected_uid < 1000 else "🔴 Cold user"
    st.success(f"🎯 Selected: User {st.session_state.selected_uid} ({user_type})")
else:
    st.info("👆 Click on a floating ball above to select a user")

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