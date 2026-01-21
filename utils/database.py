"""
Database Utility Module
=======================
Handles connection and queries to Supabase.
"""

import streamlit as st
from supabase import create_client, Client
from typing import Optional, Dict, Any, List
import os

class DatabaseManager:
    """
    Manages Supabase client and database operations.
    """
    
    def __init__(self):
        self.supabase: Optional[Client] = self._init_client()
        
    def _init_client(self) -> Optional[Client]:
        """Initialize Supabase client using secrets."""
        try:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["key"]
            return create_client(url, key)
        except Exception:
            # Fallback for local development or missing secrets
            return None

    def is_connected(self) -> bool:
        return self.supabase is not None

    def create_profile(self, user_id: str, email: str, full_name: str = ""):
        """Create or update user profile."""
        if not self.supabase: return
        
        data = {
            "id": user_id,
            "email": email,
            "full_name": full_name,
            "updated_at": "now()"
        }
        return self.supabase.table("profiles").upsert(data).execute()

    def save_resume_analysis(self, user_id: str, analysis_data: Dict[str, Any]):
        """
        Save resume analysis results to database.
        
        analysis_data expects:
        - filename
        - storage_path
        - parsed_text
        - page_count
        - confidence_score
        - predicted_role
        - match_score
        - skills (list of dicts with name, category)
        """
        if not self.supabase: return
        
        # 1. Insert Resume
        resume_entry = {
            "user_id": user_id,
            "filename": analysis_data["filename"],
            "storage_path": analysis_data["storage_path"],
            "parsed_text": analysis_data["parsed_text"],
            "page_count": analysis_data["page_count"],
            "confidence_score": analysis_data["confidence_score"],
            "predicted_role": analysis_data["predicted_role"],
            "match_score": analysis_data["match_score"]
        }
        
        response = self.supabase.table("resumes").insert(resume_entry).execute()
        
        if response.data:
            resume_id = response.data[0]["id"]
            
            # 2. Insert Skills
            skills_entries = [
                {"resume_id": resume_id, "skill_name": s["name"], "category": s["category"]}
                for s in analysis_data.get("skills", [])
            ]
            
            if skills_entries:
                self.supabase.table("skills").insert(skills_entries).execute()
                
            return resume_id
        return None

    def get_user_history(self, user_id: str) -> List[Dict]:
        """Fetch analysis history for a user."""
        if not self.supabase: return []
        
        return self.supabase.table("resumes")\
            .select("*, skills(*)")\
            .eq("user_id", user_id)\
            .order("created_at", desc=True)\
            .execute().data
