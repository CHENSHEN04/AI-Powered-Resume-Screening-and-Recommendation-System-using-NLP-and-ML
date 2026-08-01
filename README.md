# Deep Career Coach
### AI-Powered Resume Screening and Recommendation System using NLP and ML

> **Capstone Project 2 — Final Report** | Bachelor of Information Systems (Honours) (Data Analytics), Sunway University
> **Author**: Chen Shen (22065833) · **Supervisor**: Prof. Angela Lee Siew Hoong · **Semester**: September 2025

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://chenshen04-ai-powered-resume-screening-and-recommend-app-dnjfw4.streamlit.app/)

---

## 📖 Overview

Manual resume screening is slow and inconsistent, and first-generation Applicant Tracking Systems (ATS) rely on rigid keyword matching that misreads context, misses synonyms, and rejects up to ~75% of resumes before a human ever reads them. This disproportionately hurts students and early-career candidates, who lack insider knowledge of ATS-friendly formatting and receive no feedback on *why* they were filtered out.

**Deep Career Coach** flips the paradigm from **rejection** to **mentorship**. It parses PDF/DOCX resumes and job descriptions, predicts the candidate's target job role, runs a dynamic semantic skill-gap analysis against market standards or a pasted JD, and generates a personalized growth plan — transparent hire-ability scores, a skill radar, a visual formatting audit, LLM-generated feedback, custom mock-interview questions, and a curated learning roadmap.

The system is built around resolving the **"latency vs. depth" trade-off**: combining a fast statistical classifier with a lightweight semantic transformer so that career coaching feels instantaneous, explainable, and privacy-respecting rather than a black box.

---

## 🛠️ System Architecture

The system implements a **Three-Layer Intelligent Processing Pipeline**:

```
[Candidate Resume & JD]
          │
          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 1. Intelligent Parsing Layer                                           │
│    - pdfplumber (primary) + PyMuPDF (fallback/rendering) for PDFs      │
│    - python-docx for Word files                                        │
│    - Tesseract OCR fallback for scanned/image-only documents           │
│    - Heuristic section segmentation (Education, Experience, Skills…)   │
└────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 2. Hybrid Classification & Extraction Layer                            │
│    Stream A (Statistical/Lexical)      Stream B (Semantic/Contextual)  │
│    - Calibrated Linear SVM             - all-MiniLM-L6-v2               │
│      over 5,000-feature TF-IDF           SentenceTransformer            │
│      vector space (43 job roles)         (cosine-similarity ranking)    │
│    - spaCy NER + EntityRuler pattern matcher (skill/entity extraction) │
└────────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────────────────────┐
│ 3. Generative Feedback & Coaching Layer                                │
│    - Weighted hire-ability scorer (semantic + skills + SVM + education)│
│    - Visual Polish Scanner: renders resume to image, audits layout     │
│    - LLM Coaching via Google Gemini / Groq (feedback, interview Qs,    │
│      learning roadmap) — fed only structured, non-PII context          │
└────────────────────────────────────────────────────────────────────────┘
          │
          ▼
[Deep Coach Dashboard: Hire-ability Score, Skill Radar, Roadmap, AI Chat]
```

### Weighted Hire-ability Score

To prevent keyword-stuffing from gaming the score, the final index blends four signals:

```
Final Score = (0.50 × Semantic Similarity)     # SentenceTransformer cosine similarity
            + (0.30 × Skill Overlap)           # spaCy NER matched ∩ required skills
            + (0.10 × SVM Confidence)          # calibrated classifier probability
            + (0.10 × Education Match)         # degree-level hierarchy match
```

For **custom/out-of-distribution roles** (outside the 43 trained categories), the SVM component is bypassed and its weight is redistributed to the semantic score, so scoring remains mathematically valid without closed-world constraints.

### Dual-Mode Stack Architecture

1. **Streamlit Monolith (Active Demo)** — [app.py](app.py). A single-runtime application that unifies the UI, NLP/ML pipeline, and Supabase connectivity for rapid iteration and the deployed demo.
2. **Decoupled Next.js + FastAPI Stack (Production-track)**:
   - **Frontend**: Next.js 14 (React, Tailwind CSS, Framer Motion, Lucide) in [/frontend](frontend).
   - **Backend**: FastAPI REST API in [/backend](backend), wrapping the same `utils/` NLP core into JSON endpoints, secured with Supabase JWT bearer auth.

Both stacks share the same core `utils/` pipeline and a **Supabase (PostgreSQL) backend** with **Row-Level Security (RLS)** so users can only ever read or write their own resumes, skills, and chat history — PII stays local, and only structured, de-identified context (skills, gaps, target role) is sent to external LLM APIs.

---

## 📊 Evaluation Results

Evaluated on the [`ahmedheakl/resume-atlas`](https://huggingface.co/datasets/ahmedheakl/resume-atlas) dataset (13,389 labeled resumes, 43 job categories), stratified 70/15/15 train/val/test split. Full methodology and discussion in the capstone report; raw numbers are reproducible from [data/model_metrics.json](data/model_metrics.json).

| Dimension | Metric | Result |
|---|---|---|
| **Classification** (Calibrated Linear SVM + TF-IDF) | Test Accuracy | **82.23%** |
| | Macro F1-Score | **81.62%** |
| | Macro Precision / Recall | 82.35% / 81.50% |
| | Inference Latency | 0.04 ms |
| **Semantic Ranking** (`all-MiniLM-L6-v2` vs. `bert-base-uncased` baseline) | Mean Reciprocal Rank (MRR) | **0.6446** (vs. 0.2412 baseline — 2.7×) |
| | Top-5 Match Accuracy | **85.7%** (vs. 28.6% baseline) |
| | Embedding Latency | 112.05 ms (vs. 895.14 ms baseline — 87.5% faster) |
| **Skill Gap Detection** (spaCy NER + Pattern Matcher) | Precision | **84.50%** |
| | Recall | 82.10% |
| **End-to-End Pipeline** | Total In-Memory Latency | **232.09 ms** (well under the 1.0s HCI interactivity threshold) |

**Key takeaways**: the distilled `all-MiniLM-L6-v2` model was chosen for production over raw `bert-base-uncased` because it is both more accurate for ranking (fine-tuned specifically for semantic similarity, not just masked-language modelling) and ~3× faster on CPU — resolving the latency-vs-depth trade-off. The 70/15/15 split was selected over 60/20/20, 80/10/10, and 90/5/5 alternatives for the best Macro F1 with the lowest training time (32.73s).

Known classification confusion pairs (e.g., *Management* vs. *Operations Manager/PMO*, *React Developer* vs. *Web Designing*) are mitigated at the product level via an 85%-confidence user-confirmation prompt, manual role override, and the fact that SVM confidence only contributes 10% to the final weighted score.

---

## 📂 Project Directory Map

```
project-root/
├── app.py                        # Main Streamlit application (monolith demo)
├── supabase_schema.sql           # PostgreSQL schema, RLS policies & triggers
├── requirements.txt              # Python dependencies
├── .streamlit/
│   ├── config.toml                # Streamlit theme configuration
│   └── secrets.toml.example       # Secrets template (Supabase & LLM API keys)
├── backend/                       # FastAPI REST API (decoupled stack)
│   ├── main.py                     # API entrypoint, CORS & middleware
│   ├── auth.py                     # Supabase JWT bearer authentication
│   ├── schemas.py                  # Pydantic request/response data contracts
│   └── routers/                    # analyze, chat, history, metrics, profile
├── frontend/                      # Next.js 14 frontend (decoupled stack)
│   ├── app/                        # Pages: dashboard, history, login, signup
│   └── components/                 # Reusable React components
├── data/                          # Dynamic standards & evaluation artifacts
│   ├── market_standards.json        # Required/recommended skills per role
│   ├── learning_resources.json      # Curated courses mapped to skills
│   ├── salary_ranges.json           # Role salary benchmarks
│   └── model_metrics.json           # Classifier & semantic-matching evaluation results
├── models/                        # Pre-trained ML artifacts
│   ├── clf.joblib                   # Calibrated Linear SVM classifier
│   ├── tfidf.joblib                 # Fitted TF-IDF vectorizer (5,000 features)
│   └── encoder.joblib               # Label encoder for the 43 job categories
├── utils/                         # Shared Python core (NLP/ML business logic)
│   ├── parser.py                    # pdfplumber/PyMuPDF/docx parsing + OCR fallback
│   ├── skill_extractor.py           # spaCy NER + EntityRuler skill extraction
│   ├── classifier.py                # Calibrated Linear SVM role classifier
│   ├── semantic_matcher.py          # SentenceTransformer cosine-similarity ranking
│   ├── weighted_scorer.py           # Multi-factor hire-ability score aggregation
│   ├── gap_analyzer.py              # Skill overlap & gap computation
│   ├── jd_matcher.py                # Resume-to-JD comparative alignment
│   ├── role_standards_resolver.py   # Dynamic custom-role standard synthesis
│   ├── ai_assistant.py              # Gemini/Groq API caller, chat, visual auditor
│   ├── growth_tracker.py            # Historical progress tracking
│   ├── category_manager.py          # Job category CRUD/lookup helpers
│   ├── db_handler.py                # Supabase client & query helpers
│   ├── pdf_generator.py             # Exportable PDF report generation
│   ├── visualizer.py                # Skill radar / chart rendering
│   └── validators.py, errors.py, rate_limiter.py, date_parser.py, mcp_client.py
├── scripts/                       # Development & ML lifecycle scripts
│   ├── train_model.py               # Trains the SVM on resume-atlas dataset
│   ├── evaluate_models.py           # MiniLM vs. BERT semantic ranking evaluation
│   ├── run_split_experiments.py     # Data-split strategy comparison (Table 4)
│   └── seed_database.py             # Seeds Supabase with market benchmark JSON
└── tests/                         # Pytest suite
    ├── unit/                        # Classifier, parser, gap analyzer, validators…
    └── integration/                 # End-to-end pipeline workflow tests
```

---

## 🚀 Quick Start (Local Setup)

### 1. Prerequisites
- Python 3.9+
- Node.js 18+ (only needed for the Next.js frontend)
- Tesseract OCR installed and on PATH (for scanned-resume fallback)

### 2. Environment Configuration
```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

Copy the secrets template and configure credentials:
```bash
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
```
Add your **Supabase URL & Keys**, and your **GEMINI_API_KEY** / **GROQ_API_KEY**.

### 3. Model Training & Database Seeding
```bash
# Seed market benchmarks (roles, skills, learning resources) into Supabase
python scripts/seed_database.py

# Train the Calibrated Linear SVM classifier on the resume-atlas dataset
python scripts/train_model.py
```

### 4. Running the Application

**Option A — Streamlit Monolith (recommended demo)**
```bash
streamlit run app.py
```
Open `http://localhost:8501`.

**Option B — Decoupled Next.js + FastAPI Stack**
```bash
python backend/main.py
```
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:3000`.

### 5. Running Tests
```bash
pytest tests/
```

---

## 🔐 Data Privacy & Security

- **Local-first processing**: text extraction, SVM classification, and SentenceTransformer embeddings all run on the application server — raw resumes are never sent to an LLM.
- **PII isolation**: only structured, de-identified context (extracted skills, detected gaps, target role, layout metrics) is passed to the Gemini/Groq API for feedback generation.
- **PostgreSQL Row-Level Security**: Supabase RLS policies (`auth.uid() = user_id`) enforce data isolation at the database kernel level for `resumes`, `resume_skills`, and chat history — see [supabase_schema.sql](supabase_schema.sql).
- **Bias mitigation**: demographic attributes (name, gender, age, nationality) are excluded from the feature pipeline; classification is based solely on skills, experience, and education.

---

## 🧭 Limitations & Future Work

| Limitation | Planned Direction |
|---|---|
| Closed-world SVM bounded to 43 trained job categories | Open-world zero-shot classification via embedding projection |
| Dictionary-based skill extraction (spaCy EntityRuler) | Custom transformer-based token classification (deep NER) for novel skills |
| English-only parsing and embeddings | Multilingual SentenceTransformer + translation preprocessing |
| In-memory O(N) cosine similarity | `pgvector` + HNSW indexing on Supabase for sub-millisecond ANN search at scale |
| Cloud LLM dependency (2–4s latency, third-party cost) | On-premises quantized SLM (e.g., Llama-3-8B-Instruct) for coaching feedback |
| No longitudinal outcome tracking | Cohort progression logging to correlate coaching with real hiring outcomes |

---

## 📄 License
This project is licensed under the MIT License.
