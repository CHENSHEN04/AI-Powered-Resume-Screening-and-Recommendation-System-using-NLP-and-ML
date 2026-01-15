"""
Pytest Configuration and Fixtures
==================================
Shared fixtures for all tests in the AI Resume Screening System.
"""

import sys
from pathlib import Path

# Add project root to Python path so utils module can be imported
# This allows running individual test files and debugging to work properly
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest

# ==============================================================================
# Path Fixtures
# ==============================================================================

@pytest.fixture
def project_root():
    """Return the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def sample_resumes_dir(project_root):
    """Return the sample resumes directory."""
    return project_root / "tests" / "sample_resumes"


@pytest.fixture
def valid_resumes_dir(sample_resumes_dir):
    """Return the valid sample resumes directory."""
    return sample_resumes_dir / "valid"


@pytest.fixture
def invalid_resumes_dir(sample_resumes_dir):
    """Return the invalid sample resumes directory."""
    return sample_resumes_dir / "invalid"


@pytest.fixture
def data_dir(project_root):
    """Return the data directory."""
    return project_root / "data"


@pytest.fixture
def models_dir(project_root):
    """Return the models directory."""
    return project_root / "models"


# ==============================================================================
# Sample Data Fixtures
# ==============================================================================

@pytest.fixture
def sample_resume_text():
    """Return sample resume text for testing."""
    return """
    John Doe
    Software Engineer
    john.doe@email.com | (555) 123-4567
    
    EDUCATION
    Bachelor of Science in Computer Science
    University of Technology, 2024
    GPA: 3.8/4.0
    
    SKILLS
    Programming Languages: Python, JavaScript, SQL
    Frameworks: React, Django, Flask
    Tools: Git, Docker, AWS
    
    EXPERIENCE
    Software Engineering Intern | Tech Company | Summer 2023
    - Developed REST APIs using Python and Flask
    - Built frontend components with React
    - Collaborated with team using Git and Agile methodologies
    
    PROJECTS
    E-commerce Platform
    - Built full-stack web application using React and Django
    - Implemented user authentication and payment processing
    """


@pytest.fixture
def sample_skills_list():
    """Return a sample list of extracted skills."""
    return [
        {"name": "Python", "level": 4},
        {"name": "JavaScript", "level": 3},
        {"name": "SQL", "level": 3},
        {"name": "React", "level": 3},
        {"name": "Django", "level": 2},
        {"name": "Git", "level": 3},
    ]


@pytest.fixture
def sample_job_categories():
    """Return sample job categories for testing."""
    return [
        "junior_frontend_developer",
        "junior_backend_developer",
        "data_analyst",
        "software_engineer_fullstack",
    ]


# ==============================================================================
# Mock Fixtures
# ==============================================================================

@pytest.fixture
def mock_streamlit_session():
    """Mock Streamlit session state for testing."""
    class MockSessionState(dict):
        def __getattr__(self, name):
            return self.get(name)
        
        def __setattr__(self, name, value):
            self[name] = value
    
    return MockSessionState()
