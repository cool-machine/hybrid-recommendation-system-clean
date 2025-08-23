"""
Streamlit Cloud Entry Point for Hybrid Recommendation System

This file serves as the main entry point for Streamlit Cloud deployment.
It properly imports and runs the recommendation system frontend.
"""
import sys
import os
from pathlib import Path

# Add deployment/streamlit directory to Python path
streamlit_dir = Path(__file__).parent / "deployment" / "streamlit"
if streamlit_dir.exists():
    sys.path.insert(0, str(streamlit_dir))

# Import the main streamlit app
try:
    # Import and execute the streamlit app
    import streamlit as st
    
    # Import all the functions and run the app
    exec(open(streamlit_dir / "streamlit_app.py").read())
    
except FileNotFoundError:
    import streamlit as st
    st.error("Could not find the Streamlit app files. Please check the deployment/streamlit directory.")
    st.stop()
except Exception as e:
    import streamlit as st
    st.error(f"Error loading app: {str(e)}")
    import traceback
    st.code(traceback.format_exc())
    st.stop()