import streamlit as st
import os
import sys

# Add project root to python path
sys.path.insert(0, os.getcwd())

# Mock st.secrets so DatabaseManager can initialize
from unittest.mock import MagicMock
import toml

secrets = toml.load(".streamlit/secrets.toml")
st.secrets = secrets

from utils.db_handler import DatabaseManager

db = DatabaseManager()
print(f"Supabase client initialized: {db.supabase is not None}")

# Let's try signing in or creating a user to check RLS
email = "test_user_antigravity@email.com"
password = "TestPassword123!"

# Try to sign in or sign up
res, err = db.sign_in(email, password)
if err:
    print(f"Sign in failed: {err}. Trying to sign up...")
    res, err = db.sign_up(email, password, "Test User Antigravity")
    if err:
        print(f"Sign up also failed: {err}")
        sys.exit(1)
    else:
        print("Sign up successful!")
        user = res.user
else:
    print("Sign in successful!")
    user = res.user

print(f"Logged in user ID: {user.id}")

# Let's sync auth session
db.sync_auth_session()

# Now try to save a mock resume analysis
analysis_data = {
    "filename": "diagnostic_test.pdf",
    "storage_path": f"resumes/{user.id}/diagnostic_test.pdf",
    "parsed_text": "This is parsed text from a test resume.",
    "page_count": 2,
    "confidence_score": 0.95,
    "predicted_role": "data_science",
    "match_score": 88.5,
    "skills": [{"name": "Python", "category": "extracted"}, {"name": "SQL", "category": "extracted"}]
}

print("Attempting to save resume analysis...")
try:
    # Explicitly run the insert to see the exception
    resume_entry = {
        "user_id": user.id,
        "filename": analysis_data["filename"],
        "storage_path": analysis_data["storage_path"],
        "parsed_text": analysis_data["parsed_text"],
        "page_count": analysis_data["page_count"],
        "confidence_score": analysis_data["confidence_score"],
        "predicted_role": analysis_data["predicted_role"],
        "match_score": analysis_data["match_score"]
    }
    
    response = db.supabase.table("resumes").insert(resume_entry).execute()
    print("Insert response:", response)
    
    if response.data:
        print(f"SUCCESS! Created resume with ID: {response.data[0]['id']}")
    else:
        print("Insert succeeded but returned no data.")
except Exception as e:
    print("ERROR DURING INSERT:")
    import traceback
    traceback.print_exc()
