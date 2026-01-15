# AI-Powered Resume Screening and Recommendation System

> **Version**: 1.0.0  
> **Status**: In Development (Milestone 1)

## Overview

This AI-powered system helps students and fresh graduates:

- 📄 **Parse Resumes**: Upload PDF/DOCX and extract structured data
- 🔍 **Analyze Skills**: NER + keyword-based skill extraction
- 📊 **Gap Analysis**: Compare skills against market standards
- 🎯 **Recommendations**: Get personalized career coaching

## Quick Start

### Prerequisites

- Python 3.9+
- pip (Python package manager)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/AI-Resume-Screening.git
cd AI-Resume-Screening

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_sm
```

### Configuration

1. Copy the secrets template:
   ```bash
   copy .streamlit\secrets.toml.example .streamlit\secrets.toml
   ```

2. Edit `.streamlit/secrets.toml` with your credentials:
   - Supabase URL and keys
   - Admin password hash

### Running the App

```bash
streamlit run app.py
```

The app will open at `http://localhost:8501`

## Project Structure

```
project/
├── app.py                    # Main Streamlit application
├── requirements.txt          # Python dependencies
├── .streamlit/
│   ├── config.toml           # Streamlit theme config
│   └── secrets.toml.example  # Secrets template (copy to secrets.toml)
├── data/
│   ├── market_standards.json # Job category benchmarks
│   └── learning_resources.json # Curated courses/tutorials
├── models/                   # Trained ML models (.pkl, .joblib)
├── utils/                    # Core business logic
│   ├── parser.py             # PDF/DOCX parsing
│   ├── skill_extractor.py    # NER + keyword extraction
│   ├── classifier.py         # TF-IDF/SVM + BERT
│   ├── gap_analyzer.py       # Skill gap analysis
│   └── ...
├── pages/                    # Streamlit multi-page app
├── scripts/
│   └── train_models.py       # Model training script
└── tests/
    ├── conftest.py           # Pytest fixtures
    ├── unit/                 # Unit tests
    ├── integration/          # Integration tests
    └── sample_resumes/       # Test resume files
```

## Development

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=utils --cov-report=html

# Run specific test file
pytest tests/unit/test_parser.py -v
```

### Training Models

Before first deployment, train the classification models:

```bash
python scripts/train_models.py
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Frontend | Streamlit |
| ML Models | sentence-transformers, scikit-learn, spaCy |
| Database | Supabase (PostgreSQL) |
| File Storage | Supabase Storage |
| Hosting | Streamlit Cloud |

## License

MIT License - See [LICENSE](LICENSE) for details.
