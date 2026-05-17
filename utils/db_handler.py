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
            key = st.secrets["supabase"]["anon_key"]
            return create_client(url, key)
        except Exception as e:
            # log_error skipped here to avoid circular dep or missing logger
            return None

    # --- Authentication Methods ---
    
    def sign_up(self, email: str, password: str, full_name: str):
        """Register a new user."""
        if not self.supabase: return None, "Database not connected"
        try:
            # Pass full_name in metadata so the Trigger can use it
            options = {"data": {"full_name": full_name}}
            res = self.supabase.auth.sign_up({
                "email": email, 
                "password": password, 
                "options": options
            })
            # Profile creation is now handled by the SQL Trigger (on_auth_user_created)
            return res, None
        except Exception as e:
            return None, str(e)

    def sign_in(self, email: str, password: str):
        """Log in an existing user."""
        if not self.supabase: return None, "Database not connected"
        try:
            return self.supabase.auth.sign_in_with_password({"email": email, "password": password}), None
        except Exception as e:
            return None, str(e)

    def sign_out(self):
        """Log out the current user."""
        if self.supabase:
            return self.supabase.auth.sign_out()

    def sign_in_anonymously(self):
        """Create an anonymous session."""
        if not self.supabase: return None, "Database not connected"
        try:
            return self.supabase.auth.sign_in_anonymously(), None
        except Exception as e:
            return None, str(e)

    def merge_anonymous_data(self, anonymous_id: str, new_user_id: str):
        """Reassign data from anonymous user to new authenticated user."""
        if not self.supabase: return False, "Database not connected"
        try:
            # Update resumes table
            self.supabase.table("resumes").update({"user_id": new_user_id}).eq("user_id", anonymous_id).execute()
            return True, None
        except Exception as e:
            return False, str(e)

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
        
        try:
            response = self.supabase.table("resumes").insert(resume_entry).execute()
        
            if response.data:
                resume_id = response.data[0]["id"]
                
                # 2. Insert Skills
                skills_entries = [
                    {"resume_id": resume_id, "skill_name": s["name"], "category": s["category"]}
                    for s in analysis_data.get("skills", [])
                ]
                
                if skills_entries:
                    self.supabase.table("resume_skills").insert(skills_entries).execute()
                    
                return resume_id
        except Exception as e:
             # Just return None for now or log error
            return None
        return None

    def get_user_history(self, user_id: str) -> List[Dict]:
        """Fetch analysis history for a user."""
        if not self.supabase: return []
        
        try:
            return self.supabase.table("resumes")\
                .select("*, resume_skills(*)")\
                .eq("user_id", user_id)\
                .order("created_at", desc=True)\
                .execute().data
        except Exception as e:
            return []

    def get_previous_version(self, user_id: str, filename: str) -> Optional[Dict]:
        """
        Fetch the most recent previous version of a specific file.
        Returns None if this is the first upload.
        """
        if not self.supabase: return None
        
        try:
            # Fetch most recent matching filename
            # Note: This logic assumes we haven't inserted the NEW one yet, 
            # OR we need to handle ignoring the current one if it's already inserted.
            # Best pattern: Call this BEFORE inserting the new one.
            response = self.supabase.table("resumes")\
                .select("*, resume_skills(*)")\
                .eq("user_id", user_id)\
                .eq("filename", filename)\
                .order("created_at", desc=True)\
                .limit(1)\
                .execute()
            
            if response.data:
                return response.data[0]
            return None
        except Exception as e:
            return None

    def get_market_standards(self, role_slug_or_title: str) -> Optional[Dict]:
        """
        Fetch job category details and related skills from the database.
        Returns a dict structure compatible with the GapAnalyzer.
        """
        if not self.supabase: return None
        
        try:
            # Normalize input to slug (simple approach)
            slug = role_slug_or_title.lower().replace(" ", "_").replace("/", "_")
            
            # 1. Fetch Job Category
            # We try exact match on slug first
            cat_res = self.supabase.table("job_categories")\
                .select("*")\
                .eq("slug", slug)\
                .execute()
                
            if not cat_res.data:
                # Fallback: try to find by title ilike
                cat_res = self.supabase.table("job_categories")\
                    .select("*")\
                    .ilike("title", role_slug_or_title)\
                    .execute()
                    
            if not cat_res.data:
                return None
            
            cat_data = cat_res.data[0]
            cat_id = cat_data["id"]
            
            # 2. Fetch Skills
            # Join market_standards -> skills
            # Note: Supabase-py select query with join
            standards_res = self.supabase.table("market_standards")\
                .select("importance_level, skills(name)")\
                .eq("job_category_id", cat_id)\
                .execute()
                
            result = {
                "title": cat_data["title"],
                "weights": cat_data.get("weights", {}),
                "required_skills": [],
                "recommended_skills": [],
                "nice_to_have": []
            }
            
            for item in standards_res.data:
                # item["skills"] is a dict {"name": "..."} because it's a join on FK
                skill_name = item["skills"]["name"] if item.get("skills") else "Unknown"
                importance = item["importance_level"]
                
                if importance == "required":
                    result["required_skills"].append(skill_name)
                elif importance == "recommended":
                    result["recommended_skills"].append(skill_name)
                elif importance == "nice_to_have":
                    result["nice_to_have"].append(skill_name)
            
            return result
        except Exception as e:
            # st.error(f"DB Error fetching standards: {e}")
            return None


    def find_similar_roles(self, role_title: str) -> list:
        """Search DB for roles with similar title/slug. Returns [(title, slug)]."""
        if not self.supabase:
            return []
        try:
            slug_q = role_title.lower().replace(" ", "_").replace("/", "_")
            by_title = self.supabase.table("job_categories")                 .select("title, slug").ilike("title", f"%{role_title}%").limit(5).execute()
            by_slug = self.supabase.table("job_categories")                 .select("title, slug").ilike("slug", f"%{slug_q}%").limit(5).execute()
            seen, results = set(), []
            for row in (by_title.data or []) + (by_slug.data or []):
                if row["slug"] not in seen:
                    seen.add(row["slug"])
                    results.append((row["title"], row["slug"]))
            return results
        except Exception:
            return []

    def get_all_role_titles(self) -> list:
        """Return all (title, slug) pairs from job_categories table."""
        if not self.supabase:
            return []
        try:
            res = self.supabase.table("job_categories").select("title, slug").execute()
            return [(r["title"], r["slug"]) for r in (res.data or [])]
        except Exception:
            return []

    def save_custom_role(self, role_title: str, role_slug: str,
                         required_skills: list, recommended_skills: list,
                         nice_to_have_skills: list) -> tuple:
        """
        Save a user-defined job role to job_categories + market_standards.
        Uses separate SELECT after each write — works with all supabase-py versions.
        Returns (True, None) on success, (False, error_message) on failure.
        """
        if not self.supabase:
            return False, "Database not connected."
        try:
            # Step 1: Check if slug already exists
            existing = self.supabase.table("job_categories")                 .select("id").eq("slug", role_slug).execute()
            if existing.data:
                cat_id = existing.data[0]["id"]
                self.supabase.table("job_categories")                     .update({"title": role_title}).eq("id", cat_id).execute()
            else:
                self.supabase.table("job_categories").insert({
                    "slug": role_slug, "title": role_title,
                    "weights": {"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3}
                }).execute()
                fetch = self.supabase.table("job_categories")                     .select("id").eq("slug", role_slug).execute()
                if not fetch.data:
                    return False, "Role inserted but could not be retrieved. Check DB permissions."
                cat_id = fetch.data[0]["id"]

            # Step 2: Clear old market_standards for clean re-save
            self.supabase.table("market_standards")                 .delete().eq("job_category_id", cat_id).execute()

            # Step 3: Save each skill and link to role
            all_skills = (
                [(s.strip(), "required")     for s in required_skills     if s.strip()] +
                [(s.strip(), "recommended")  for s in recommended_skills  if s.strip()] +
                [(s.strip(), "nice_to_have") for s in nice_to_have_skills if s.strip()]
            )
            for skill_name, importance in all_skills:
                sk = self.supabase.table("skills").select("id").eq("name", skill_name).execute()
                if sk.data:
                    skill_id = sk.data[0]["id"]
                else:
                    self.supabase.table("skills").insert({"name": skill_name}).execute()
                    sk2 = self.supabase.table("skills").select("id").eq("name", skill_name).execute()
                    if not sk2.data:
                        continue
                    skill_id = sk2.data[0]["id"]
                ms = self.supabase.table("market_standards").select("id")                     .eq("job_category_id", cat_id).eq("skill_id", skill_id).execute()
                if not ms.data:
                    self.supabase.table("market_standards").insert({
                        "job_category_id": cat_id, "skill_id": skill_id,
                        "importance_level": importance
                    }).execute()
            return True, None
        except Exception as e:
            return False, str(e)

    def get_learning_resources(self, skill_names: List[str]) -> Dict[str, List[Dict]]:
        """
        Fetch learning resources for a list of skills.
        Returns a dict {skill_name: [resources]}.
        """
        if not self.supabase or not skill_names: return {}
        
        try:
            # We can't efficiently do "WHERE skill_name IN (...)" with join in one go 
            # unless we query learning_resources joined with skills filtered by name list.
            # Supabase-py 'in_' filter: .in_("skills.name", skill_names) might work with !inner join.
            
            # Using !inner to filter by related table
            res = self.supabase.table("learning_resources")\
                .select("title, url, resource_type, difficulty, skills!inner(name)")\
                .in_("skills.name", skill_names)\
                .execute()
                
            output = {}
            for item in res.data:
                skill_name = item["skills"]["name"]
                if skill_name not in output:
                    output[skill_name] = []
                
                output[skill_name].append({
                    "title": item["title"],
                    "url": item["url"],
                    "type": item.get("resource_type", "Resource"),
                    "difficulty": item.get("difficulty", "General")
                })
            return output
        except Exception as e:
            # st.error(f"DB Error fetching resources: {e}")
            return {}

    def log_system_event(self, level: str, message: str, details: Dict[str, Any] = None):
        """
        Log a system event to the database.
        
        Args:
            level: 'INFO', 'WARNING', 'ERROR'
            message: Description of the event
            details: Optional JSON serializable dictionary
        """
        if not self.supabase: return
        
        try:
            entry = {
                "level": level,
                "message": message,
                "details": details or {},
                # "created_at": "now()" -- defaults in DB
            }
            # Fire and forget - don't block main thread if possible, 
            # though supabase-py is sync by default unless using async client.
            self.supabase.table("system_logs").insert(entry).execute()
        except Exception as e:
            # Fallback to console if DB logging fails
            print(f"FAILED TO LOG TO DB: {e}")