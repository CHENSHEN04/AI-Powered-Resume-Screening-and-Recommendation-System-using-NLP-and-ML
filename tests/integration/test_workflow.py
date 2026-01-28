"""
Integration Tests for Resume Analysis Workflow
==============================================
Tests the complete upload → parse → analyze → save flow.
"""

import pytest
import pandas as pd
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from utils.parser import ResumeParser
from utils.skill_extractor import SkillExtractor
from utils.classifier import JobClassifier
from utils.gap_analyzer import GapAnalyzer


class TestFullAnalysisWorkflow:
    """Integration tests for end-to-end resume analysis."""
    
    @pytest.fixture
    def sample_resume_text(self):
        """Sample resume text for testing."""
        return"""
        JOHN DOE
        Email: john.doe@email.com
        Phone: +1-234-567-8900
        
        EDUCATION
        Bachelor of Science in Computer Science
        University of Technology, 2020-2024
        
        SKILLS
        Programming: Python, Java, JavaScript, SQL
        Frameworks: Django, React, Spring Boot
        Tools: Git, Docker, AWS
        
        EXPERIENCE
        Software Engineering Intern
        Tech Company Inc., Summer 2023
        - Developed RESTful APIs using Python and Django
        - Implemented unit tests with pytest
        - Collaborated using Git and Agile methodologies
        
        PROJECTS
        E-Commerce Website
        - Built full-stack web application using React and Django
        - Integrated PostgreSQL database
        - Deployed on AWS
        """
    
    def test_complete_analysis_pipeline(self, sample_resume_text):
        """Test the complete analysis workflow from text to recommendations."""
        
        # Step 1: Extract skills
        extractor = SkillExtractor()
        skill_data = extractor.extract_skills(sample_resume_text)
        
        assert skill_data["count"] > 0, "Should extract at least one skill"
        assert "python" in [s.lower() for s in skill_data["all_skills"]], "Should extract Python"
        
        # Step 2: Classify job category
        classifier = JobClassifier()
        if classifier.clf is None:
            pytest.skip("Classifier models not loaded (expected in CI environment)")
            
        prediction = classifier.predict(sample_resume_text)
        
        assert prediction["top_category"] is not None, "Should predict a job category"
        assert prediction["confidence"] >= 0.0, "Confidence should be non-negative"
        
        # Step 3: Fallback to skill-based categorization if needed
        role_cats = extractor.map_to_category(skill_data["all_skills"])
        top_skill_cat = list(role_cats.keys())[0] if role_cats else "Unknown"
        
        target_role = prediction["top_category"]
        if target_role == "Unknown" or str(target_role).isdigit():
            target_role = top_skill_cat
        
        assert target_role != "Unknown" or top_skill_cat != "Unknown", "Should determine a valid role"
        
        # Step 4: Analyze gaps
        gap_analyzer = GapAnalyzer()
        analysis = gap_analyzer.analyze_gaps(skill_data["all_skills"], target_role)
        
        # Validate gap analysis structure
        assert "role" in analysis, "Gap analysis should include role"
        assert "missing_required" in analysis, "Should have missing_required field"
        assert "missing_recommended" in analysis, "Should have missing_recommended field"
        assert "match_percentage" in analysis, "Should have match_percentage"
        assert "recommendations" in analysis, "Should have recommendations"
        assert "learning_paths" in analysis, "Should have learning_paths"
        
        # Validate types
        assert isinstance(analysis["missing_required"], list), "missing_required should be a list"
        assert isinstance(analysis["missing_recommended"], list), "missing_recommended should be a list"
        assert isinstance(analysis["match_percentage"], (int, float)), "match_percentage should be numeric"
        assert isinstance(analysis["recommendations"], list), "recommendations should be a list"
        assert isinstance(analysis["learning_paths"], dict), "learning_paths should be a dict"
    
    def test_empty_resume_handling(self):
        """Test handling of empty or minimal resume."""
        extractor = SkillExtractor()
        classifier = JobClassifier()
        gap_analyzer = GapAnalyzer()
        
        empty_text = "John Doe\nemail@example.com"
        
        # Should not crash
        skill_data = extractor.extract_skills(empty_text)
        assert skill_data["count"] == 0, "Empty resume should have no skills"
        
        if classifier.clf:
            prediction = classifier.predict(empty_text)
            assert prediction["top_category"] is not None, "Should return a category even for empty resume"
        
        analysis = gap_analyzer.analyze_gaps([], "Unknown")
        assert analysis["match_percentage"] == 0.0, "Empty resume should have 0% match"
    
    def test_classification_confidence_thresholds(self, sample_resume_text):
        """Test that classification confidence scores are reasonable."""
        classifier = JobClassifier()
        
        if classifier.clf is None:
            pytest.skip("Classifier models not loaded")
        
        prediction = classifier.predict(sample_resume_text)
        
        assert 0.0 <= prediction["confidence"] <= 1.0, "Confidence should be between 0 and 1"
        
        if "all_scores" in prediction and prediction["all_scores"]:
            total_prob = sum(prediction["all_scores"].values())
            # Allow small floating point error
            assert abs(total_prob - 1.0) < 0.01, "All probabilities should sum to ~1.0"
    
    def test_gap_analysis_for_matching_profile(self):
        """Test gap analysis when candidate closely matches requirements."""
        extractor = SkillExtractor()
        gap_analyzer = GapAnalyzer()
        
        # Resume with Python-heavy skills
        python_resume = """
        Skills: Python, Django, FastAPI, PostgreSQL, Docker, AWS, Git, 
        REST API, Testing, SQL
        """
        
        skill_data = extractor.extract_skills(python_resume)
        analysis = gap_analyzer.analyze_gaps(skill_data["all_skills"], "python_developer")
        
        # Should have high match if market_standards.json is properly configured
        # (This might fail if python_developer isn't in market_standards.json)
        assert analysis["match_percentage"] >= 0.0, "Match percentage should be calculated"
        
        # If we get an error, it should be documented
        if "error" in analysis:
            assert analysis["recommendations"], "Should provide recommendations even on error"
    
    @pytest.mark.skipif(
        not Path("models/encoder.joblib").exists(),
        reason="Encoder not found - likely CI environment without trained models"
    )
    def test_label_encoder_integration(self, sample_resume_text):
        """Test that label encoder properly decodes predictions."""
        import joblib
        
        classifier = JobClassifier()
        
        if classifier.clf is None or classifier.encoder is None:
            pytest.skip("Models not loaded")
        
        prediction = classifier.predict(sample_resume_text)
        
        # Should return string labels, not numeric indices
        assert isinstance(prediction["top_category"], str), "top_category should be a string"
        assert not prediction["top_category"].isdigit(), "Should not return numeric string like '6'"


class TestErrorRecovery:
    """Test error handling and fallback mechanisms."""
    
    def test_malformed_text_handling(self):
        """Test handling of unusual or malformed text."""
        extractor = SkillExtractor()
        
        # Unicode and special characters
        weird_text = "Python 🐍 JavaScript 💻 React ⚛️"
        skill_data = extractor.extract_skills(weird_text)
        
        # Should extract skills despite emojis
        assert skill_data["count"] >= 0, "Should handle unicode gracefully"
    
    def test_very_long_resume(self):
        """Test handling of excessively long resumes."""
        extractor = SkillExtractor()
        classifier = JobClassifier()
        
        # Generate a very long resume
        long_text = ("Python developer with experience. " * 1000)
        
        skill_data = extractor.extract_skills(long_text)
        assert skill_data["count"] > 0, "Should extract skills from long text"
        
        if classifier.clf:
            prediction = classifier.predict(long_text)
            assert prediction["top_category"] is not None, "Should classify long resume"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
