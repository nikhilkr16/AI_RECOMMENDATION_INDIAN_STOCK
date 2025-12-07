import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions
import time

# --- 1. THE FIX (Rate Limit Handler) ---
# We intercept the API call to add automatic retries
original_generate_content = genai.GenerativeModel.generate_content

def safe_generate_content(self, *args, **kwargs):
    max_retries = 5
    base_wait = 2 
    
    for attempt in range(max_retries):
        try:
            # Try to run the original function
            return original_generate_content(self, *args, **kwargs)
        except exceptions.ResourceExhausted:
            # If Google blocks us (429), we wait and try again
            time.sleep(base_wait)
            base_wait *= 2 # Wait longer (2s -> 4s -> 8s)
        except Exception as e:
            raise e 
            
    # If all retries fail, return a fake safe response so the app doesn't crash
    class MockResponse:
        text = "⚠️ Server is busy. Please try again in 10 seconds."
    return MockResponse()

# Apply the fix
genai.GenerativeModel.generate_content = safe_generate_content

# --- 2. RUN YOUR ORIGINAL APP ---
# IMPORTANT: This filename must match your original file EXACTLY.
# If your main file is named "app.py" or "churn.py", change "main.py" below.
target_file = "AdvanceStockAnalysis.py" 

with open(target_file) as f:
    code = compile(f.read(), target_file, 'exec')
    exec(code, globals())
