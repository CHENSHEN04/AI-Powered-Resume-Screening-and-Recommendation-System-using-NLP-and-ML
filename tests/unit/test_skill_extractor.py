"""
Test Skill Extractor Module
===========================
Unit tests for skill extraction functionality.
"""

import pytest
import shutil
from pathlib import Path
from utils.skill_extractor import SkillExtractor

class TestSkillExtractor:
    """Test the SkillExtractor class."""
    
    @pytest.fixture(scope="class")
    def extractor(self):
        """Create a SkillExtractor instance (loaded once for class)."""
        return SkillExtractor()
    
    def test_initialization(self, extractor):
        """Test that extractor initializes and loads resources."""
        assert extractor.nlp is not None
        assert extractor.standards is not None
        assert len(extractor.skill_db) > 0
    
    def test_normalize_skill(self, extractor):
        """Test skill normalization and alias handling."""
        # Test exact match (no change)
        assert extractor.normalize_skill("Python") == "Python"
        
        # Test alias
        assert extractor.normalize_skill("js") == "JavaScript"
        assert extractor.normalize_skill("react.js") == "React"
        assert extractor.normalize_skill("ml") == "Machine Learning"
    
    def test_extract_skills_keywords(self, extractor):
        """Test extracting skills via keyword matching."""
        text = "I have experience with Python, SQL, and Django."
        result = extractor.extract_skills(text)
        skills = result["all_skills"]
        
        assert "Python" in skills
        assert "SQL" in skills
        assert "Django" in skills
        assert result["count"] >= 3
    
    def test_extract_skills_aliases(self, extractor):
        """Test extracting skills via aliases."""
        text = "Proficient in js and ts."
        result = extractor.extract_skills(text)
        skills = result["all_skills"]
        
        assert "JavaScript" in skills
        assert "TypeScript" in skills
    
    def test_extract_skills_case_insensitive(self, extractor):
        """Test case-insensitive extraction."""
        text = "expert in python and react."
        result = extractor.extract_skills(text)
        skills = result["all_skills"]
        
        assert "Python" in skills
        assert "React" in skills

    def test_extract_skills_no_false_positives(self, extractor):
        """Test avoiding partial matches (e.g. 'java' in 'javascript')."""
        text = "I write JavaScript code."
        result = extractor.extract_skills(text)
        skills = result["all_skills"]
        
        assert "JavaScript" in skills
        # "Java" should NOT be extracted unless explicitly present
        # This depends on the exact regex logic; usually strict bounds prevent partials
        if "Java" in extractor.skill_db:
             assert "Java" not in skills

    def test_map_to_category(self, extractor):
        """Test job category mapping/scoring."""
        # Frontend skills
        frontend_skills = ["HTML", "CSS", "JavaScript", "React"]
        scores = extractor.map_to_category(frontend_skills)
        
        # Should score highest for Frontend Developer
        top_category = list(scores.keys())[0]
        assert top_category == "frontend_developer"
        assert scores["frontend_developer"] > 0.5
        
        # Backend skills
        backend_skills = ["Python", "SQL", "Django", "API Design"]
        scores_backend = extractor.map_to_category(backend_skills)
        
        top_category_backend = list(scores_backend.keys())[0]
        assert top_category_backend == "backend_developer"

    def test_empty_text(self, extractor):
        """Test extraction with empty text."""
        result = extractor.extract_skills("")
        assert result["all_skills"] == []
        assert result["count"] == 0

    def test_normalize_stripping(self, extractor):
         """Test whitespace stripping in normalization."""
         assert extractor.normalize_skill("  Python  ") == "Python"
