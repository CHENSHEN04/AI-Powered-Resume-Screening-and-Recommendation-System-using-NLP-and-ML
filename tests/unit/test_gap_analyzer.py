"""
Test Gap Analyzer Module
========================
Unit tests for gap analysis and recommendation functionality.
"""

import pytest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
from utils.gap_analyzer import GapAnalyzer
from utils.role_standards_resolver import (
    extract_skill_candidates,
    is_standards_usable,
    resolve_role_standards,
    skill_mentioned_in_text,
    standards_from_jd,
)

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
        assert result["required_skills"] == ["HTML", "CSS", "JavaScript"]
        assert result["recommended_skills"] == ["React", "TypeScript"]
        assert result["nice_to_have"] == ["Figma"]
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
    def test_analyze_gaps_with_transferable_bonus(self, mock_exists, mock_json_load):
        """Test that extra skills provide a bonus to match_percentage in analyze_gaps."""
        mock_exists.return_value = True
        mock_json_load.side_effect = [MOCK_MARKET_STANDARDS, MOCK_LEARNING_RESOURCES]
        
        analyzer = GapAnalyzer()
        
        # User has required skills: HTML, CSS, JavaScript
        # Also has 5 extra skills not in standards: Excel, Python, Java, SQL, SAP
        user_skills = ["HTML", "CSS", "JavaScript", "Excel", "Python", "Java", "SQL", "SAP"]
        result = analyzer.analyze_gaps(user_skills, "Frontend Developer")
        
        # Required skills weight sum = 3 * 1.0 = 3.0
        # Recommended skills weight sum = 2 * 0.5 = 1.0
        # Nice weight sum = 1 * 0.2 = 0.2
        # Total weight = 4.2
        # Matched weight = 3.0 (from required) + 0.0 (from recommended/nice) = 3.0
        # Base match % = 3.0 / 4.2 * 100 = 71.4%
        # User has 5 extra skills -> bonus is 5.0%
        # Boosted match % = 71.4% + 5.0% = 76.4%
        assert result["match_percentage"] == 76.4

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

    @patch('utils.ai_assistant._call_ai')
    @patch('utils.gap_analyzer.json.load')
    @patch('pathlib.Path.exists')
    def test_get_learning_resources(self, mock_exists, mock_json_load, mock_call_ai):
        """Test fetching learning resources."""
        mock_exists.return_value = True
        mock_json_load.side_effect = [MOCK_MARKET_STANDARDS, MOCK_LEARNING_RESOURCES]
        mock_call_ai.return_value = None
        
        analyzer = GapAnalyzer()
        missing = ["React", "UnknownLib"]
        resources = analyzer._get_learning_resources(missing)
        
        assert "React" in resources
        assert "UnknownLib" not in resources
        assert len(resources["React"]) == 1
        assert resources["React"][0]["title"] == "React Docs"

    @patch('utils.gap_analyzer.json.load')
    @patch('pathlib.Path.exists')
    @patch('utils.gap_analyzer.resolve_role_standards')
    def test_empty_db_role_resolves_dynamic_standards(self, mock_resolve, mock_exists, mock_json_load):
        """Existing roles with no market_standards should be repopulated dynamically."""
        mock_exists.return_value = True
        mock_json_load.side_effect = [{"job_categories": {}}, {"resources": {}}]
        mock_db = MagicMock()
        mock_db.get_market_standards.return_value = {
            "title": "Cloud Security Specialist",
            "required_skills": [],
            "recommended_skills": [],
            "nice_to_have": [],
            "weights": {"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3},
        }
        mock_db.save_custom_role.return_value = (True, None)
        mock_resolve.return_value = ({
            "title": "Cloud Security Specialist",
            "required_skills": ["AWS", "Network Security"],
            "recommended_skills": ["SIEM"],
            "nice_to_have": ["Terraform"],
            "salary_ranges": {"Malaysia": "RM5,000 - RM9,000/mo"},
            "weights": {"required": 1.0, "recommended": 0.6, "nice_to_have": 0.3},
        }, None)

        analyzer = GapAnalyzer(mock_db)
        result = analyzer.analyze_gaps(["AWS"], "cloud_security_specialist", jd_text="Requires AWS and SIEM.")

        assert result["missing_required"] == ["Network Security"]
        assert result["missing_recommended"] == ["SIEM"]
        mock_db.save_custom_role.assert_called_once()

    @patch('utils.gap_analyzer.json.load')
    @patch('pathlib.Path.exists')
    def test_is_skill_matched_false_positives(self, mock_exists, mock_json_load):
        """Test that false-positive substring pairs are correctly rejected."""
        mock_exists.return_value = True
        mock_json_load.side_effect = [{"job_categories": {}}, {"resources": {}}]
        
        analyzer = GapAnalyzer()
        
        # Java should not match JavaScript
        assert not analyzer._is_skill_matched("Java", {"javascript", "python"})
        # Word should not match Wordpress
        assert not analyzer._is_skill_matched("Word", {"wordpress", "html"})
        # But normal substring matches should work (e.g. "Analytical skills" matches "analytical")
        assert analyzer._is_skill_matched("analytical", {"analytical skills"})

    @patch('utils.gap_analyzer.json.load')
    @patch('pathlib.Path.exists')
    def test_is_skill_matched_asymmetric_semantics(self, mock_exists, mock_json_load):
        """Test asymmetric semantic matching for MS Office suites and individual apps."""
        mock_exists.return_value = True
        mock_json_load.side_effect = [{"job_categories": {}}, {"resources": {}}]
        
        analyzer = GapAnalyzer()
        
        # 1. Target "MS Office" matches user having "Microsoft Excel"
        assert analyzer._is_skill_matched("MS Office", {"microsoft excel"})
        # 2. Target "Excel" matches user having "MS Office"
        assert analyzer._is_skill_matched("Excel", {"ms office"})
        # 3. Target "Excel" does NOT match user having only "Word"
        assert not analyzer._is_skill_matched("Excel", {"word"})
        # 4. Target "SAP" matches user having "ERP" (since SAP is an ERP system)
        assert analyzer._is_skill_matched("SAP", {"erp"})
        # 5. Target "SAP" does NOT match user having only "Oracle"
        assert not analyzer._is_skill_matched("SAP", {"oracle"})
        # 6. Target "Mandarin" matches user having "Chinese"
        assert analyzer._is_skill_matched("Mandarin", {"chinese"})

    @patch('utils.gap_analyzer.json.load')
    @patch('pathlib.Path.exists')
    def test_noise_words_filtered(self, mock_exists, mock_json_load):
        """Test that noise words are correctly filtered out from gaps."""
        mock_exists.return_value = True
        
        # Mock standards containing noise words in required_skills and recommended_skills
        standards_with_noise = {
            "job_categories": {
                "test_role": {
                    "title": "Test Role",
                    "required_skills": ["Python", "Role Summary", "Essential Requirements"],
                    "recommended_skills": ["Git", "APBS", "Data Management Internship"],
                    "nice_to_have": ["Figma"],
                    "weights": {"required": 1.0, "recommended": 0.5, "nice_to_have": 0.2}
                }
            }
        }
        mock_json_load.side_effect = [standards_with_noise, MOCK_LEARNING_RESOURCES]
        
        analyzer = GapAnalyzer()
        result = analyzer.analyze_gaps(["Python"], "test_role")
        
        # Verify noise words are not in required_skills, recommended_skills, or missing lists
        assert "Role Summary" not in result["required_skills"]
        assert "Essential Requirements" not in result["required_skills"]
        assert "APBS" not in result["recommended_skills"]
        assert "Data Management Internship" not in result["recommended_skills"]
        
        assert "Role Summary" not in result["missing_required"]
        assert "Essential Requirements" not in result["missing_required"]
        assert "APBS" not in result["missing_recommended"]
        assert "Data Management Internship" not in result["missing_recommended"]
        
        # Actual valid skills should still be present
        assert "Python" in result["required_skills"]
        assert "Git" in result["missing_recommended"]
class TestRoleStandardsResolver:
    def test_rejects_generic_ai_fallback_skills(self):
        standards = {
            "required_skills": ["Communication", "Problem Solving", "Technical Aptitude"],
            "recommended_skills": ["Project Management"],
            "nice_to_have_skills": ["Adaptability"],
        }

        assert not is_standards_usable(standards)

    @patch('utils.ai_assistant.AIRoleStandardGenerator.generate_standards')
    def test_generic_ai_falls_back_to_jd_skills(self, mock_generate):
        mock_generate.return_value = {
            "description": "Generic fallback",
            "required_skills": ["Communication", "Problem Solving", "Technical Aptitude"],
            "recommended_skills": ["Project Management"],
            "nice_to_have_skills": ["Adaptability"],
            "salary_ranges": {},
        }
        jd_text = """
        Requirements: Python, FastAPI, PostgreSQL, AWS.
        Preferred: Docker, CI/CD, Terraform.
        Bonus: SIEM.
        """

        standards, err = resolve_role_standards("Platform Engineer", jd_text=jd_text)

        assert err is None
        assert standards["_source"] == "jd"
        assert "Python" in standards["required_skills"]
        assert "Docker" in standards["recommended_skills"]

    @patch('utils.ai_assistant.AIRoleStandardGenerator.generate_standards')
    def test_no_ai_no_jd_returns_error(self, mock_generate):
        mock_generate.return_value = {
            "required_skills": ["Communication", "Problem Solving", "Technical Aptitude"],
            "recommended_skills": [],
            "nice_to_have_skills": [],
            "salary_ranges": {},
        }

        standards, err = resolve_role_standards("Unclear Role", jd_text="")

        assert standards is None
        assert "Unable to create usable skill coverage" in err

    def test_jd_extraction_not_limited_to_static_categories(self):
        standards = standards_from_jd(
            "MLOps Engineer",
            "Required: Kubernetes, MLflow, Feature Store, Python. Preferred: Kubeflow and Terraform.",
        )

        assert "Kubernetes" in standards["required_skills"]
        assert "MLflow" in standards["required_skills"]
        assert "Feature Store" in standards["required_skills"]
        assert "Terraform" in standards["recommended_skills"]

    def test_dynamic_jd_skills_can_be_matched_in_resume_text(self):
        jd_skills = extract_skill_candidates("Required: Kubernetes, MLflow, Feature Store.")
        resume_text = "Built deployment workflows with Kubernetes and MLflow model tracking."
        matched = [skill for skill in jd_skills if skill_mentioned_in_text(skill, resume_text)]

        assert "Kubernetes" in matched
        assert "MLflow" in matched
