"""
Test Gap Analyzer Module
========================
Unit tests for gap analysis and recommendation functionality.
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
from utils.gap_analyzer import GapAnalyzer

# Sample mock data
MOCK_MARKET_STANDARDS = {
    "job_categories": {
        "frontend_developer": {
            "title": "Frontend Developer",
            "required_skills": ["HTML", "CSS", "JavaScript"],
            "recommended_skills": ["React", "TypeScript"],
            "nice_to_have": ["Figma"],
            "weights": {"required": 1.0, "recommended": 0.5, "nice_to_have": 0.2}
        }
    }
}

MOCK_LEARNING_RESOURCES = {
    "resources": {
        "react": [
            {"title": "React Docs", "url": "https://react.dev", "type": "Documentation"}
        ],
        "typescript": [
            {"title": "TS Handbook", "url": "https://ts.org", "type": "Guide"}
        ]
    }
}

class TestGapAnalyzer:
    """Test the GapAnalyzer class."""
    
    @patch('utils.gap_analyzer.json.load')
    @patch('pathlib.Path.exists')
    def test_initialization(self, mock_exists, mock_json_load):
        """Test initialization loads data correctly."""
        mock_exists.return_value = True
        mock_json_load.side_effect = [MOCK_MARKET_STANDARDS, MOCK_LEARNING_RESOURCES]
        
        analyzer = GapAnalyzer()
        assert analyzer.standards == MOCK_MARKET_STANDARDS
        assert analyzer.resources == MOCK_LEARNING_RESOURCES

    @patch('utils.gap_analyzer.json.load')
    @patch('pathlib.Path.exists')
    def test_analyze_gaps_exact_match(self, mock_exists, mock_json_load):
        """Test analysis with a perfect match."""
        mock_exists.return_value = True
        mock_json_load.side_effect = [MOCK_MARKET_STANDARDS, MOCK_LEARNING_RESOURCES]
        
        analyzer = GapAnalyzer()
        
        user_skills = ["HTML", "CSS", "JavaScript", "React", "TypeScript", "Figma"]
        result = analyzer.analyze_gaps(user_skills, "frontend_developer")
        
        assert result["match_percentage"] == 100.0
        assert not result["missing_required"]
        assert not result["missing_recommended"]
        assert "recommendations" in result
        assert "strong profile" in result["recommendations"][0]

    @patch('utils.gap_analyzer.json.load')
    @patch('pathlib.Path.exists')
    def test_analyze_gaps_missing_skills(self, mock_exists, mock_json_load):
        """Test analysis with missing skills."""
        mock_exists.return_value = True
        mock_json_load.side_effect = [MOCK_MARKET_STANDARDS, MOCK_LEARNING_RESOURCES]
        
        analyzer = GapAnalyzer()
        
        # Missing JavaScript (Required) and TypeScript (Recommended)
        user_skills = ["HTML", "CSS", "React"]
        result = analyzer.analyze_gaps(user_skills, "Frontend Developer")
        
        assert "JavaScript" in result["missing_required"]
        assert "TypeScript" in result["missing_recommended"]
        assert result["match_percentage"] < 100.0
        assert result["learning_paths"] is not None
        # Should have resources for TypeScript (missing recommended) but maybe not JS (if not in mock resources)
        # In our mock, TypeScript is present
        assert "TypeScript" in result["learning_paths"]

    @patch('utils.gap_analyzer.json.load')
    @patch('pathlib.Path.exists')
    def test_normalize_role_name_cases(self, mock_exists, mock_json_load):
        """Test role name normalization."""
        mock_exists.return_value = True
        mock_json_load.side_effect = [MOCK_MARKET_STANDARDS, MOCK_LEARNING_RESOURCES]
        
        analyzer = GapAnalyzer()
        
        assert analyzer._normalize_role_name("Frontend Developer") == "frontend_developer"
        assert analyzer._normalize_role_name("frontend_developer") == "frontend_developer"
        assert analyzer._normalize_role_name("Data Scientist") == "data_scientist" # Default fallback snake_case

    @patch('utils.gap_analyzer.json.load')
    @patch('pathlib.Path.exists')
    def test_invalid_role(self, mock_exists, mock_json_load):
        """Test analysis with unknown role."""
        mock_exists.return_value = True
        mock_json_load.side_effect = [MOCK_MARKET_STANDARDS, MOCK_LEARNING_RESOURCES]
        
        analyzer = GapAnalyzer()
        result = analyzer.analyze_gaps(["Python"], "Astronaut")
        
        assert result["error"] == "Role not found in standards"
        assert result["match_percentage"] == 0.0

    @patch('utils.gap_analyzer.json.load')
    @patch('pathlib.Path.exists')
    def test_get_learning_resources(self, mock_exists, mock_json_load):
        """Test fetching learning resources."""
        mock_exists.return_value = True
        mock_json_load.side_effect = [MOCK_MARKET_STANDARDS, MOCK_LEARNING_RESOURCES]
        
        analyzer = GapAnalyzer()
        missing = ["React", "UnknownLib"]
        resources = analyzer._get_learning_resources(missing)
        
        assert "React" in resources
        assert "UnknownLib" not in resources
        assert len(resources["React"]) == 1
        assert resources["React"][0]["title"] == "React Docs"
