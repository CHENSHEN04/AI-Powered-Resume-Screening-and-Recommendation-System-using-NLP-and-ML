"""
Test Project Setup
==================
Basic tests to verify the project structure and dependencies are working.
"""

import pytest
from pathlib import Path


class TestProjectStructure:
    """Test that the project structure is correct."""
    
    def test_project_root_exists(self, project_root):
        """Test that the project root directory exists."""
        assert project_root.exists()
    
    def test_required_directories_exist(self, project_root):
        """Test that required directories exist."""
        required_dirs = [
            "utils",
            "tests",
            "data",
            "models",
            "scripts",
            ".streamlit",
        ]
        
        for dir_name in required_dirs:
            dir_path = project_root / dir_name
            assert dir_path.exists(), f"Directory {dir_name} should exist"
    
    def test_required_files_exist(self, project_root):
        """Test that required files exist."""
        required_files = [
            "app.py",
            "requirements.txt",
            "README.md",
            ".gitignore",
            "utils/__init__.py",
            "tests/conftest.py",
        ]
        
        for file_name in required_files:
            file_path = project_root / file_name
            assert file_path.exists(), f"File {file_name} should exist"
    
    def test_streamlit_config_exists(self, project_root):
        """Test that Streamlit config exists."""
        config_path = project_root / ".streamlit" / "config.toml"
        assert config_path.exists(), "Streamlit config.toml should exist"
    
    def test_secrets_template_exists(self, project_root):
        """Test that secrets template exists."""
        template_path = project_root / ".streamlit" / "secrets.toml.example"
        assert template_path.exists(), "secrets.toml.example should exist"


class TestDependencyImports:
    """Test that key dependencies can be imported."""
    
    def test_streamlit_import(self):
        """Test that Streamlit can be imported."""
        import streamlit
        assert streamlit is not None
    
    def test_pytest_import(self):
        """Test that pytest can be imported."""
        import pytest
        assert pytest is not None
    
    def test_pathlib_import(self):
        """Test that pathlib can be imported."""
        from pathlib import Path
        assert Path is not None


class TestFixtures:
    """Test that pytest fixtures work correctly."""
    
    def test_sample_resume_text_fixture(self, sample_resume_text):
        """Test the sample resume text fixture."""
        assert "John Doe" in sample_resume_text
        assert "Python" in sample_resume_text
        assert "EDUCATION" in sample_resume_text
    
    def test_sample_skills_list_fixture(self, sample_skills_list):
        """Test the sample skills list fixture."""
        assert len(sample_skills_list) > 0
        assert any(s["name"] == "Python" for s in sample_skills_list)
    
    def test_sample_job_categories_fixture(self, sample_job_categories):
        """Test the sample job categories fixture."""
        assert len(sample_job_categories) > 0
        assert "junior_frontend_developer" in sample_job_categories
