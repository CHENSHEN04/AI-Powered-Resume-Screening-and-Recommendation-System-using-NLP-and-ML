"""
Gap Analyzer Module
===================
Analyzes skill gaps against market standards and generates personalized recommendations.

Implements the logic specified in OUTPUT_SPECIFICATION.md section 2.1.2 (Hybrid Processing Layer).
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Any
import joblib
import streamlit as st

from utils.errors import ErrorCode, AppError, get_error, log_error

# ==============================================================================
# Constants
# ==============================================================================

MARKET_STANDARDS_PATH = Path("data/market_standards.json")
LEARNING_RESOURCES_PATH = Path("data/learning_resources.json")

# ==============================================================================
# Gap Analyzer Class
# ==============================================================================

class GapAnalyzer:
    """
    Analyzes skill gaps and provides recommendations based on job category.
    """
    
    def __init__(self, db_manager=None):
        """
        Initialize analyzer by loading standards and resources.
        
        Args:
            db_manager: Optional DatabaseManager instance for live data fetching.
        """
        self.db_manager = db_manager
        self.standards = self._load_json(MARKET_STANDARDS_PATH)
        self.resources = self._load_json(LEARNING_RESOURCES_PATH)
        
    def _load_json(self, path: Path) -> Dict:
        """Load JSON data from file."""
        try:
            if not path.exists():
                return {}
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            log_error(get_error(ErrorCode.INSUFFICIENT_DATA), 
                     {"context": f"Loading {path}", "error": str(e)})
            return {}
            
    def analyze_gaps(self, user_skills: List[str], target_role: str) -> Dict[str, Any]:
        """
        Identify missing skills for a target role, prioritizing DB data.
        
        Args:
            user_skills: List of skills extracted from resume
            target_role: Target job category (key or title)
            
        Returns:
            Dictionary containing gaps and recommendations.
        """
        # Normalize user skills for comparison
        user_skills_set = {s.lower() for s in user_skills}
        
        role_data = None

        # Try multiple slug variations to handle spacing/casing differences
        slug_variations = list(dict.fromkeys([
            target_role,
            target_role.lower().replace(" ", "_").replace("/", "_").replace("-", "_"),
            self._normalize_role_name(target_role),
            target_role.lower().strip(),
        ]))

        # 1. Try DB with each slug variation
        if self.db_manager:
            for _slug in slug_variations:
                role_data = self.db_manager.get_market_standards(_slug)
                if role_data:
                    break

        # 2. Fallback to local JSON with each slug variation
        if not role_data:
            for _slug in slug_variations:
                role_data = self.standards.get("job_categories", {}).get(_slug)
                if role_data:
                    break

        # 3. Fallback to session state (for offline/guest custom roles)
        if not role_data:
            for _slug in slug_variations:
                session_key = f"custom_standards_{_slug}"
                if session_key in st.session_state:
                    role_data = st.session_state[session_key]
                    break

        if not role_data:
            import sys
            if "pytest" not in sys.modules:
                try:
                    from utils.ai_assistant import AIRoleStandardGenerator
                    ai_gen = AIRoleStandardGenerator()
                    role_title = target_role.replace("_", " ").title()
                    role_data = ai_gen.generate_standards(role_title)
                    
                    if role_data:
                        if "nice_to_have_skills" in role_data and "nice_to_have" not in role_data:
                            role_data["nice_to_have"] = role_data["nice_to_have_skills"]
                            
                        # Save to DB so other users targeting the same approach have access!
                        if self.db_manager:
                            try:
                                slug_name = target_role.lower().replace(" ", "_").replace("/", "_").replace("-", "_")
                                self.db_manager.save_custom_role(
                                    role_title=role_title,
                                    role_slug=slug_name,
                                    required_skills=role_data.get("required_skills", []),
                                    recommended_skills=role_data.get("recommended_skills", []),
                                    nice_to_have_skills=role_data.get("nice_to_have", [])
                                )
                            except Exception as db_save_err:
                                import logging
                                logging.warning(f"Failed to auto-harvest dynamic job role standards to DB: {db_save_err}")
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to generate dynamic AI standards: {e}")

        if not role_data:
            return {
                "error": "Role not found in standards",
                "role": target_role,
                "missing_required": [],
                "missing_recommended": [],
                "missing_nice_to_have": [],
                "match_percentage": 0.0,
                "recommendations": [
                    f"No skill standards found for '{target_role}'. "
                    "If you just added this role, make sure you saved it with at least "
                    "one Required Skill before running analysis."
                ],
                "learning_paths": {}
            }
            
        required = role_data.get("required_skills", [])
        recommended = role_data.get("recommended_skills", [])
        nice_to_have = role_data.get("nice_to_have", [])
        weights = role_data.get("weights", {"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3})
        
        # Calculate gaps
        missing_required = [s for s in required if s.lower() not in user_skills_set]
        missing_recommended = [s for s in recommended if s.lower() not in user_skills_set]
        missing_nice = [s for s in nice_to_have if s.lower() not in user_skills_set]
        
        # Calculate weighted match percentage
        total_weight = (len(required) * weights["required"] + 
                       len(recommended) * weights["recommended"] +
                       len(nice_to_have) * weights["nice_to_have"])
        
        matched_weight = ((len(required) - len(missing_required)) * weights["required"] +
                         (len(recommended) - len(missing_recommended)) * weights["recommended"] +
                         (len(nice_to_have) - len(missing_nice)) * weights["nice_to_have"])
                         
        match_percentage = (matched_weight / total_weight * 100) if total_weight > 0 else 0.0
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            missing_required, missing_recommended, role_data.get("title", target_role)
        )
        
        # Get Learning Resources (Hybrid DB + JSON)
        learning_paths = self._get_learning_resources(missing_required + missing_recommended)
        
        return {
            "role": role_data.get("title", target_role),
            "missing_required": missing_required,
            "missing_recommended": missing_recommended,
            "missing_nice_to_have": missing_nice,
            "match_percentage": round(match_percentage, 1),
            "recommendations": recommendations,
            "learning_paths": learning_paths
        }
    
    def get_all_known_roles(self) -> list:
        """Return sorted list of all (title, slug) — merges local JSON + DB."""
        known = {}
        for slug, data in self.standards.get("job_categories", {}).items():
            known[slug] = data.get("title", slug.replace("_", " ").title())
        if self.db_manager:
            try:
                for title, slug in self.db_manager.get_all_role_titles():
                    known[slug] = title
            except Exception:
                pass
        return sorted([(title, slug) for slug, title in known.items()], key=lambda x: x[0])

    def _normalize_role_name(self, role_name: str) -> str:
        """Convert role name to json key format (e.g. 'Data Scientist' -> 'data_scientist')."""
        # This mapping might need to be more robust depending on classifier output
        # Classifier output: "Data Scientist", JSON key: "data_scientist"
        if not role_name: 
            return ""
            
        # Try direct key access first
        if role_name in self.standards.get("job_categories", {}):
            return role_name
            
        # Try converting "Title Case" to "snake_case"
        snake_case = role_name.lower().replace(" ", "_")
        if snake_case in self.standards.get("job_categories", {}):
            return snake_case
            
        return snake_case # Default fallback

    def _generate_recommendations(self, missing_req: List[str], missing_rec: List[str], role_title: str) -> List[str]:
        """Generate textual recommendations."""
        recs = []
        
        if missing_req:
            recs.append(f"To qualify for {role_title} roles, focus on learning **{', '.join(missing_req[:3])}** first.")
            
        if missing_rec:
            if not missing_req:
                recs.append(f"To become a strong candidate, add **{', '.join(missing_rec[:3])}** to your skillset.")
            else:
                recs.append(f"Once you cover the basics, consider learning **{', '.join(missing_rec[:2])}** to stand out.")
                
        if not missing_req and not missing_rec:
            recs.append("You have a strong profile for this role! Focus on building projects to demonstrate your expertise.")
            
        return recs

    def _get_learning_resources(self, missing_skills: List[str]) -> Dict[str, List[Dict]]:
        """Get learning resources for missing skills (DB + JSON fallback + Dynamic AI Generator)."""
        paths = {}
        
        # 1. Try DB
        if self.db_manager:
            try:
                db_paths = self.db_manager.get_learning_resources(missing_skills)
                paths.update(db_paths)
            except Exception:
                pass
            
        # 2. Fill gaps from JSON
        # Only fetch for skills not found or simple merge
        all_resources = self.resources.get("resources", {})
        
        for skill in missing_skills:
            if skill not in paths: # Only fallback if completely missing from DB result
                skill_key = skill.lower()
                if skill_key in all_resources:
                    paths[skill] = all_resources[skill_key]
                    
        # 3. Dynamic AI Fallback (Knowledge Harvesting & Collaborative database loop)
        for skill in missing_skills:
            if skill not in paths:
                try:
                    from utils.ai_assistant import _call_ai
                    prompt = f"""You are an expert technical educator. For the skill: "{skill}"
Generate 2 high-quality recommended learning resources (e.g. online courses, official tutorials, or books).
Return ONLY a valid JSON array of objects, where each object has these exact keys:
- "title": "concise title of the course/tutorial"
- "url": "a high-quality valid link (e.g., to Coursera, Udemy, or official documentation like react.dev or python.org)"
- "type": "Course", "Article", "Video", or "Project"
- "difficulty": "Beginner", "Intermediate", or "Advanced"

Return ONLY valid JSON. No markdown block backticks, no extra text."""
                    raw = _call_ai(prompt, max_tokens=512)
                    if raw:
                        clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                        resources = json.loads(clean)
                        if isinstance(resources, list) and len(resources) > 0:
                            paths[skill] = resources
                            # Write back to Supabase! (Collective Intelligence loop!)
                            if self.db_manager:
                                try:
                                    self.db_manager.save_learning_resources(skill, resources)
                                except Exception as db_save_err:
                                    import logging
                                    logging.warning(f"Failed to auto-harvest dynamic learning resources to DB: {db_save_err}")
                except Exception as e:
                    import logging
                    logging.warning(f"Failed to generate dynamic learning resources for skill {skill}: {e}")
                
        return paths
