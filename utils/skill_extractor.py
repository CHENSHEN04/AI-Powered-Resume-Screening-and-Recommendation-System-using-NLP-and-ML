"""
Skill Extractor Module
======================
Extracts skills from text using a hybrid approach (NER + Keyword Matching).

Implements the skill extraction logic specified in OUTPUT_SPECIFICATION.md section 2.1.
Uses spaCy for NLP processing and a predefined database of skills/keywords.
"""

import spacy
import json
import re
from pathlib import Path
from typing import List, Dict, Set, Tuple, Any
from functools import lru_cache
import streamlit as st

from utils.errors import ErrorCode, AppError, get_error, log_error

# ==============================================================================
# Constants
# ==============================================================================

MARKET_STANDARDS_PATH = Path("data/market_standards.json")
SPACY_MODEL_NAME = "en_core_web_sm"

# Path to local extracted model
LOCAL_MODEL_DIR = Path("models") / "en_core_web_sm_local"
LOCAL_MODEL_PATH = LOCAL_MODEL_DIR / f"{SPACY_MODEL_NAME}-3.7.0" / SPACY_MODEL_NAME / f"{SPACY_MODEL_NAME}-3.7.0"

# Pre-load/download the model at module load time (so it downloads during app startup, not during user inference)
try:
    if LOCAL_MODEL_PATH.exists():
        spacy.load(str(LOCAL_MODEL_PATH))
    else:
        spacy.load(SPACY_MODEL_NAME)
except OSError:
    # Model not found in system packages or local folder, download and extract it in-process
    try:
        import urllib.request
        import tarfile
        
        url = f"https://github.com/explosion/spacy-models/releases/download/{SPACY_MODEL_NAME}-3.7.0/{SPACY_MODEL_NAME}-3.7.0.tar.gz"
        tar_path = LOCAL_MODEL_DIR / f"{SPACY_MODEL_NAME}.tar.gz"
        
        LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        
        # Download the model tarball
        urllib.request.urlretrieve(url, tar_path)
        
        # Extract the model tarball
        with tarfile.open(tar_path, "r:gz") as tar:
            tar.extractall(path=LOCAL_MODEL_DIR)
            
        # Clean up the tarball
        tar_path.unlink()
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Failed to download spaCy model: {e}")

# ==============================================================================
# Skill Extractor Class
# ==============================================================================

# Module-level caches to avoid repeating Supabase queries and heavy regex compiles on every instantiation
_skills_cache = None
_db_regex_cache = None
_alias_regex_cache = None

class SkillExtractor:
    """
    Extracts skills from resume text using hybrid NER and keyword matching.
    """
    
    def __init__(self):
        """Initialize the extractor by loading resources."""
        self.nlp = self._load_spacy_model()
        self.standards = self._load_market_standards()
        self.aliases = self.standards.get("skill_aliases", {})
        
        global _skills_cache, _db_regex_cache, _alias_regex_cache
        
        if _skills_cache is None:
            self.skill_db = self._build_skill_db()
            _skills_cache = self.skill_db
            
            # Pre-compile the union database skills regex (sorted by length descending)
            sorted_skills = sorted(list(self.skill_db), key=len, reverse=True)
            if sorted_skills:
                _db_regex_cache = re.compile(r'\b(' + '|'.join(re.escape(s) for s in sorted_skills) + r')\b', re.IGNORECASE)
            else:
                _db_regex_cache = None

            # Pre-compile the union alias regex (sorted by length descending)
            sorted_aliases = sorted(list(self.aliases.keys()), key=len, reverse=True)
            if sorted_aliases:
                _alias_regex_cache = re.compile(r'\b(' + '|'.join(re.escape(a) for a in sorted_aliases) + r')\b', re.IGNORECASE)
            else:
                _alias_regex_cache = None
        else:
            self.skill_db = _skills_cache
            
        self.db_regex = _db_regex_cache
        self.alias_regex = _alias_regex_cache
        
    @staticmethod
    @st.cache_resource
    def _load_spacy_model():
        """Load spaCy model with caching."""
        try:
            if LOCAL_MODEL_PATH.exists():
                return spacy.load(str(LOCAL_MODEL_PATH))
            return spacy.load(SPACY_MODEL_NAME)
        except OSError:
            # Fallback - download and extract it in-process if not done already
            try:
                if not LOCAL_MODEL_PATH.exists():
                    import urllib.request
                    import tarfile
                    url = f"https://github.com/explosion/spacy-models/releases/download/{SPACY_MODEL_NAME}-3.7.0/{SPACY_MODEL_NAME}-3.7.0.tar.gz"
                    tar_path = LOCAL_MODEL_DIR / f"{SPACY_MODEL_NAME}.tar.gz"
                    LOCAL_MODEL_DIR.mkdir(parents=True, exist_ok=True)
                    urllib.request.urlretrieve(url, tar_path)
                    with tarfile.open(tar_path, "r:gz") as tar:
                        tar.extractall(path=LOCAL_MODEL_DIR)
                    tar_path.unlink()
                return spacy.load(str(LOCAL_MODEL_PATH))
            except Exception:
                return spacy.load(SPACY_MODEL_NAME)
    
    def _load_market_standards(self) -> Dict:
        """Load market standards from JSON file."""
        try:
            if not MARKET_STANDARDS_PATH.exists():
                return {"job_categories": {}, "skill_aliases": {}}
                
            with open(MARKET_STANDARDS_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            log_error(get_error(ErrorCode.INSUFFICIENT_DATA), {"context": "loading market standards"})
            return {"job_categories": {}, "skill_aliases": {}}

    def _build_skill_db(self) -> Set[str]:
        """
        Build a comprehensive set of known skills from market standards.
        Returns a set of normalized (lowercase) skills.
        """
        skills = set()
        categories = self.standards.get("job_categories", {})
        
        for cat in categories.values():
            skills.update(s.lower() for s in cat.get("required_skills", []))
            skills.update(s.lower() for s in cat.get("recommended_skills", []))
            skills.update(s.lower() for s in cat.get("nice_to_have", []))
            
        # Add dynamically resolved common skills and database skills
        try:
            from utils.role_standards_resolver import get_dynamic_common_skills
            skills.update(get_dynamic_common_skills())
        except Exception:
            pass

        return skills

    def normalize_skill(self, skill: str) -> str:
        """
        Normalize skill name using alias handling.
        """
        skill_lower = skill.lower().strip()
        # Check aliases first
        if skill_lower in self.aliases:
            return self.aliases[skill_lower]
        
        # Capitalize appropriately (simple title case for now, 
        # but could rely on the original casing from DB if matched)
        return skill.strip() # For now just return stripped, casing handles by fuzzy match logic usually

    def extract_skills(self, text: str) -> Dict[str, List[str]]:
        """
        Extract skills from text.
        
        Args:
            text: Resume text
            
        Returns:
            Dict containing lists of extracted skills (categorized if possible, 
            currently just 'extracted_skills')
        """
        if not text:
             return {"all_skills": [], "count": 0}

        return self._weighted_extraction(text)

    def _segment_text(self, text: str) -> Dict[str, str]:
        """
        Segment text into logical sections (Education, Work, Projects, Skills).
        """
        sections = {
            "education": "", 
            "work": "", 
            "projects": "", 
            "skills": "", 
            "certifications": "",
            "other": ""
        }
        
        # Simple heuristic regex for headers
        # Note: This is fragile and works best on structured text. 
        # For production, use ML-based segmentation or LayoutLM.
        headers = {
            "education": r"(?i)\b(education|academic background|university|college)\b",
            "work": r"(?i)\b(experience|employment|work history|professional experience)\b",
            "projects": r"(?i)\b(projects|personal projects|hackathons)\b",
            "skills": r"(?i)\b(skills|technical skills|technologies|competencies)\b",
            "certifications": r"(?i)\b(certifications|courses|licenses)\b"
        }
        
        lines = text.split('\n')
        current_section = "other"
        buffer = []
        
        for line in lines:
            line_clean = line.strip()
            if not line_clean: 
                continue
                
            # Check if line is a header (short, matches keywords)
            is_header = False
            if len(line_clean) < 40: # Headers are usually short
                for section, pattern in headers.items():
                    if re.search(pattern, line_clean):
                        # Save buffer to previous section
                        if buffer:
                            sections[current_section] += "\n".join(buffer) + "\n"
                        # Start new section
                        current_section = section
                        buffer = []
                        is_header = True
                        break
            
            if not is_header:
                buffer.append(line)
        
        # Flush last buffer
        if buffer:
            sections[current_section] += "\n".join(buffer)
            
        return sections

    def _weighted_extraction(self, text: str) -> Dict[str, Any]:
        """
        Extract skills with section-based weighting.
        """
        sections = self._segment_text(text)
        found_skills = {} # {name: {count, sources: [], max_weight}}
        
        # Define Section Weights (Education > Skills > Projects > Work for Students)
        section_weights = {
            "education": 1.2,
            "skills": 1.0,
            "projects": 0.9,
            "work": 0.8, # Lower for students as it might be irrelevant internship
            "certifications": 0.8,
            "other": 0.5
        }
        
        db_casing_map = {}
        for cat in self.standards.get("job_categories", {}).values():
             for group in ["required_skills", "recommended_skills", "nice_to_have"]:
                 for s in cat.get(group, []):
                     db_casing_map[s.lower()] = s

        for section_name, section_text in sections.items():
            if not section_text: continue
            
            # Extract from this section
            text_lower = section_text.lower()
            
            # Combine skill_db scanning + Alias scanning
            matches = set()
            
            # 1. DB Scan (one-pass regex)
            if self.db_regex:
                for match in self.db_regex.finditer(text_lower):
                    matches.add(match.group(0).lower())
            
            # 2. Alias Scan (one-pass regex)
            if self.alias_regex:
                for match in self.alias_regex.finditer(text_lower):
                    alias_lower = match.group(0).lower()
                    real_name = self.aliases.get(alias_lower)
                    if real_name:
                        matches.add(real_name.lower())

            # Register matches
            weight = section_weights.get(section_name, 0.5)
            for m in matches:
                # Restore case
                original_name = db_casing_map.get(m, self.normalize_skill(m.title()))
                
                if original_name not in found_skills:
                    found_skills[original_name] = {"count": 0, "sources": set(), "max_weight": 0}
                
                found_skills[original_name]["count"] += 1
                found_skills[original_name]["sources"].add(section_name)
                found_skills[original_name]["max_weight"] = max(found_skills[original_name]["max_weight"], weight)

        # Format output
        formatted_skills = []
        for name, data in found_skills.items():
            formatted_skills.append({
                "name": name,
                "sources": list(data["sources"]),
                "weight_score": data["max_weight"]
            })

        return {
            "all_skills": sorted([s["name"] for s in formatted_skills]),
            "detailed_skills": formatted_skills,
            "count": len(formatted_skills)
        }

    def apply_student_dampening(self, self_rating: int, years_experience: float) -> int:
        """
        Apply 'Student Dampening Factor' to self-reported ratings.
        
        Logic:
        - Students often overrate (Dunning-Kruger).
        - If Exp < 1 year: Max rating is 3 (Intermediate).
        - If Exp < 3 years: Max rating is 4 (Advanced).
        - To get 5 (Expert), need 3+ years or verified output.
        
        Args:
            self_rating: 1-5 scale
            years_experience: Years of experience
            
        Returns:
            Adjusted rating (1-5)
        """
        if years_experience < 1.0:
            return min(self_rating, 3)
        if years_experience < 3.0:
            return min(self_rating, 4)
            
        return self_rating

    def map_to_category(self, extracted_skills: List[str]) -> Dict[str, float]:
        """
        Determine the likely job category based on extracted skills.
        
        Returns:
            Dict of category keys and match scores (0.0 to 1.0)
        """
        extracted_set = {s.lower() for s in extracted_skills}
        scores = {}
        
        categories = self.standards.get("job_categories", {})
        
        for cat_key, cat_data in categories.items():
            required = set(s.lower() for s in cat_data.get("required_skills", []))
            recommended = set(s.lower() for s in cat_data.get("recommended_skills", []))
            
            # Simple scoring: (Matches / Total Required) * 0.7 + (Matches / Total Rec) * 0.3
            # Avoid division by zero
            req_score = 0
            if required:
                req_matches = len(required.intersection(extracted_set))
                req_score = req_matches / len(required)
            
            rec_score = 0
            if recommended:
                rec_matches = len(recommended.intersection(extracted_set))
                rec_score = rec_matches / len(recommended)
                
            final_score = (req_score * 0.7) + (rec_score * 0.3)
            scores[cat_key] = round(final_score, 2)
            
        return dict(sorted(scores.items(), key=lambda item: item[1], reverse=True))

