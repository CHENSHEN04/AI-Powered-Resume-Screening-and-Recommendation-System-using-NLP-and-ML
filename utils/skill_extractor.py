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
from typing import List, Dict, Set, Tuple
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

        doc = self.nlp(text[:100000]) # Limit text length for performance
        
        found_skills = set()
        
        # 1. NER-based extraction (if custom labels existed, but standard model relies on ORG/PRODUCT)
        # We use NER primarily to identify candidates, then validate against DB
        for ent in doc.ents:
            if ent.label_ in ["ORG", "PRODUCT", "WORK_OF_ART", "LANGUAGE"]:
                candidate = ent.text.lower()
                if candidate in self.skill_db:
                    found_skills.add(self.normalize_skill(ent.text))
        
        # 2. Phrase matching / Keyword scanning (more reliable for specific tech stack)
        # Scan for every known skill in the text
        # This is simple O(N*M) but robust for the limited skill set size (~100-200 skills)
        text_lower = text.lower()
        
        # Create a mapping of lower->original for the skill DB to restore casing
        db_casing_map = {}
        for cat in self.standards.get("job_categories", {}).values():
             for group in ["required_skills", "recommended_skills", "nice_to_have"]:
                 for s in cat.get(group, []):
                     db_casing_map[s.lower()] = s

        for skill_lower in self.skill_db:
            # Use regex to find whole words only to avoid partial usage (e.g. "java" in "javascript")
            # Escape regex special chars in skill name
            escaped_skill = re.escape(skill_lower)
            pattern = r'\b' + escaped_skill + r'\b'
            
            if re.search(pattern, text_lower):
                # Retrieve original casing if available, else usage
                original_case = db_casing_map.get(skill_lower, skill_lower.title())
                found_skills.add(original_case)
                
        # 3. Check for specific aliases in text (e.g. "js" for "JavaScript")
        for alias, real_name in self.aliases.items():
             pattern = r'\b' + re.escape(alias) + r'\b'
             if re.search(pattern, text_lower):
                 found_skills.add(real_name)

        return {
            "all_skills": sorted(list(found_skills)),
            "count": len(found_skills)
        }

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

