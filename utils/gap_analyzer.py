"""
Gap Analyzer Module
===================
Analyzes skill gaps against market standards and generates personalized recommendations.

Implements the logic specified in OUTPUT_SPECIFICATION.md section 2.1.2 (Hybrid Processing Layer).
"""

import json
from pathlib import Path
from typing import Dict, List, Set, Any, Optional
import joblib
import streamlit as st

from utils.errors import ErrorCode, AppError, get_error, log_error
from utils.role_standards_resolver import (
    is_standards_usable,
    normalize_role_slug,
    normalize_standards,
    resolve_role_standards,
    _is_noise,
)

# ==============================================================================
# Constants
# ==============================================================================

MARKET_STANDARDS_PATH = Path("data/market_standards.json")
LEARNING_RESOURCES_PATH = Path("data/learning_resources.json")

# ==============================================================================
# Gap Analyzer Class
# ==============================================================================

def deduplicate_language_skills(skills: List[str]) -> List[str]:
    lang_groups = [
        {"chinese", "mandarin", "mandarin speaker"},
        {"english", "english speaker"},
        {"malay", "malay speaker", "bahasa melayu"},
        {"tamil", "tamil speaker"},
        {"cantonese", "cantonese speaker"}
    ]
    to_remove = set()
    skills_lower = [s.lower().strip() for s in skills]
    
    for group in lang_groups:
        present_indices = [i for i, s in enumerate(skills_lower) if s in group]
        if len(present_indices) > 1:
            # Find the longest one to keep
            longest_idx = max(present_indices, key=lambda i: len(skills[i]))
            for idx in present_indices:
                if idx != longest_idx:
                    to_remove.add(skills[idx])
                    
    return [s for s in skills if s not in to_remove]


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
            
    def analyze_gaps(self, user_skills: List[str], target_role: str, jd_text: str = "", experience_level: str = "Internship") -> Dict[str, Any]:
        """
        Identify missing skills for a target role, prioritizing DB data.
        
        Args:
            user_skills: List of skills extracted from resume
            target_role: Target job category (key or title)
            jd_text: Optional job description text
            experience_level: User's experience level ("Beginner", "Some Projects", "Internship", "1+ Years")
            
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
        db_role_found = False
        db_role_slug = None
        db_role_title = None

        if self.db_manager:
            for _slug in slug_variations:
                try:
                    exists_res = self.db_manager.supabase.table("job_categories").select("id, title, slug").eq("slug", _slug).execute()
                    if exists_res.data:
                        db_role_found = True
                        db_role_slug = _slug
                        db_role_title = exists_res.data[0]["title"]
                        role_data = self.db_manager.get_market_standards(_slug)
                        if is_standards_usable(role_data):
                            break
                        role_data = None
                except Exception:
                    pass

        # Auto-resolve empty DB role
        if db_role_found and not role_data:
            role_title = db_role_title or target_role.replace("_", " ").title()
            resolved, resolve_err = resolve_role_standards(role_title, jd_text=jd_text)
            if resolved and is_standards_usable(resolved):
                if self.db_manager:
                    try:
                        self.db_manager.save_custom_role(
                            role_title=role_title,
                            role_slug=db_role_slug,
                            required_skills=resolved.get("required_skills", []),
                            recommended_skills=resolved.get("recommended_skills", []),
                            nice_to_have_skills=resolved.get("nice_to_have", resolved.get("nice_to_have_skills", [])),
                            advanced_skills=resolved.get("advanced_skills", []),
                            salary_ranges=resolved.get("salary_ranges", {}),
                            learning_resources=resolved.get("learning_resources", {}),
                            skill_difficulties=resolved.get("skill_difficulties", {})
                        )
                    except Exception as db_save_err:
                        import logging
                        logging.warning(f"Failed to auto-resolve and save empty DB role standards: {db_save_err}")
                role_data = resolved

        # 2. Fallback to local JSON with each slug variation
        if not role_data:
            for _slug in slug_variations:
                role_data = self.standards.get("job_categories", {}).get(_slug)
                if is_standards_usable(role_data):
                    break
                role_data = None

        # 3. Fallback to session state (for offline/guest custom roles)
        if not role_data:
            for _slug in slug_variations:
                session_key = f"custom_standards_{_slug}"
                if session_key in st.session_state:
                    role_data = st.session_state[session_key]
                    if not is_standards_usable(role_data):
                        role_data = None
                        continue
                    break

        if not role_data:
            role_title = target_role.replace("_", " ").title()
            role_data, resolve_err = resolve_role_standards(role_title, jd_text=jd_text)
            if role_data and is_standards_usable(role_data):
                slug_name = normalize_role_slug(target_role)
                if self.db_manager:
                    try:
                        success, err = self.db_manager.save_custom_role(
                            role_title=role_title,
                            role_slug=slug_name,
                            required_skills=role_data.get("required_skills", []),
                            recommended_skills=role_data.get("recommended_skills", []),
                            nice_to_have_skills=role_data.get("nice_to_have", role_data.get("nice_to_have_skills", [])),
                            advanced_skills=role_data.get("advanced_skills", []),
                            salary_ranges=role_data.get("salary_ranges", {}),
                            learning_resources=role_data.get("learning_resources", {}),
                            skill_difficulties=role_data.get("skill_difficulties", {})
                        )
                        if not success:
                            import logging
                            logging.warning(f"Failed to save resolved role standards to DB: {err}")
                    except Exception as db_save_err:
                        import logging
                        logging.warning(f"Failed to auto-harvest dynamic job role standards to DB: {db_save_err}")
                st.session_state[f"custom_standards_{slug_name}"] = role_data
            else:
                role_data = None

        if not role_data:
            return {
                "error": "Role not found in standards",
                "role": target_role,
                "missing_required": [],
                "missing_recommended": [],
                "missing_nice_to_have": [],
                "missing_advanced": [],
                "match_percentage": 0.0,
                "recommendations": [
                    f"No skill standards found for '{target_role}'. "
                    "If you just added this role, make sure you saved it with at least "
                    "one Required Skill before running analysis."
                ],
                "learning_paths": {}
            }
            
        role_data = normalize_standards(role_data, target_role, role_data.get("_source", "standards"))
        
        required = [s for s in role_data.get("required_skills", []) if not _is_noise(s)]
        recommended = [s for s in role_data.get("recommended_skills", []) if not _is_noise(s)]
        nice_to_have = [s for s in role_data.get("nice_to_have", []) if not _is_noise(s)]
        advanced = [s for s in role_data.get("advanced_skills", []) if not _is_noise(s)]
        
        # Deduplicate redundant language variations across required, recommended, nice_to_have, and advanced
        all_req_skills = required + recommended + nice_to_have + advanced
        deduped_all = deduplicate_language_skills(all_req_skills)
        deduped_set = set(s.lower() for s in deduped_all)
        
        required = [s for s in required if s.lower() in deduped_set]
        recommended = [s for s in recommended if s.lower() in deduped_set]
        nice_to_have = [s for s in nice_to_have if s.lower() in deduped_set]
        advanced = [s for s in advanced if s.lower() in deduped_set]
        
        weights = role_data.get("weights", {"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3})
        weights_advanced = weights.get("advanced", 0.5)
        
        # Calculate gaps using smart skill matching
        missing_required = [s for s in required if not self._is_skill_matched(s, user_skills_set)]
        missing_recommended = [s for s in recommended if not self._is_skill_matched(s, user_skills_set)]
        missing_nice = [s for s in nice_to_have if not self._is_skill_matched(s, user_skills_set)]
        missing_advanced = [s for s in advanced if not self._is_skill_matched(s, user_skills_set)]
        
        # Calculate extra skills (bonus skills the candidate has that are not required/recommended/nice-to-have/advanced)
        target_skills_set = {s.lower() for s in required + recommended + nice_to_have + advanced}
        extra_skills = [s for s in user_skills if not self._is_skill_matched(s, target_skills_set)]
        
        is_intern_or_beginner = experience_level in ["Beginner", "Some Projects", "Internship"]
        
        # Calculate weighted match percentage
        if is_intern_or_beginner:
            # For interns, ignore advanced skills in weights
            total_weight = (len(required) * weights.get("required", 1.0) + 
                           len(recommended) * weights.get("recommended", 0.6) +
                           len(nice_to_have) * weights.get("nice_to_have", 0.3))
            
            matched_weight = ((len(required) - len(missing_required)) * weights.get("required", 1.0) +
                             (len(recommended) - len(missing_recommended)) * weights.get("recommended", 0.6) +
                             (len(nice_to_have) - len(missing_nice)) * weights.get("nice_to_have", 0.3))
        else:
            # For 1+ Years, include advanced skills
            total_weight = (len(required) * weights.get("required", 1.0) + 
                           len(recommended) * weights.get("recommended", 0.6) +
                           len(nice_to_have) * weights.get("nice_to_have", 0.3) +
                           len(advanced) * weights_advanced)
            
            matched_weight = ((len(required) - len(missing_required)) * weights.get("required", 1.0) +
                             (len(recommended) - len(missing_recommended)) * weights.get("recommended", 0.6) +
                             (len(nice_to_have) - len(missing_nice)) * weights.get("nice_to_have", 0.3) +
                             (len(advanced) - len(missing_advanced)) * weights_advanced)
                          
        match_percentage = (matched_weight / total_weight * 100) if total_weight > 0 else 0.0
        
        # Apply transferable skill bonus (+1.0% per extra skill, capped at 10.0%)
        if extra_skills and total_weight > 0:
            bonus = min(len(extra_skills) * 1.0, 10.0)
            match_percentage = min(match_percentage + bonus, 100.0)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            missing_required, missing_recommended, role_data.get("title", target_role)
        )
        
        # Get Learning Resources (Hybrid DB + JSON)
        learning_paths = self._get_learning_resources(missing_required + missing_recommended + missing_advanced)
        
        return {
            "role": role_data.get("title", target_role),
            "required_skills": required,
            "recommended_skills": recommended,
            "nice_to_have": nice_to_have,
            "advanced_skills": advanced,
            "missing_required": missing_required,
            "missing_recommended": missing_recommended,
            "missing_nice_to_have": missing_nice,
            "missing_advanced": missing_advanced,
            "extra_skills": extra_skills,
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
                # DB rows can hold stale/hallucinated links saved before link
                # verification existed (or from a previous bad AI generation).
                # Re-verify at read time so a fix here also heals old bad data,
                # instead of silently serving 404s forever.
                for skill_name, resources in db_paths.items():
                    db_paths[skill_name] = self._verify_resource_links(skill_name, resources)
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
                    
        # 3. Dynamic AI Fallback (Knowledge Harvesting & Collaborative database batching)
        missing_unresolved = [skill for skill in missing_skills if skill not in paths]
        if missing_unresolved:
            try:
                from utils.ai_assistant import _call_ai
                skills_str = ", ".join(f'"{s}"' for s in missing_unresolved)
                prompt = f"""You are an expert technical educator. For the following skills: [{skills_str}]
Generate exactly 2 high-quality recommended learning resources (e.g. online courses, official tutorials, or books) for each skill.
Return ONLY a valid JSON object mapping each skill name to its array of resource objects. Each resource object must have these exact keys:
- "title": "concise title of the course/tutorial"
- "url": "a real, currently-existing URL you are highly confident resolves correctly. Strongly prefer stable landing pages you are certain exist — official documentation home/tutorial pages (e.g. https://react.dev/learn, https://docs.python.org/3/tutorial/), a platform's general course-catalog/search page (e.g. https://www.coursera.org/search?query=..., https://www.udemy.com/courses/search/?q=...), or a well-known site's homepage. Do NOT invent or guess a specific deep-linked course slug/ID (e.g. a specific DataCamp/Udemy/Coursera course URL) unless you are certain it exists — a guessed URL that 404s is worse than a general page."
- "type": "Course", "Article", "Video", or "Project"
- "difficulty": "Beginner", "Intermediate", or "Advanced"

Example output structure:
{{
  "SkillName": [
    {{
      "title": "Course Name",
      "url": "https://example.com",
      "type": "Course",
      "difficulty": "Beginner"
    }},
    {{
      "title": "Tutorial Name",
      "url": "https://example.com",
      "type": "Video",
      "difficulty": "Intermediate"
    }}
  ]
}}

Return ONLY valid JSON. No markdown block backticks, no extra text."""
                raw = _call_ai(prompt, max_tokens=2048)
                if raw:
                    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    parsed = json.loads(clean)
                    if isinstance(parsed, dict):
                        skill_map = {s.lower(): s for s in missing_unresolved}
                        for k, v in parsed.items():
                            k_lower = k.lower()
                            if k_lower in skill_map and isinstance(v, list) and len(v) > 0:
                                mapped_skill = skill_map[k_lower]
                                # AI-suggested URLs can be hallucinated / lead to 404s
                                # (e.g. guessed DataCamp course slugs). Verify each link
                                # actually resolves before showing it to the user, and
                                # substitute a guaranteed-valid fallback link otherwise.
                                verified = self._verify_resource_links(mapped_skill, v)
                                paths[mapped_skill] = verified
                                # Write back to Supabase!
                                if self.db_manager:
                                    try:
                                        self.db_manager.save_learning_resources(mapped_skill, verified)
                                    except Exception as db_save_err:
                                        import logging
                                        logging.warning(f"Failed to auto-harvest dynamic learning resources to DB: {db_save_err}")
            except Exception as e:
                import logging
                logging.warning(f"Failed to generate dynamic learning resources in batch: {e}")
                
        return paths

    def _url_is_reachable(self, url: str) -> bool:
        """Quick liveness check for a resource URL (used to catch AI-hallucinated links)."""
        if not url or not url.startswith(("http://", "https://")):
            return False
        try:
            import httpx
            headers = {"User-Agent": "Mozilla/5.0 (DeepCareerCoach LinkChecker)"}
            with httpx.Client(follow_redirects=True, timeout=4.0, headers=headers) as client:
                resp = client.head(url)
                if resp.status_code in (405, 403, 501):
                    # Some sites reject HEAD requests; retry with a cheap GET.
                    resp = client.get(url)
                return resp.status_code < 400
        except Exception:
            return False

    def _verify_resource_links(self, skill: str, resources: List[Dict]) -> List[Dict]:
        """
        Filter out any AI-suggested resource whose URL doesn't actually resolve
        (broken/hallucinated link), so users never land on a 404 page. If every
        suggested link fails, fall back to a guaranteed-valid search link.
        """
        live = []
        for r in resources:
            url = r.get("url") if isinstance(r, dict) else None
            if self._url_is_reachable(url):
                live.append(r)
        if live:
            return live

        import urllib.parse
        query = urllib.parse.quote(f"{skill} tutorial")
        return [{
            "title": f"Search for '{skill}' learning resources",
            "url": f"https://www.google.com/search?q={query}",
            "type": "Search",
            "difficulty": "Beginner",
        }]

    def _get_education_level(self, skill: str) -> Optional[int]:
        """
        Extract the highest educational level from a skill string using whole word matching.
        """
        import re
        s = skill.lower().strip()
        s = s.replace("b.s.", "bs").replace("b.a.", "ba").replace("m.s.", "ms").replace("m.a.", "ma").replace("ph.d.", "phd")
        s = s.replace("b.sc.", "bsc").replace("m.sc.", "msc")
        
        words = re.findall(r"\b[a-z0-9]+\b", s)
        
        edu_hierarchy = {
            "diploma": 1,
            "degree": 2, "bachelor": 2, "bsc": 2, "ba": 2, "bs": 2, "undergraduate": 2,
            "master": 3, "msc": 3, "ma": 3, "ms": 3, "mba": 3, "postgraduate": 3,
            "phd": 4, "doctor": 4, "doctorate": 4
        }
        
        max_level = None
        for word in words:
            if word in edu_hierarchy:
                level = edu_hierarchy[word]
                if max_level is None or level > max_level:
                    max_level = level
        return max_level

    def _is_skill_matched(self, target_skill: str, user_skills_set: Set[str]) -> bool:
        """
        Check if a target skill is matched in the user's extracted skills set.
        Handles abbreviations (e.g., MS Office -> Microsoft Office), equivalent groups 
        (e.g., Chinese -> Mandarin, SAP -> ERP), stemming/substrings (e.g., Analysis -> Analytical),
        and educational hierarchy (Degree satisfies Diploma).
        """
        ts_lower = target_skill.lower().strip()
        
        # 1. Direct match
        if ts_lower in user_skills_set:
            return True
            
        # 2. Educational Hierarchy Match (Degree satisfies Diploma)
        target_edu_level = self._get_education_level(ts_lower)
        if target_edu_level is not None:
            for u_skill in user_skills_set:
                u_level = self._get_education_level(u_skill)
                if u_level is not None and u_level >= target_edu_level:
                    return True
                        
        # 3. Semantic / Equivalent / Alias groups (asymmetric mapping)
        office_suite = {
            "ms office", "microsoft office", "office", "ms word", "word", "ms excel", "excel", 
            "powerpoint", "microsoft excel", "microsoft word", "microsoft powerpoint", "ms powerpoint"
        }
        excel_group = {"excel", "ms excel", "microsoft excel", "ms office", "microsoft office", "office"}
        word_group = {"word", "ms word", "microsoft word", "ms office", "microsoft office", "office"}
        powerpoint_group = {"powerpoint", "ms powerpoint", "microsoft powerpoint", "ms office", "microsoft office", "office"}
        
        erp_suite = {"erp", "enterprise resource planning", "sap", "oracle"}
        sap_group = {"sap", "erp", "enterprise resource planning"}
        oracle_group = {"oracle", "erp", "enterprise resource planning"}
        
        chinese_group = {"chinese", "mandarin", "mandarin speaker"}
        analysis_group = {"analysis", "analytical", "analytics", "analyze", "data analytics"}
        
        asymmetric_groups = {
            "ms office": office_suite,
            "microsoft office": office_suite,
            "office": office_suite,
            "excel": excel_group,
            "ms excel": excel_group,
            "microsoft excel": excel_group,
            "word": word_group,
            "ms word": word_group,
            "microsoft word": word_group,
            "powerpoint": powerpoint_group,
            "ms powerpoint": powerpoint_group,
            "microsoft powerpoint": powerpoint_group,
            
            "erp": erp_suite,
            "enterprise resource planning": erp_suite,
            "sap": sap_group,
            "oracle": oracle_group,
            
            "chinese": chinese_group,
            "mandarin": chinese_group,
            "mandarin speaker": chinese_group,
            
            "analysis": analysis_group,
            "analytical": analysis_group,
            "analytics": analysis_group,
            "analyze": analysis_group,
            "data analytics": analysis_group,
        }
        
        if ts_lower in asymmetric_groups:
            allowed_user_skills = asymmetric_groups[ts_lower]
            if any(item in user_skills_set for item in allowed_user_skills):
                return True
                    
        # 4. Suffix / Stemming / Partial matches (e.g. "analytical skills" matches "analysis")
        false_positives = {
            ("java", "javascript"),
            ("word", "wordpress"),
            ("rust", "trust"),
            ("git", "github"),
            ("sql", "nosql"),
            ("sql", "mysql"),
            ("sql", "postgresql"),
            ("net", "internet")
        }
        for u_skill in user_skills_set:
            if len(ts_lower) >= 4 and len(u_skill) >= 4:
                if ts_lower in u_skill or u_skill in ts_lower:
                    if (ts_lower, u_skill) not in false_positives and (u_skill, ts_lower) not in false_positives:
                        return True
                # Stemming check
                if ts_lower.startswith("analyt") and u_skill.startswith("analyt"):
                    return True
                if ts_lower.startswith("communicat") and u_skill.startswith("communicat"):
                    return True
                if ts_lower.startswith("program") and u_skill.startswith("program"):
                    return True
                    
        return False