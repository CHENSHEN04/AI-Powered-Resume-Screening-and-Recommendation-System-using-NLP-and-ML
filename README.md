# AI-Powered Resume Screening & Recommendation System
> **Vision**: A "Deep Career Coach" for students and fresh graduates. 
> **Status**: Implementation Phase (Dual Frontend: Streamlit Monolith Demo & Next.js/FastAPI Decoupled App)

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://chenshen04-ai-powered-resume-screening-and-recommend-app-dnjfw4.streamlit.app/)

---

## 📖 Overview

Traditional Applicant Tracking Systems (ATS) act as "black boxes" that filter out candidates without explanation, leaving students unaware of why they failed or what to learn next. 

This system pivots the screening paradigm from **rejection** to **mentorship**. It parses PDF/DOCX resumes, predicts the candidate's target job role, runs a dynamic semantic gap analysis against market standards or custom Job Descriptions (JDs), and builds a personalized growth plan containing feedback, customized interview questions, and curated learning roadmaps.

---

## 🛠️ System Architecture & AI Pipeline

The system is designed with a **Three-Layer Intelligent Processing Pipeline**:

```
[Candidate Resume & JD] 
          │
          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 1. Intelligent Parsing Layer                                           │
│    - PyMuPDF / pdfplumber for digital files                            │
│    - Tesseract OCR fallback for scanned documents                      │
│    - Layout-aware parser to extract structural sections                │
└────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. Hybrid Classification & Extraction Layer                           │
│    - Broad Classification: TF-IDF + SVM Classifier (SGD-trained)       │
│    - Semantic Nuance Classifier: BERT SentenceTransformers             │
│    - Skill Extraction: Customized spaCy NER + Pattern Matchers         │
└────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. Generative Feedback & Coaching Layer                                │
│    - Match scoring: Weighted matrix of BERT, skill overlap, & SVM      │
│    - Aesthetic Audit: Computer Vision review of resume formatting      │
│    - LLM Coaching: Gemini / Groq api generating feedback & roadmaps    │
└────────────────────────────────────────────────────────────────────────┘
          │
          ▼
[Deep Coach Dashboard: Scores, Skill Radar, Roadmap, Career Chat]
```

### Decoupled Stack Architecture (Dual-mode)
1. **Streamlit Monolith (Active Demo)**: Implemented in [app.py](file:///c:/CapStone/AI-Powered-Resume-Screening-and-Recommendation-System-using-NLP-and-ML/app.py). A comprehensive single-file application handling routing, parsing, RLS, and the visual UI.
2. **Next.js & FastAPI Stack (Phase 2)**:
   - **Frontend**: A Next.js 14 web application located in the [/frontend](file:///c:/CapStone/AI-Powered-Resume-Screening-and-Recommendation-System-using-NLP-and-ML/frontend) folder, utilizing Tailwind CSS, Framer Motion, and Lucide React.
   - **Backend**: A FastAPI server located in the [/backend](file:///c:/CapStone/AI-Powered-Resume-Screening-and-Recommendation-System-using-NLP-and-ML/backend) folder, wrapping the core python utilities into JSON API routes.

---

## 📂 Project Directory Map

```
project-root/
├── app.py                    # Main Streamlit application
├── supabase_schema.sql       # Production-ready SQL database schema & triggers
├── requirements.txt          # Python dependencies
├── .streamlit/
│   ├── config.toml           # Streamlit theme configurations
│   └── secrets.toml.example  # Streamlit secrets template (Supabase & LLM keys)
├── backend/                  # FastAPI Backend API (Phase 2)
│   ├── main.py               # API entrypoint
│   └── routers/              # Endpoint modules (analyze, chat, history, profile)
├── frontend/                 # Next.js Frontend (Phase 2)
│   ├── app/                  # Pages (dashboard, login, signup)
│   └── components/           # Reusable React components
├── data/                     # Dynamic standard files
│   ├── market_standards.json # Benchmarks for roles (Required & Recommended skills)
│   └── learning_resources.json # Curated courses and documentation mapped to skills
├── models/                   # Pre-trained ML classifiers
│   ├── clf.joblib            # Trained SVM classifier
│   └── tfidf.joblib          # Fitted TF-IDF Vectorizer
├── utils/                    # Shared Python core business logic
│   ├── parser.py             # Document parser (fitz, docx) & OCR fallback
│   ├── skill_extractor.py    # Custom spaCy NER skill extractor
│   ├── classifier.py         # Broad role classifier interface
│   ├── gap_analyzer.py       # Computes overlaps & identifies skill deficits
│   ├── ai_assistant.py       # Gemini API caller, chat history, and visual auditor
│   └── role_standards_resolver.py # Automatically extracts custom role expectations
├── scripts/                  # Development scripts
│   ├── train_model.py        # Model training script (runs on HF resume-atlas dataset)
│   └── seed_database.py      # Seeds Supabase schema with json market benchmarks
└── tests/                    # Pytest test cases
    ├── unit/                 # Model, parsing, and validator unit tests
    └── integration/          # Core pipeline integration tests
```

---

## 🚀 Quick Start (Local Setup)

### 1. Prerequisites
- Python 3.9+
- Node.js 18+ (for Next.js frontend)

### 2. Environment Configuration
1. Clone the project and configure Python virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # Windows
   # source venv/bin/activate  # macOS/Linux
   pip install -r requirements.txt
   python -m spacy download en_core_web_sm
   ```

2. Copy the secrets template and configure credentials:
   ```bash
   copy .streamlit\secrets.toml.example .streamlit\secrets.toml
   ```
   Add your **Supabase URL & Keys**, and your **GEMINI_API_KEY** (from AI Studio).

### 3. Model Training & Database Seeding
Before running the application, populate standard categories and train classification models:
```bash
# Seeding market benchmarks to Supabase Database
python scripts/seed_database.py

# Training SGD Classification models on HuggingFace dataset
python scripts/train_model.py
```

### 4. Running the Applications

#### Option A: Streamlit Monolith (Recommended Demo)
```bash
streamlit run app.py
```
Open `http://localhost:8501` to access the application.

#### Option B: Decoupled Next.js + FastAPI Stack
1. Start the FastAPI backend server:
   ```bash
   python backend/main.py
   ```
2. Start the Next.js development server:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
   Open `http://localhost:3000` to access the application.

---

## 📊 Evaluation Metrics

1. **Classification Accuracy**: Targets $>85\%$ F1-score predicting job categories.
2. **Gap Detection Precision**: Targets $>80\%$ precision in identifying missing required capabilities.
3. **Conversion Optimization**: Evaluates guest teaser clicks converted into active user profiles.

---

## 📄 License
This project is licensed under the MIT License.
