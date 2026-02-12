import streamlit as st
import pandas as pd
from utils.db_handler import DatabaseManager

st.set_page_config(page_title="Job Coach Admin", layout="wide")

st.title("Admin Dashboard 🛡️")

# Simple Password Protection
if "admin_authenticated" not in st.session_state:
    st.session_state.admin_authenticated = False

def check_password():
    """Returns `True` if the user had the correct password."""
    
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["admin_password"]:
            st.session_state.admin_authenticated = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state.admin_authenticated = False

    if st.session_state.admin_authenticated:
        return True

    st.text_input(
        "Enter Admin Password", type="password", on_change=password_entered, key="password"
    )
    return False

if not check_password():
    st.stop()

# --- Admin Content ---

db = DatabaseManager()

tab1, tab2, tab3 = st.tabs(["System Logs", "Job Categories", "User Stats"])

with tab1:
    st.header("System Logs")
    if st.button("Refresh Logs"):
        try:
            res = db.supabase.table("system_logs").select("*").order("created_at", desc=True).limit(50).execute()
            if res.data:
                df = pd.DataFrame(res.data)
                st.dataframe(df)
            else:
                st.info("No logs found.")
        except Exception as e:
            st.error(f"Error fetching logs: {e}")

with tab2:
    st.header("Job Category Management")
    st.subheader("Pending Approval")
    
    try:
        res = db.supabase.table("job_categories").select("*").eq("status", "pending").execute()
        if res.data:
            for cat in res.data:
                with st.expander(f"{cat['title']} ({cat['slug']})"):
                    st.write(f"Description: {cat.get('description', 'N/A')}")
                    col1, col2 = st.columns([1, 1])
                    if col1.button("Approve", key=f"approve_{cat['id']}"):
                        try:
                            db.supabase.table("job_categories").update({"status": "official"}).eq("id", cat["id"]).execute()
                            st.success(f"Approved {cat['title']}")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))
                            
                    if col2.button("Reject", key=f"reject_{cat['id']}"):
                         try:
                            # Consider delete or status=rejected
                            db.supabase.table("job_categories").delete().eq("id", cat["id"]).execute()
                            st.success(f"Rejected {cat['title']}")
                            st.rerun()
                         except Exception as e:
                            st.error(str(e))
        else:
            st.info("No pending categories to review.")
    except Exception as e:
        st.error(f"Error fetching categories: {e}")

with tab3:
    st.header("Platform Statistics")
    # Quick Pulse
    try:
        user_count = db.supabase.table("profiles").select("id", count="exact").execute().count
        resume_count = db.supabase.table("resumes").select("id", count="exact").execute().count
        
        col1, col2 = st.columns(2)
        col1.metric("Total Users", user_count)
        col2.metric("Total Resumes Analyzed", resume_count)
    except Exception as e:
        st.warning("Could not fetch stats yet.")

