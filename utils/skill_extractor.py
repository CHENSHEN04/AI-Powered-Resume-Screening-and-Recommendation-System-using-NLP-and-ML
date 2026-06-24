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

# ==============================================================================
# Skill Extractor Class
# ==============================================================================

class SkillExtractor:
    """
    Extracts skills from resume text using hybrid NER and keyword matching.
    """
    
    def __init__(self):
        """Initialize the extractor by loading resources."""
        self.nlp = self._load_spacy_model()
        self.standards = self._load_market_standards()
        self.skill_db = self._build_skill_db()
        self.aliases = self.standards.get("skill_aliases", {})
        
        # Pre-compile the union database skills regex (sorted by length descending)
        sorted_skills = sorted(list(self.skill_db), key=len, reverse=True)
        if sorted_skills:
            self.db_regex = re.compile(r'\b(' + '|'.join(re.escape(s) for s in sorted_skills) + r')\b', re.IGNORECASE)
        else:
            self.db_regex = None

        # Pre-compile the union alias regex (sorted by length descending)
        sorted_aliases = sorted(list(self.aliases.keys()), key=len, reverse=True)
        if sorted_aliases:
            self.alias_regex = re.compile(r'\b(' + '|'.join(re.escape(a) for a in sorted_aliases) + r')\b', re.IGNORECASE)
        else:
            self.alias_regex = None
        
    @staticmethod
    @st.cache_resource
    def _load_spacy_model():
        """Load spaCy model with caching."""
        try:
            return spacy.load(SPACY_MODEL_NAME)
        except OSError:
            # If model is not found, download it
            from spacy.cli import download
            download(SPACY_MODEL_NAME)
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
            from utils.role_standards_resolver import load_all_known_skills
            skills.update(load_all_known_skills())
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

