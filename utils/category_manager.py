from typing import Tuple, Dict, Optional
import streamlit as st
from utils.db_handler import DatabaseManager
from utils.semantic_matcher import SemanticMatcher

class CategoryManager:
    """
    Manages job categories, including custom additions and semantic de-duplication.
    """
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.matcher = SemanticMatcher()

    def check_and_add_category(self, user_input: str) -> Tuple[Optional[Dict], str]:
        """
        Process user input for a job category.
        
        Returns:
            (category_dict, status_message)
            
        status_message can be:
        - "found_exact": "We found an exact match."
        - "found_similar": "Did you mean [Similar Category]?"
        - "created_pending": "Category submitted for review."
        - "error": "Something went wrong."
        """
        if not user_input or not user_input.strip():
            return None, "empty_input"
            
        cleaned_input = user_input.strip()
        slug_input = cleaned_input.lower().replace(" ", "_")
        
        # 1. Check Exact Match
        try:
            res = self.db.supabase.table("job_categories")\
                .select("*")\
                .or_(f"slug.eq.{slug_input},title.ilike.{cleaned_input}")\
                .execute()
                
            if res.data:
                return res.data[0], "found_exact"
        except Exception as e:
            return None, "error"

        # 2. Semantic Search
        # Fetch all categories to compare against
        # Optimization: In production, use pgvector in Supabase for this. 
        # For now, we fetch all (assuming < 1000 categories) and compute locally.
        try:
            all_cats_res = self.db.supabase.table("job_categories").select("slug, title").execute()
            candidates = {item["slug"]: item["title"] for item in all_cats_res.data}
            
            best_slug, score = self.matcher.find_best_match(cleaned_input, candidates)
            
            if best_slug and score > 0.85:
                # Retrieve the full object for the match
                match_res = self.db.supabase.table("job_categories").select("*").eq("slug", best_slug).execute()
                if match_res.data:
                    return match_res.data[0], "found_similar"
                    
        except Exception as e:
             # If semantic search fails, proceed to creation
             pass

        # 3. Create Pending Category
        new_category = {
            "title": cleaned_input,
            "slug": slug_input,
            "status": "pending",
            "description": "User submitted category",
            "weights": {"education": 0.4, "skills": 0.4, "projects": 0.2} # Default weights
        }
        
        try:
            res = self.db.supabase.table("job_categories").insert(new_category).execute()
            if res.data:
                return res.data[0], "created_pending"
        except Exception as e:
            # Handle unique constraint violation just in case race condition
            return None, "error"
            
        return None, "error"
