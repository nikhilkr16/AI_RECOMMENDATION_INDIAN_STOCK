import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions
import time
import os

# --- 1. THE MONKEY PATCH (Fixing the Error) ---
# We intercept the API call to add automatic retries
original_generate_content = genai.GenerativeModel.generate_content

def safe_generate_content(self, *args, **kwargs):
    # Retry configuration
    max_retries = 5
    base_wait = 2 
    
    for attempt in range(max_retries):
        try:
            return original_generate_content(self, *args, **kwargs)
        except exceptions.ResourceExhausted:
            # If Google blocks us (429), we wait and try again
            time.sleep(base_wait)
            base_wait *= 2 # Exponential backoff (2s, 4s, 8s...)
        except Exception as e:
            raise e # Real errors still crash (as they should)
            
    # If all retries fail, return a safe fallback message instead of crashing app
    class MockResponse:
        text = "⚠️ System is busy. Please try again in 30 seconds."
    return MockResponse()

# Apply the fix
genai.GenerativeModel.generate_content = safe_generate_content

# --- 2. RUN YOUR ORIGINAL APP ---
# Replace 'main.py' with the ACTUAL name of your script
target_file = "AdvanceStockAnalysis.py" 

with open(target_file) as f:
    code = compile(f.read(), target_file, 'exec')
    exec(code, globals())
