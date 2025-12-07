import streamlit as st
import google.generativeai as genai
import time

# 1. SETUP: Use the STABLE model (1.5 Flash), not the experimental one
# Experimental models (2.0) have much stricter limits.
MODEL_NAME = "gemini-1.5-flash"

# 2. CONFIGURE API
# Put your key in Streamlit Secrets (Best Practice) or directly here
api_key = st.secrets.get("GEMINI_API_KEY", "AIzaSyBXtYVWb-_2TqkZOAsUfu_I2RPV8ARGj10")
genai.configure(api_key=api_key)

# 3. THE FIX: CACHED MODEL LOADING
# @st.cache_resource ensures we only connect to Google ONCE per session
@st.cache_resource
def get_model():
    return genai.GenerativeModel(MODEL_NAME)

model = get_model()

# 4. THE FIX: CACHED RESPONSE FUNCTION
# This prevents calling the API again if the prompt hasn't changed
@st.cache_data(show_spinner=False)
def get_gemini_response(prompt_text):
    time.sleep(1) 
    try:
        response = model.generate_content(prompt_text)
        return response.text
    except Exception as e:
        return f"Error: {e}"

# 5. YOUR APP UI
st.title("Churn Prediction Assistant")
user_input = st.text_input("Ask about a customer:")

if st.button("Analyze"):
    if user_input:
        with st.spinner("Analyzing..."):
            # Call the CACHED function
            result = get_gemini_response(user_input)
            st.write(result)
