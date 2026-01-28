"""
Growth Tracker Module
=====================
Calculates progress metrics between resume versions.
"""

from typing import Dict, List, Optional
import streamlit as st

class GrowthTracker:
    """
    Tracks skill growth and score improvements.
    """
    
    @staticmethod
    def calculate_growth(current_analysis: Dict, current_skills: List[str], previous_record: Dict) -> Dict:
        """
        Compare current analysis with previous database record.
        
        Args:
            current_analysis: Gap analysis dictionary (contains match_percentage)
            current_skills: List of extracted skill strings
            previous_record: Dictionary from database (contains match_score, skills)
            
        Returns:
            Dictionary with delta metrics.
        """
        if not previous_record:
            return {
                "score_delta": 0,
                "skills_added": [],
                "is_improved": False,
                "first_upload": True
            }
            
        # 1. Score Delta
        current_score = current_analysis.get("match_percentage", 0)
        previous_score = previous_record.get("match_score", 0)
        score_delta = current_score - previous_score
        
        # 2. Skills Added
        curr_set = set(s.lower() for s in current_skills)
        
        prev_skills_data = previous_record.get("skills", [])
        # Handle Supabase response format (list of dicts)
        prev_set = set()
        if prev_skills_data:
            for s in prev_skills_data:
                if isinstance(s, dict) and "skill_name" in s:
                    prev_set.add(s["skill_name"].lower())
                    
        added_skills = list(curr_set - prev_set)
        
        return {
            "score_delta": score_delta,
            "skills_added": [s.title() for s in added_skills],
            "is_improved": score_delta > 0,
            "first_upload": False
        }
    
    @staticmethod
    def render_growth_metrics(growth_data: Dict):
        """Render growth metrics in Streamlit."""
        if growth_data.get("first_upload"):
            st.info("🌟 First analysis! Upload a new version later to track your growth.")
            return

        cols = st.columns(3)
        delta = growth_data["score_delta"]
        
        with cols[0]:
            st.metric(
                "Score Change", 
                f"{delta:+.1f}%", 
                delta,
                delta_color="normal"
            )
            
        with cols[1]:
            added_count = len(growth_data["skills_added"])
            st.metric(
                "Skills Added", 
                added_count,
                f"+{added_count}" if added_count > 0 else "0",
                delta_color="normal"
            )
            
        if growth_data["is_improved"]:
            st.success("🎉 Great job! Your resume has improved.")
            if delta >= 10:
                st.toast("🏆 Achievement Unlocked: Double Digit Growth!", icon="🚀")
            if len(growth_data["skills_added"]) >= 3:
                st.toast("🎓 Achievement Unlocked: Skill Collector!", icon="📚")
