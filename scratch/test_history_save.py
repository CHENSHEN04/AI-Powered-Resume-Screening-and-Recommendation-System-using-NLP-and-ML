import streamlit as st
import os
import sys

# Add root folder to sys.path so we can import utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock streamlit secrets if needed (Streamlit handles this, but since we are running as a script we can load manually)
import toml
secrets = toml.load(".streamlit/secrets.toml")

# Set environment variables for the supabase client to load
os.environ["SUPABASE_URL"] = secrets["supabase"]["url"]
os.environ["SUPABASE_KEY"] = secrets["supabase"]["anon_key"]

from utils.db_handler import DatabaseManager

db = DatabaseManager()
print(f"Supabase Client initialized: {db.supabase is not None}")

# Try to insert a dummy resume and see if it works or fails
# We'll use a test user or dummy auth if possible, or try direct insert
try:
    print("Testing select from resumes...")
    res = db.supabase.table("resumes").select("*").limit(5).execute()
    print("Select resumes data:", res.data)
except Exception as e:
    print("Select resumes failed:", e)

try:
    print("Testing select from resume_skills...")
    res = db.supabase.table("resume_skills").select("*").limit(5).execute()
    print("Select resume_skills data:", res.data)
except Exception as e:
    print("Select resume_skills failed:", e)
