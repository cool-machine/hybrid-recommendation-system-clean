"""
Debug version - minimal Streamlit app to identify the crash issue
"""
import streamlit as st
import requests
import random

st.set_page_config(page_title="Debug Recommender", page_icon="🔍")

st.title("🔍 Debug Recommender")

# Test basic state management
if "debug_counter" not in st.session_state:
    st.session_state.debug_counter = 0
if "selected_user" not in st.session_state:
    st.session_state.selected_user = None

st.write(f"Debug counter: {st.session_state.debug_counter}")
st.write(f"Selected user: {st.session_state.selected_user}")

# Test 1: Basic button functionality
st.subheader("Test 1: Basic Button Click")
if st.button("Test Button"):
    st.session_state.debug_counter += 1
    st.write("✅ Button click works!")

# Test 2: Button with state change
st.subheader("Test 2: User Selection Buttons")
test_users = [12, 34, 56, 78]

cols = st.columns(4)
for i, user_id in enumerate(test_users):
    with cols[i]:
        if st.button(f"User {user_id}", key=f"user_{user_id}"):
            st.session_state.selected_user = user_id
            st.session_state.debug_counter += 1
            st.rerun()  # Force immediate rerun

# Test 3: Show current selection
if st.session_state.selected_user:
    st.success(f"Selected user: {st.session_state.selected_user}")
    
    # Test 4: Simple API call
    if st.button("Test API Call"):
        with st.spinner("Testing API..."):
            try:
                # Test with a simple endpoint first
                test_payload = {
                    "user_id": st.session_state.selected_user,
                    "k": 5
                }
                st.write("Payload:", test_payload)
                
                # Let's test the API URL first
                api_url = "https://ocp9funcapp-recsys.azurewebsites.net/api/reco"
                st.write("API URL:", api_url)
                
                response = requests.post(api_url, json=test_payload, timeout=10)
                st.write("Response status:", response.status_code)
                st.write("Response headers:", dict(response.headers))
                
                if response.status_code == 200:
                    data = response.json()
                    st.write("Response data:", data)
                else:
                    st.error(f"API returned {response.status_code}: {response.text}")
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.write("Exception type:", type(e).__name__)
                import traceback
                st.code(traceback.format_exc())

# Debug info
st.subheader("Debug Info")
st.write("Session state keys:", list(st.session_state.keys()))
st.write("Session state:", dict(st.session_state))