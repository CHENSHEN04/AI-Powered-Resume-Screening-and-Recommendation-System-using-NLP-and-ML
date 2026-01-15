# AI-Powered Resume Screening System - Output Specification

> **Document Version**: 2.0  
> **Last Updated**: 2026-01-12  
> **Status**: Complete - Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
   - 2.1 Three-Layer Architecture
   - 2.2 Model Decision Logic
   - 2.3 Training Data & Model Pipeline
3. [Data Architecture](#3-data-architecture)
   - 3.1 Storage Model & Database Schema
   - 3.2 Skill Rating System
   - 3.3 Section Extraction Priority
   - 3.4 Job Category Management
4. [User Experience Flow](#4-user-experience-flow)
5. [Edge Case Handling](#5-edge-case-handling)
6. [Technical Implementation](#6-technical-implementation)
   - 6.1 Deployment Stack & Constraints
   - 6.2 Market Standards Database
   - 6.3 Learning Resources
   - 6.4 Logging & Monitoring
   - 6.5 Error Handling
   - 6.6 Test Strategy
7. [Evaluation Metrics](#7-evaluation-metrics)
8. [Scope Prioritization (MoSCoW)](#8-scope-prioritization-moscow)
9. [The "One Thing" That Must Work](#9-the-one-thing-that-must-work)
10. [Future Roadmap](#10-future-roadmap-thesis-appendix)
11. [Appendices](#appendix-a-technology-stack-summary)

---

## 1. Executive Summary

### 1.1 Project Vision
A **hybrid resume screening and career preparation support system** that combines TF-IDF/SVM for fast statistical classification with BERT for semantic understanding. Designed specifically for **students and fresh graduates** seeking internships and entry-level positions.

### 1.2 Core Value Proposition
- **Speed + Depth**: Fill the latency-vs-accuracy gap in resume analysis
- **Coaching, Not Judging**: Skill-gap analysis as career guidance, not pass/fail
- **Transparency**: Solve the "black box" problem with interpretable insights
- **Growth Tracking**: Long-term career development support, not one-shot analysis

### 1.3 Target Users
| User Type | Primary Goals |
|-----------|---------------|
| University Students (Year 1-4) | Prepare for internships, build competitive resumes |
| Fresh Graduates | Identify skill gaps for target job categories |
| Career Switchers | Understand transferable skills and missing requirements |

---

## 2. System Architecture

### 2.1 Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│  Supported Formats: PDF, DOCX (1-2 pages, max 5-10MB)               │
│  Parsing Stack:                                                     │
│   ├── PDF: pdfplumber, PyMuPDF (fitz)                               │
│   ├── DOCX: python-docx                                             │
│   ├── OCR (Secondary): pytesseract, Google Cloud Vision             │
│   ├── NER: spaCy (en_core_web_sm) or custom model                   │
│   └── Fallback: textract                                            │
│  File Validation: magic library for MIME type verification          │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    HYBRID PROCESSING LAYER                          │
├─────────────────────────────────────────────────────────────────────┤
│  Model Integration: CASCADE APPROACH                                │
│   Step 1: TF-IDF/SVM fast filter (<50ms)                            │
│   Step 2: BERT semantic ranking for top candidates (100-200ms)      │
│   Step 3: Combined score with configurable weights                  │
│                                                                     │
│  Recommended Model: sentence-transformers/all-MiniLM-L6-v2          │
│   - 22M parameters, ~20ms latency, optimized for semantic similarity│
│                                                                     │
│  Skill-Gap Pipeline:                                                │
│   1. Extract skills using NER + keyword matching                    │
│   2. Compare against Market Standard JSON database                  │
│   3. Detect "Skill Clusters" for missing link analysis              │
│   4. Calculate gap score + generate coaching recommendations        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                                │
├─────────────────────────────────────────────────────────────────────┤
│  Framework: Streamlit (Desktop-first hybrid)                        │
│  Visualization: Radar Chart + Checklist + Action Cards              │
│  Explainability: SHAP, LIME, Attention Visualization                │
│  Export: PDF Career Roadmap                                         │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Model Decision Logic

**When Models Disagree:**
- Rank by **confidence score**: Higher confidence = Rank 1
- Display **Top 3 results** to user
- User's **selected target job** takes priority for skill-gap analysis

**Fallback Pipeline (tenacity library):**
1. **Gold Standard**: Full BERT analysis
2. **Silver Standard**: TF-IDF/SVM only (if BERT fails)
3. **Bronze**: Basic parsed data (Name, Skills, Education)
4. UI shows "Refresh Full Analysis" button when degraded

### 2.3 Training Data & Model Pipeline

#### 2.3.1 Training Dataset

**Source**: [MikePfunk28/resume-training-dataset](https://huggingface.co/datasets/MikePfunk28/resume-training-dataset)

| Property | Value |
|----------|-------|
| **Samples** | 22,855 resume conversation pairs |
| **Format** | JSONL (role/content pairs) |
| **Content** | Resume critiques, improvement suggestions, career advice |
| **License** | MIT |

**Dataset Structure:**
```json
[
  {"role": "system", "content": "You are an expert resume assistant..."},
  {"role": "user", "content": "Critique this resume: [resume content]"},
  {"role": "assistant", "content": "This resume could benefit from..."}
]
```

**How the Dataset is Used:**

| Purpose | Usage |
|---------|-------|
| **Train TF-IDF Vectorizer** | Extract resume text from `user` role to build vocabulary |
| **Train SVM Classifier** | Label resumes by job category for classification |
| **Skill Pattern Extraction** | Identify common skills mentioned across resumes |
| **Validation Set** | Hold out 20% for testing parsing & classification accuracy |

> **Note**: The fine-tuned model [kiritps/resume-ai-assistant](https://huggingface.co/kiritps/resume-ai-assistant) (2.6GB GPT-Neo) is NOT used at runtime due to memory constraints. We use the lightweight dataset approach instead.

#### 2.3.2 Training Pipeline

```python
# scripts/train_models.py
# Run BEFORE deployment to generate .pkl files

import pandas as pd
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split
from datasets import load_dataset

def load_resume_dataset():
    """Load and preprocess the HuggingFace dataset."""
    dataset = load_dataset("MikePfunk28/resume-training-dataset")
    
    resumes = []
    for item in dataset['train']:
        # Extract resume text from user messages
        for msg in item['messages']:
            if msg['role'] == 'user' and 'resume' in msg['content'].lower():
                resumes.append({
                    'text': msg['content'],
                    'category': extract_job_category(msg['content'])  # Custom function
                })
    
    return pd.DataFrame(resumes)

def train_tfidf_svm(df):
    """Train TF-IDF vectorizer and SVM classifier."""
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        df['text'], df['category'], 
        test_size=0.2, random_state=42
    )
    
    # Train TF-IDF
    tfidf = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 2),
        stop_words='english'
    )
    X_train_tfidf = tfidf.fit_transform(X_train)
    X_test_tfidf = tfidf.transform(X_test)
    
    # Train SVM
    svm = SVC(kernel='linear', probability=True)
    svm.fit(X_train_tfidf, y_train)
    
    # Evaluate
    accuracy = svm.score(X_test_tfidf, y_test)
    print(f"Test Accuracy: {accuracy:.2%}")
    
    # Save models
    with open('models/tfidf_vectorizer.pkl', 'wb') as f:
        pickle.dump(tfidf, f)
    
    with open('models/svm_classifier.pkl', 'wb') as f:
        pickle.dump(svm, f)
    
    return tfidf, svm, accuracy

if __name__ == "__main__":
    df = load_resume_dataset()
    train_tfidf_svm(df)
```

**Training Output Files:**
```
models/
├── tfidf_vectorizer.pkl    # ~5-10 MB (vocabulary + weights)
├── svm_classifier.pkl      # ~10-20 MB (trained classifier)
└── training_metrics.json   # Accuracy, F1, confusion matrix
```

#### 2.3.3 Runtime Model Loading

```python
# utils/model_loader.py
# Used in production Streamlit app

import pickle
import streamlit as st
from sentence_transformers import SentenceTransformer

@st.cache_resource(show_spinner="Loading classification models...")
def load_classification_models():
    """Load pre-trained TF-IDF and SVM from pickle files."""
    with open('models/tfidf_vectorizer.pkl', 'rb') as f:
        tfidf = pickle.load(f)
    
    with open('models/svm_classifier.pkl', 'rb') as f:
        svm = pickle.load(f)
    
    return tfidf, svm

@st.cache_resource(show_spinner="Loading semantic model...")
def load_embedding_model():
    """Load sentence transformer for semantic similarity."""
    return SentenceTransformer('all-MiniLM-L6-v2')

@st.cache_resource
def load_spacy_model():
    """Load spaCy NER model."""
    import spacy
    try:
        return spacy.load("en_core_web_sm")
    except OSError:
        import subprocess
        subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
        return spacy.load("en_core_web_sm")

def classify_resume(text: str) -> dict:
    """Classify resume using hybrid TF-IDF/SVM + BERT approach."""
    tfidf, svm = load_classification_models()
    embedding_model = load_embedding_model()
    
    # Step 1: TF-IDF/SVM fast classification
    text_tfidf = tfidf.transform([text])
    svm_probs = svm.predict_proba(text_tfidf)[0]
    svm_top3 = sorted(
        zip(svm.classes_, svm_probs), 
        key=lambda x: x[1], 
        reverse=True
    )[:3]
    
    # Step 2: BERT semantic similarity for refinement
    resume_embedding = embedding_model.encode(text)
    # Compare with job category embeddings...
    
    return {
        "svm_predictions": svm_top3,
        "bert_similarity": {...},
        "combined_score": {...}
    }
```

**Memory Footprint at Runtime:**
```
┌────────────────────────────────────────────┐
│         RUNTIME MEMORY USAGE               │
├────────────────────────────────────────────┤
│ Base Streamlit + Python:     ~350 MB       │
│ spaCy en_core_web_sm:        ~ 12 MB       │
│ all-MiniLM-L6-v2:            ~ 90 MB       │
│ TF-IDF vectorizer (.pkl):    ~ 10 MB       │
│ SVM classifier (.pkl):       ~ 20 MB       │
│ ────────────────────────────────────       │
│ Total:                       ~482 MB       │
│ Available buffer:            ~518 MB ✅    │
└────────────────────────────────────────────┘
```

---

## 3. Data Architecture

### 3.1 Three-Layer Storage Model (Supabase)

| Layer | Content | Storage Type | Purpose |
|-------|---------|--------------|---------|
| **Source** | Original PDF/DOCX files | Supabase Storage (GCS) | Audit trail, re-parsing |
| **Analytical** | Extracted JSON (skills, education, experience) | PostgreSQL | Skill-gap analysis, recommendations |
| **Historical** | Resume Score snapshots per upload | PostgreSQL | Growth tracking, progress visualization |

### 3.1.1 Database Schema Details

**Entity Relationship Diagram:**
```
┌─────────────┐       ┌─────────────────┐       ┌──────────────────┐
│   users     │──1:N──│    resumes      │──1:N──│ analysis_results │
└─────────────┘       └─────────────────┘       └──────────────────┘
       │                      │
       │                      └──────N:M──────┌──────────────┐
       │                                      │    skills    │
       └──────────────────1:N─────────────────┴──────────────┘
                                                     │
                                              ┌──────┴──────┐
                                              │             │
                                      ┌───────────┐  ┌────────────────┐
                                      │job_categories│ │market_standards│
                                      └───────────┘  └────────────────┘
```

**SQL Table Definitions:**

```sql
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- USERS TABLE
-- ============================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE,
    auth_provider VARCHAR(50) DEFAULT 'email', -- 'email', 'google', 'anonymous'
    display_name VARCHAR(100),
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login_at TIMESTAMP WITH TIME ZONE,
    is_anonymous BOOLEAN DEFAULT FALSE,
    profile_claimed BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_users_email ON users(email);

-- ============================================
-- RESUMES TABLE
-- ============================================
CREATE TABLE resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- File metadata
    original_filename VARCHAR(255) NOT NULL,
    storage_path TEXT NOT NULL,
    file_size_bytes INTEGER,
    page_count INTEGER,
    mime_type VARCHAR(100),
    
    -- Extracted personal info
    extracted_name VARCHAR(200),
    extracted_email VARCHAR(255),
    extracted_phone VARCHAR(50),
    graduation_year INTEGER,
    education_level VARCHAR(50),  -- 'high_school', 'bachelor', 'master', 'phd'
    field_of_study VARCHAR(200),
    
    -- Processing metadata
    parse_confidence DECIMAL(3,2),
    processing_status VARCHAR(50) DEFAULT 'pending',
    parser_version VARCHAR(20),
    
    -- Timestamps
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- Version tracking
    version_number INTEGER DEFAULT 1,
    is_latest BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_resumes_user_id ON resumes(user_id);
CREATE INDEX idx_resumes_status ON resumes(processing_status);
CREATE INDEX idx_resumes_latest ON resumes(user_id, is_latest) WHERE is_latest = TRUE;

-- ============================================
-- SKILLS TABLE (Master list)
-- ============================================
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    canonical_name VARCHAR(100),
    category VARCHAR(50),  -- 'programming', 'framework', 'soft_skill', 'tool'
    aliases TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_skills_name ON skills(name);
CREATE INDEX idx_skills_canonical ON skills(canonical_name);

-- ============================================
-- RESUME_SKILLS TABLE (Junction)
-- ============================================
CREATE TABLE resume_skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id UUID REFERENCES resumes(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    
    self_rated_level INTEGER CHECK (self_rated_level BETWEEN 1 AND 5),
    inferred_level INTEGER CHECK (inferred_level BETWEEN 1 AND 5),
    final_level INTEGER CHECK (final_level BETWEEN 1 AND 5),
    
    source_section VARCHAR(50),
    years_experience DECIMAL(3,1),
    extraction_confidence DECIMAL(3,2),
    user_confirmed BOOLEAN DEFAULT FALSE,
    
    UNIQUE(resume_id, skill_id)
);

CREATE INDEX idx_resume_skills_resume ON resume_skills(resume_id);

-- ============================================
-- JOB_CATEGORIES TABLE
-- ============================================
CREATE TABLE job_categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    slug VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(150),
    parent_category_id UUID REFERENCES job_categories(id),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- MARKET_STANDARDS TABLE
-- ============================================
CREATE TABLE market_standards (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_category_id UUID REFERENCES job_categories(id) ON DELETE CASCADE,
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    
    importance_level VARCHAR(20) NOT NULL,  -- 'required', 'recommended', 'nice_to_have'
    market_demand_percentage INTEGER,
    min_proficiency_level INTEGER CHECK (min_proficiency_level BETWEEN 1 AND 5),
    
    market_context VARCHAR(100),
    source VARCHAR(255),
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    UNIQUE(job_category_id, skill_id)
);

-- ============================================
-- ANALYSIS_RESULTS TABLE
-- ============================================
CREATE TABLE analysis_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resume_id UUID REFERENCES resumes(id) ON DELETE CASCADE,
    target_job_category_id UUID REFERENCES job_categories(id),
    
    overall_score INTEGER CHECK (overall_score BETWEEN 0 AND 100),
    svm_confidence DECIMAL(4,3),
    bert_similarity DECIMAL(4,3),
    combined_score DECIMAL(4,3),
    
    top_matches JSONB,
    matching_skills_count INTEGER,
    missing_skills_count INTEGER,
    total_required_skills INTEGER,
    gap_details JSONB,
    recommendations JSONB,
    
    processing_time_ms INTEGER,
    model_version VARCHAR(50),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_analysis_resume ON analysis_results(resume_id);
CREATE INDEX idx_analysis_created ON analysis_results(created_at DESC);

-- ============================================
-- LEARNING_RESOURCES TABLE
-- ============================================
CREATE TABLE learning_resources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    skill_id UUID REFERENCES skills(id) ON DELETE CASCADE,
    
    title VARCHAR(255) NOT NULL,
    provider VARCHAR(100),
    url TEXT NOT NULL,
    resource_type VARCHAR(50),
    difficulty_level VARCHAR(20),
    estimated_hours DECIMAL(5,1),
    is_free BOOLEAN DEFAULT TRUE,
    
    last_checked_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- SYSTEM_LOGS TABLE
-- ============================================
CREATE TABLE system_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    event_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info',
    
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
    
    message TEXT,
    error_code VARCHAR(50),
    stack_trace TEXT,
    metadata JSONB,
    
    processing_stage VARCHAR(50),
    duration_ms INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_logs_type ON system_logs(event_type);
CREATE INDEX idx_logs_severity ON system_logs(severity);
CREATE INDEX idx_logs_created ON system_logs(created_at DESC);

-- ============================================
-- USER_SESSIONS TABLE
-- ============================================
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    session_token TEXT UNIQUE NOT NULL,
    
    ip_address INET,
    user_agent TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    last_activity_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);
```

### 3.1.2 Supabase Storage Path Convention

```
resumes/
├── {user_id}/
│   ├── {timestamp}_{sanitized_filename}
│   │   Example: 2026-01-12T14-30-00_john_doe_resume.pdf
│   └── ...
└── anonymous/
    └── {session_id}/
        └── {timestamp}_{filename}
```

**Naming Rules:**
- Timestamps in ISO format with colons replaced by dashes
- Filenames sanitized: lowercase, spaces → underscores, special chars removed
- Max filename length: 100 characters

### 3.2 Skill Rating System

**Layered Logic:**
```
Priority 1: User Self-Rating (if provided)
    └── Normalize to 1-5 scale:
        ├── ★★★★☆ → 4
        ├── 80/100 progress bar → 4
        ├── "Expert" → 5 (Novice=1, Beginner=2, Competent=3, Proficient=4, Expert=5)
        
Priority 2: Inferred Weighting (tie-breaker/validation)
    └── Cross-reference with years of experience
    └── Flag discrepancies: "Expert" + 0 years → warn user
    
Default: 3 (if no proficiency given)
```

**Dampening Factor for Students:**
- Self-rated "Expert" + only academic use → System treats as 2/5
- Show coaching message: "Recruiters may see this as 'Beginner' level"

### 3.3 Section Extraction Priority

| Priority | Sections | Rationale |
|----------|----------|-----------|
| 🔴 **High** | Education, Skills | Core for student/fresh grad targeting |
| 🟡 **Medium** | Projects, Certifications, Awards | Demonstrates practical application |
| 🟢 **Low** | Work Experience | Often part-time/cashier for students |

> **Note**: Projects section skills count EQUAL to Work Experience skills

### 3.4 Job Category Management

**Primary**: Dropdown with predefined categories  
**Secondary**: "Other" text field with semantic deduplication

```
User types: "Machine Learning Engineer"
System: "It looks like you mean 'ML Engineer.' Use that instead?"
→ Prevents duplicates from entering database
```

**Maintenance**: Monthly manual review of "Other" entries

---

## 4. User Experience Flow

### 4.1 Onboarding: "Value First" Approach

```
┌─────────────────────────────────────────────────────────────────────┐
│  LANDING PAGE                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │           [Upload Your Resume]  ← Primary CTA               │    │
│  │                                                             │    │
│  │           Already have an account? [Login]                  │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ANONYMOUS UPLOAD (No login required)                               │
│                                                                     │
│  1. User uploads PDF/DOCX                                           │
│  2. Prompted for Target Job Category                                │
│  3. System parses and shows "TEASER" analysis:                      │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │ "Your Technical Score is 75%! We found 3 missing keywords   │ │
│     │ for your target role. [Claim Profile to see full analysis]" │ │
│     └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  REVIEW SCREEN (Before saving profile)                              │
│  ┌────────────────────────┬──────────────────────────────────────┐  │
│  │   ORIGINAL PDF         │   EXTRACTED DATA (Editable)          │  │
│  │   (Left Panel)         │   (Right Panel)                      │  │
│  │                        │                                      │  │
│  │   [PDF Preview]        │   Name: [___________] ✅            │  │
│  │                        │   Email: [__________] ⚠️ Needs check   │  │
│  │                        │   Grad Year: [______] ❓ Conflict      │  │
│  │                        │   Skills: [Tag Cloud with ratings]    │  │
│  │                        │                                      │  │
│  │                        │   [+ Add Missing Section]             │  │
│  └────────────────────────┴────────────────────────────────────┘ │
│                                                                    │
│  Features:                                                         │
│  • Confidence highlighting (orange < 0.7)                           │
│  • Conflict resolution via radio buttons                            │
│  • Undo/Redo support                                                │
│  • "Is this you?" conversational header                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Main Dashboard: Progressive Disclosure

```
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 1: IDENTITY & HOOK (Hero Section)                            │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    ┌─────┐                                      ││
│  │     Resume Score:  │ 72  │ / 100                                ││
│  │                    └─────┘                                      ││
│  │                                                                 ││
│  │     Your Top Matches:                                           ││
│  │     1. Junior Web Developer (90%) ← Click to see gaps          ││
│  │     2. Frontend Engineer (78%)                                  ││
│  │     3. UI/UX Designer (65%)                                     ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 2: SKILLS LANDSCAPE (Radar Chart)                            │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │              Your Skills vs. Market Average                      ││
│  │                                                                 ││
│  │                    JavaScript                                   ││
│  │                       ●                                         ││
│  │           React    ●─────●    CSS                               ││
│  │                   /       \                                     ││
│  │                  ●─────────●                                    ││
│  │                HTML       Git                                   ││
│  │                                                                 ││
│  │     ── You (solid)   ─ ─ Market Standard (dashed)              ││
│  │                                                                 ││
│  │     [Show All Skills ▼]  ← Progressive disclosure              ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PHASE 3: GAP & GROWTH (Action Section)                             │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  SKILL GAP CHECKLIST                                            ││
│  │  ✅ React.js                                                    ││
│  │  ✅ CSS/HTML                                                    ││
│  │  ✅ Git                                                         ││
│  │  ⚠️ Testing (Low proficiency)                                   ││
│  │  ❌ TypeScript (Missing - High Demand)                          ││
│  │  ❌ Next.js (Missing - Recommended)                             ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  RECOMMENDATIONS                                                ││
│  │  ┌─────────────────────────────────────────────────────────┐   ││
│  │  │ ❌ TypeScript                              [Expand ▼]    │   ││
│  │  ├─────────────────────────────────────────────────────────┤   ││
│  │  │ CONTEXT: 80% of Junior Frontend roles require this      │   ││
│  │  │ ACTION: Add a Portfolio Project                          │   ││
│  │  │ HOW-TO: Build a To-Do app with TypeScript + React        │   ││
│  │  │ OUTCOME: +15% match for Web Developer                    │   ││
│  │  │                                                          │   ││
│  │  │ 📚 [FreeCodeCamp TypeScript Course]                      │   ││
│  │  │ 💡 [Project Idea: Type-safe API Client]                  │   ││
│  │  └─────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 4.3 Growth Tracking

**Comparison Type**: Per-upload version comparison

**Key Metrics:**
- Gap Reduction % (❌ → ✅ transitions)
- Overall Score Improvement
- Skills Added Since v1

**Gamification:**
- Badges: "TypeScript Unlocked!", "5 Gaps Filled!"
- Levels: Based on resume completeness
- Celebratory animations on score increase

---

## 5. Edge Case Handling

### 5.1 Empty/Minimal Resumes ("Builder Mode")

**Minimum Viable Content (MVC):**
1. Academic Major / Field of Study
2. Current Education Level

**Graceful Handling:**
```
When parser detects < 3 skills or 0 experience entries:
    └── Trigger "Builder Mode" UI
        ├── Ask 3-5 rapid-fire questions:
        │   • "What is your dream job?"
        │   • "Which programming languages are you learning?"
        │   • "Any university clubs or societies?"
        └── Show "Pathway Analysis":
            • Radar chart with tiny dot (you) → large target (industry)
            • "Unlock SQL" instead of "Missing SQL"
            • First 3 "Power-Ups" to add this semester
```

### 5.2 Bloated Resumes (>3 Pages)

```
Display warning:
"Whoa! Your resume is 10 pages long. Recruiters spend ~6 seconds 
per resume. Upload 1-2 pages for better insights."

Hard limits:
• Max file size: 5-10MB
• Recommended pages: 1-2
• Warning threshold: 3+ pages
```

### 5.3 Low-Confidence Parsing

**Critical Fields (Name/Email) < 30% confidence:**
```
Trigger Confirmation Modal BEFORE dashboard:
┌─────────────────────────────────────────────────────┐
│  "We've analyzed your skills! Just one thing—"      │
│                                                     │
│  Name:  [_______________] ⚠️ Needs check            │
│  Email: [_______________] ✅ Looks good             │
│                                                     │
│  [Continue to My Roadmap]                           │
└─────────────────────────────────────────────────────┘
```

**Learning Loop**: Log all manual corrections → identify parser blind spots

### 5.4 Conflicting Information

**Resolution Heuristics (in order):**
1. **Section Priority**: Education > Summary > Header
2. **Recency Check**: Compare dates against current date (2026)
3. **Pattern Recognition**: Detect "stale dates" (resume not updated)

**UI Handling:**
```
Show conflict with resolution options:
┌─────────────────────────────────────────────────────┐
│  Graduation Year: ❓ Conflict Detected              │
│                                                     │
│  We found: 2024 (Summary) vs 2025 (Education)       │
│                                                     │
│  ○ 2024  ● 2025  ○ Other: [____]                   │
└─────────────────────────────────────────────────────┘
```

### 5.5 File Issues

| Issue | Detection | Response |
|-------|-----------|----------|
| Password-protected PDF | try-except block | `st.error("Please remove password protection")` |
| Scanned image PDF | No text extraction | Offer OCR (secondary), or show "Text-based PDFs only" |
| Corrupted file | magic library MIME check | `st.error("File appears corrupted")` |
| Oversized file | Size check | Reject > 10MB before upload |

---

## 6. Technical Implementation

### 6.1 Deployment Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| **Hosting** | Streamlit Cloud (via GitHub) | Handles 10-50 concurrent users |
| **Authentication** | Supabase Auth / OAuth (Google) | Or simple email-based "Claim Profile" |
| **Database** | Supabase PostgreSQL | Relational for Users → Resumes → Skills |
| **File Storage** | Supabase Storage | Returns URL, stored in main DB |
| **Secrets** | Streamlit Secrets Manager | API keys, never in GitHub |

### 6.1.1 Memory & Resource Constraints

**Streamlit Cloud Limits (Free Tier):**

| Resource | Limit | Mitigation |
|----------|-------|------------|
| **RAM** | 1 GB | Use MiniLM (~90MB), not full BERT (~400MB) |
| **CPU** | Shared | No GPU; CPU inference only |
| **Storage** | Ephemeral | Models re-download on restart |
| **Timeout** | 10 min inactivity | Session state may be lost |
| **Concurrency** | ~5-10 users | Queue heavy requests |

**Memory Budget:**
```
Base Streamlit + Python:    ~350 MB
spaCy en_core_web_sm:       ~ 12 MB
all-MiniLM-L6-v2:           ~ 90 MB
TF-IDF + SVM Models:        ~ 50 MB
────────────────────────────────────
Fixed overhead:             ~502 MB
Available for processing:   ~498 MB
```

**Optimization Strategies:**
- Use `@st.cache_resource` for model loading
- Force garbage collection after each analysis
- Lazy-load BERT (only when needed)
- Process one resume at a time (no batching)

**Model Loading with Memory Management:**

```python
# utils/model_loader.py

import gc
import streamlit as st
from sentence_transformers import SentenceTransformer

@st.cache_resource(show_spinner="Loading AI models...")
def load_embedding_model():
    """Load embedding model once, share across sessions."""
    model = SentenceTransformer('all-MiniLM-L6-v2')
    return model

@st.cache_resource
def load_spacy_model():
    """Load spaCy NER model."""
    import spacy
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        import subprocess
        subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
        nlp = spacy.load("en_core_web_sm")
    return nlp

def cleanup_after_analysis():
    """Force garbage collection after heavy processing."""
    gc.collect()

def get_memory_usage():
    """Monitor current memory usage."""
    import psutil
    process = psutil.Process()
    mb = process.memory_info().rss / 1024 / 1024
    return f"{mb:.1f} MB"
```

### 6.1.2 Authentication Flow Details

**Supported Methods:**

| Method | Use Case | Implementation |
|--------|----------|----------------|
| Anonymous | First-time trial | `supabase.auth.sign_in_anonymously()` |
| Email Magic Link | "Claim Profile" | `supabase.auth.sign_in_with_otp()` |
| Google OAuth | Convenience login | `supabase.auth.sign_in_with_oauth()` |

**Anonymous → Claimed User Flow:**
```
User uploads resume (anonymous)
    ↓
System creates anonymous user in Supabase
    ↓
Results stored with anon_user_id
    ↓
User clicks "Claim Profile"
    ↓
Email magic link OR Google OAuth
    ↓
System merges anon data to new account
```

**Authentication Implementation (auth.py):**

```python
# utils/auth.py

from supabase import create_client
import streamlit as st

def init_supabase():
    """Initialize Supabase client with secrets."""
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["anon_key"]
    )

def create_anonymous_user():
    """Create anonymous session for first-time users."""
    supabase = init_supabase()
    
    if "user_id" not in st.session_state:
        response = supabase.auth.sign_in_anonymously()
        st.session_state.user_id = response.user.id
        st.session_state.is_anonymous = True
    
    return st.session_state.user_id

def claim_profile_email(email: str):
    """Upgrade anonymous user to email-based account."""
    supabase = init_supabase()
    
    response = supabase.auth.sign_in_with_otp({
        "email": email,
        "options": {
            "should_create_user": True,
            "data": {
                "merged_from_anonymous": st.session_state.user_id
            }
        }
    })
    return response

def claim_profile_google():
    """Upgrade anonymous user via Google OAuth."""
    supabase = init_supabase()
    
    response = supabase.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {
            "redirect_to": st.secrets["app"]["callback_url"]
        }
    })
    return response.url

def handle_auth_callback():
    """Process OAuth callback and merge anonymous data."""
    supabase = init_supabase()
    session = supabase.auth.get_session()
    
    if session and st.session_state.get("is_anonymous"):
        old_user_id = st.session_state.user_id
        new_user_id = session.user.id
        
        supabase.table("resumes").update({
            "user_id": new_user_id
        }).eq("user_id", old_user_id).execute()
        
        supabase.table("users").update({
            "merged_to": new_user_id
        }).eq("id", old_user_id).execute()
        
        st.session_state.user_id = new_user_id
        st.session_state.is_anonymous = False

def logout():
    """Clear session and logout."""
    supabase = init_supabase()
    supabase.auth.sign_out()
    st.session_state.clear()
```

**Callback URL Configuration (Supabase Dashboard):**
```
Site URL: https://your-app.streamlit.app
Redirect URLs:
  - https://your-app.streamlit.app/
  - https://your-app.streamlit.app/?callback=auth
  - http://localhost:8501/ (for local dev)
```

### 6.1.3 Rate Limiting & Security

**Upload Rate Limits:**

| User Type | Per Hour | Per Day | Max File Size |
|-----------|----------|---------|---------------|
| Anonymous | 3 | 5 | 5 MB |
| Authenticated | 10 | 50 | 10 MB |

**Rate Limiter Implementation:**

```python
# utils/rate_limiter.py

from datetime import datetime, timedelta
from collections import defaultdict
import streamlit as st

RATE_LIMITS = {
    "anonymous": {
        "uploads_per_hour": 3,
        "uploads_per_day": 5,
        "max_file_size_mb": 5,
    },
    "authenticated": {
        "uploads_per_hour": 10,
        "uploads_per_day": 50,
        "max_file_size_mb": 10,
    }
}

class RateLimiter:
    def __init__(self):
        self._requests = defaultdict(list)
    
    def check_rate_limit(self, user_id: str, is_authenticated: bool) -> tuple[bool, str]:
        """Check if user is within rate limits."""
        limits = RATE_LIMITS["authenticated" if is_authenticated else "anonymous"]
        now = datetime.now()
        
        user_requests = self._requests[user_id]
        
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        user_requests = [r for r in user_requests if r > day_ago]
        self._requests[user_id] = user_requests
        
        recent_hour = [r for r in user_requests if r > hour_ago]
        if len(recent_hour) >= limits["uploads_per_hour"]:
            wait_time = (recent_hour[0] + timedelta(hours=1) - now).seconds // 60
            return False, f"Hourly limit reached. Try again in {wait_time} minutes."
        
        if len(user_requests) >= limits["uploads_per_day"]:
            return False, "Daily limit reached. Please try again tomorrow."
        
        self._requests[user_id].append(now)
        return True, ""
    
    def get_file_size_limit(self, is_authenticated: bool) -> int:
        """Get max file size in bytes."""
        limits = RATE_LIMITS["authenticated" if is_authenticated else "anonymous"]
        return limits["max_file_size_mb"] * 1024 * 1024

rate_limiter = RateLimiter()
```

**File Validation:**

```python
# utils/validators.py

import magic
from pathlib import Path

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILENAME_LENGTH = 100

def validate_file(file_bytes: bytes, filename: str) -> tuple[bool, str]:
    """Validate uploaded file for security and format."""
    
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Invalid file type. Please upload PDF or DOCX files only."
    
    detected_mime = magic.from_buffer(file_bytes[:2048], mime=True)
    if detected_mime not in ALLOWED_MIME_TYPES:
        return False, f"File content doesn't match extension. Please upload a valid {ext} file."
    
    if len(filename) > MAX_FILENAME_LENGTH:
        return False, f"Filename too long. Maximum {MAX_FILENAME_LENGTH} characters."
    
    return True, ""

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for storage."""
    import re
    safe = re.sub(r'[^\w\-\.]', '_', filename)
    safe = safe.lower()
    name, ext = Path(safe).stem, Path(safe).suffix
    if len(name) > 80:
        name = name[:80]
    return f"{name}{ext}"
```

**Security Measures:**
- All file paths use UUIDs, not user-provided names
- PDF password protection detection → reject with message
- Admin page protected by hashed password
- No raw SQL queries (use Supabase client parameterized queries)

**Admin Page Protection:**

```python
# pages/admin.py

import streamlit as st
import hashlib

def check_admin_access():
    """Verify admin access via secret password."""
    if "admin_authenticated" not in st.session_state:
        st.session_state.admin_authenticated = False
    
    if not st.session_state.admin_authenticated:
        st.title("🔐 Admin Access")
        password = st.text_input("Enter admin password:", type="password")
        
        if st.button("Login"):
            input_hash = hashlib.sha256(password.encode()).hexdigest()
            stored_hash = st.secrets.get("admin", {}).get("password_hash", "")
            
            if input_hash == stored_hash:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("Invalid password.")
        
        st.stop()

check_admin_access()
```

### 6.2 Market Standards Database

**Source**: Preprocessed from HuggingFace dataset + manual validation

**Complete Market Standards JSON Structure:**

```json
{
  "metadata": {
    "version": "1.0",
    "last_updated": "2026-01-12",
    "market_context": "Malaysia/Singapore/Global Remote",
    "source": "LinkedIn Job Postings Analysis + Industry Surveys"
  },
  "job_categories": {
    "junior_frontend_developer": {
      "display_name": "Junior Frontend Developer",
      "aliases": ["Frontend Developer", "Front-end Developer", "UI Developer"],
      "required_skills": {
        "JavaScript": { "min_level": 3, "market_demand": 95 },
        "HTML": { "min_level": 4, "market_demand": 98 },
        "CSS": { "min_level": 4, "market_demand": 98 },
        "React": { "min_level": 2, "market_demand": 75 },
        "Git": { "min_level": 2, "market_demand": 85 }
      },
      "recommended_skills": {
        "TypeScript": { "min_level": 2, "market_demand": 60 },
        "Next.js": { "min_level": 2, "market_demand": 45 },
        "Testing": { "min_level": 2, "market_demand": 55 },
        "Responsive Design": { "min_level": 3, "market_demand": 80 }
      },
      "nice_to_have": ["Vue.js", "Angular", "Sass/SCSS", "Webpack"]
    },
    
    "junior_backend_developer": {
      "display_name": "Junior Backend Developer",
      "aliases": ["Backend Developer", "Server-side Developer", "API Developer"],
      "required_skills": {
        "Python": { "min_level": 3, "market_demand": 70 },
        "SQL": { "min_level": 3, "market_demand": 90 },
        "Git": { "min_level": 2, "market_demand": 85 },
        "REST APIs": { "min_level": 3, "market_demand": 88 }
      },
      "recommended_skills": {
        "Django": { "min_level": 2, "market_demand": 45 },
        "Flask": { "min_level": 2, "market_demand": 40 },
        "Node.js": { "min_level": 2, "market_demand": 55 },
        "Docker": { "min_level": 2, "market_demand": 50 },
        "PostgreSQL": { "min_level": 2, "market_demand": 60 }
      },
      "nice_to_have": ["Redis", "MongoDB", "AWS", "CI/CD"]
    },
    
    "data_analyst": {
      "display_name": "Data Analyst",
      "aliases": ["Business Analyst", "BI Analyst", "Analytics Specialist"],
      "required_skills": {
        "Excel": { "min_level": 4, "market_demand": 95 },
        "SQL": { "min_level": 3, "market_demand": 90 },
        "Data Visualization": { "min_level": 3, "market_demand": 85 },
        "Statistics": { "min_level": 3, "market_demand": 75 }
      },
      "recommended_skills": {
        "Python": { "min_level": 2, "market_demand": 65 },
        "Tableau": { "min_level": 2, "market_demand": 55 },
        "Power BI": { "min_level": 2, "market_demand": 60 },
        "R": { "min_level": 2, "market_demand": 35 }
      },
      "nice_to_have": ["Pandas", "Google Analytics", "A/B Testing", "Looker"]
    },
    
    "data_scientist": {
      "display_name": "Junior Data Scientist",
      "aliases": ["ML Engineer", "Data Science Intern"],
      "required_skills": {
        "Python": { "min_level": 4, "market_demand": 95 },
        "Machine Learning": { "min_level": 3, "market_demand": 90 },
        "Statistics": { "min_level": 4, "market_demand": 88 },
        "SQL": { "min_level": 3, "market_demand": 80 }
      },
      "recommended_skills": {
        "TensorFlow": { "min_level": 2, "market_demand": 55 },
        "PyTorch": { "min_level": 2, "market_demand": 50 },
        "Scikit-learn": { "min_level": 3, "market_demand": 70 },
        "Pandas": { "min_level": 3, "market_demand": 85 },
        "Deep Learning": { "min_level": 2, "market_demand": 45 }
      },
      "nice_to_have": ["NLP", "Computer Vision", "AWS SageMaker", "MLflow"]
    },
    
    "ui_ux_designer": {
      "display_name": "UI/UX Designer",
      "aliases": ["Product Designer", "UX Designer", "UI Designer"],
      "required_skills": {
        "Figma": { "min_level": 4, "market_demand": 90 },
        "User Research": { "min_level": 3, "market_demand": 75 },
        "Wireframing": { "min_level": 4, "market_demand": 85 },
        "Prototyping": { "min_level": 3, "market_demand": 80 }
      },
      "recommended_skills": {
        "Adobe XD": { "min_level": 2, "market_demand": 40 },
        "Design Systems": { "min_level": 2, "market_demand": 55 },
        "HTML/CSS": { "min_level": 2, "market_demand": 45 },
        "User Testing": { "min_level": 2, "market_demand": 60 }
      },
      "nice_to_have": ["Motion Design", "Illustration", "Sketch", "InVision"]
    },
    
    "software_engineer_fullstack": {
      "display_name": "Full Stack Developer",
      "aliases": ["Software Engineer", "Web Developer"],
      "required_skills": {
        "JavaScript": { "min_level": 4, "market_demand": 92 },
        "React": { "min_level": 3, "market_demand": 75 },
        "Node.js": { "min_level": 3, "market_demand": 70 },
        "SQL": { "min_level": 3, "market_demand": 85 },
        "Git": { "min_level": 3, "market_demand": 90 }
      },
      "recommended_skills": {
        "TypeScript": { "min_level": 3, "market_demand": 65 },
        "Docker": { "min_level": 2, "market_demand": 55 },
        "AWS": { "min_level": 2, "market_demand": 50 },
        "MongoDB": { "min_level": 2, "market_demand": 45 }
      },
      "nice_to_have": ["GraphQL", "Kubernetes", "CI/CD", "Testing"]
    },
    
    "marketing_coordinator": {
      "display_name": "Marketing Coordinator",
      "aliases": ["Marketing Assistant", "Digital Marketing"],
      "required_skills": {
        "Social Media Marketing": { "min_level": 3, "market_demand": 90 },
        "Content Creation": { "min_level": 3, "market_demand": 85 },
        "Microsoft Office": { "min_level": 3, "market_demand": 88 },
        "Communication": { "min_level": 4, "market_demand": 95 }
      },
      "recommended_skills": {
        "Google Analytics": { "min_level": 2, "market_demand": 65 },
        "SEO": { "min_level": 2, "market_demand": 60 },
        "Email Marketing": { "min_level": 2, "market_demand": 55 },
        "Canva": { "min_level": 2, "market_demand": 50 }
      },
      "nice_to_have": ["Adobe Creative Suite", "HubSpot", "Mailchimp", "Copywriting"]
    },
    
    "hr_assistant": {
      "display_name": "HR Assistant",
      "aliases": ["Human Resources Assistant", "People Operations"],
      "required_skills": {
        "Communication": { "min_level": 4, "market_demand": 95 },
        "Microsoft Office": { "min_level": 4, "market_demand": 92 },
        "Organization": { "min_level": 4, "market_demand": 90 },
        "Attention to Detail": { "min_level": 4, "market_demand": 88 }
      },
      "recommended_skills": {
        "HRIS Systems": { "min_level": 2, "market_demand": 55 },
        "Recruitment": { "min_level": 2, "market_demand": 60 },
        "Payroll": { "min_level": 2, "market_demand": 45 },
        "Employee Relations": { "min_level": 2, "market_demand": 50 }
      },
      "nice_to_have": ["Workday", "BambooHR", "ADP", "Labor Law Knowledge"]
    },
    
    "accountant_junior": {
      "display_name": "Junior Accountant",
      "aliases": ["Accounts Assistant", "Bookkeeper", "Finance Assistant"],
      "required_skills": {
        "Accounting Principles": { "min_level": 4, "market_demand": 95 },
        "Excel": { "min_level": 4, "market_demand": 95 },
        "Attention to Detail": { "min_level": 5, "market_demand": 92 },
        "Financial Reporting": { "min_level": 3, "market_demand": 80 }
      },
      "recommended_skills": {
        "QuickBooks": { "min_level": 2, "market_demand": 55 },
        "SAP": { "min_level": 2, "market_demand": 45 },
        "Tax Knowledge": { "min_level": 2, "market_demand": 60 },
        "Auditing": { "min_level": 2, "market_demand": 40 }
      },
      "nice_to_have": ["ACCA", "CPA", "Oracle Financials", "Xero"]
    },
    
    "project_manager_junior": {
      "display_name": "Junior Project Manager",
      "aliases": ["Project Coordinator", "PMO Assistant"],
      "required_skills": {
        "Project Planning": { "min_level": 3, "market_demand": 90 },
        "Communication": { "min_level": 4, "market_demand": 95 },
        "Microsoft Office": { "min_level": 4, "market_demand": 90 },
        "Time Management": { "min_level": 4, "market_demand": 88 }
      },
      "recommended_skills": {
        "Jira": { "min_level": 2, "market_demand": 60 },
        "Agile/Scrum": { "min_level": 2, "market_demand": 65 },
        "Risk Management": { "min_level": 2, "market_demand": 45 },
        "Stakeholder Management": { "min_level": 2, "market_demand": 55 }
      },
      "nice_to_have": ["PMP", "Trello", "Asana", "MS Project"]
    }
  },
  
  "skill_aliases": {
    "JavaScript": ["JS", "Javascript", "ECMAScript", "ES6", "ES2015+"],
    "Python": ["Python3", "Python 3", "Py"],
    "TypeScript": ["TS"],
    "React": ["React.js", "ReactJS"],
    "Node.js": ["NodeJS", "Node"],
    "PostgreSQL": ["Postgres", "psql"],
    "MongoDB": ["Mongo"],
    "Machine Learning": ["ML"],
    "Artificial Intelligence": ["AI"],
    "Deep Learning": ["DL"],
    "Natural Language Processing": ["NLP"],
    "Computer Vision": ["CV"],
    "Microsoft Office": ["MS Office", "Office Suite", "Word/Excel/PowerPoint"]
  }
}
```

**Update Cadence**: Static for thesis; monthly refresh for production

### 6.3 Learning Resources Database

**Hybrid Approach:**
- **Core Skills**: Hardcoded high-quality links (FreeCodeCamp, Harvard CS50)
- **Long-Tail**: Dynamic API (YouTube Data API, Coursera API) with safety filter

**Link Rot Prevention:**
- Weekly GitHub Action to ping all URLs
- Auto-hide flagged links (404/500)
- "Report Broken Link" button for users

### 6.4 Logging & Monitoring

**What to Log:**
- File metadata (size, page count)
- Error messages with stack traces
- Processing time per stage (Parse → Classify → Gap Analysis)
- Parser confidence scores

**Where to Log:**
- Streamlit Cloud logs (standard output)
- `system_logs` table in Supabase (long-term analysis)

**Admin Dashboard (`/admin` secret page):**
- Aggregated charts (user scores, job distributions)
- Fail-log table (recent parsing failures)
- Data export button (CSV for thesis SPSS/Excel)

### 6.5 Error Handling Standards

**Error Code System:**

| Code Range | Category | Examples |
|------------|----------|----------|
| `E1xxx` | File Upload | E1001 (invalid type), E1002 (too large), E1004 (password-protected) |
| `E2xxx` | Parsing | E2001 (PDF extraction failed), E2005 (no text extracted) |
| `E3xxx` | Analysis | E3001 (BERT timeout), E3004 (timeout) |
| `E4xxx` | Database | E4001 (connection failed), E4003 (storage upload failed) |
| `E5xxx` | Auth | E5001 (session expired), E5003 (OAuth failed) |

**Error Definition (errors.py):**

```python
# utils/errors.py

from enum import Enum
from dataclasses import dataclass
from typing import Optional

class ErrorCode(Enum):
    # File Upload Errors (E1xxx)
    INVALID_FILE_TYPE = "E1001"
    FILE_TOO_LARGE = "E1002"
    FILE_CORRUPTED = "E1003"
    PASSWORD_PROTECTED = "E1004"
    EMPTY_FILE = "E1005"
    
    # Parsing Errors (E2xxx)
    PDF_EXTRACTION_FAILED = "E2001"
    DOCX_EXTRACTION_FAILED = "E2002"
    OCR_FAILED = "E2003"
    NER_EXTRACTION_FAILED = "E2004"
    NO_TEXT_EXTRACTED = "E2005"
    LOW_CONFIDENCE_PARSE = "E2006"
    
    # Analysis Errors (E3xxx)
    BERT_MODEL_ERROR = "E3001"
    SVM_MODEL_ERROR = "E3002"
    SKILL_MATCHING_ERROR = "E3003"
    TIMEOUT_ERROR = "E3004"
    INSUFFICIENT_DATA = "E3005"
    
    # Database Errors (E4xxx)
    DB_CONNECTION_FAILED = "E4001"
    DB_QUERY_FAILED = "E4002"
    STORAGE_UPLOAD_FAILED = "E4003"
    STORAGE_DOWNLOAD_FAILED = "E4004"
    
    # Auth Errors (E5xxx)
    SESSION_EXPIRED = "E5001"
    INVALID_TOKEN = "E5002"
    OAUTH_FAILED = "E5003"
    EMAIL_NOT_VERIFIED = "E5004"

@dataclass
class AppError:
    code: ErrorCode
    message: str
    user_message: str
    suggestion: Optional[str] = None
    recoverable: bool = True

# Error message mappings
ERROR_MESSAGES = {
    ErrorCode.INVALID_FILE_TYPE: AppError(
        code=ErrorCode.INVALID_FILE_TYPE,
        message="File MIME type not in allowed list",
        user_message="Please upload a PDF or DOCX file only.",
        suggestion="Convert your file to PDF and try again.",
        recoverable=True
    ),
    ErrorCode.FILE_TOO_LARGE: AppError(
        code=ErrorCode.FILE_TOO_LARGE,
        message="File exceeds 10MB limit",
        user_message="Your file is too large. Maximum size is 10MB.",
        suggestion="Compress images in your resume or reduce page count.",
        recoverable=True
    ),
    ErrorCode.PASSWORD_PROTECTED: AppError(
        code=ErrorCode.PASSWORD_PROTECTED,
        message="PDF is password-protected",
        user_message="This PDF is password-protected. We cannot read it.",
        suggestion="Remove password protection and re-upload.",
        recoverable=True
    ),
    ErrorCode.NO_TEXT_EXTRACTED: AppError(
        code=ErrorCode.NO_TEXT_EXTRACTED,
        message="No text content found in document",
        user_message="We couldn't extract any text from your file.",
        suggestion="This may be a scanned image. Try uploading a text-based PDF.",
        recoverable=True
    ),
    ErrorCode.BERT_MODEL_ERROR: AppError(
        code=ErrorCode.BERT_MODEL_ERROR,
        message="BERT inference failed",
        user_message="Advanced analysis temporarily unavailable.",
        suggestion="Click 'Retry Analysis' or use basic results.",
        recoverable=True
    ),
    ErrorCode.SESSION_EXPIRED: AppError(
        code=ErrorCode.SESSION_EXPIRED,
        message="User session has expired",
        user_message="Your session has expired. Please log in again.",
        suggestion=None,
        recoverable=True
    ),
}

def get_error(code: ErrorCode) -> AppError:
    return ERROR_MESSAGES.get(code)

def log_error(error: AppError, context: dict = None):
    """Log error to system_logs table."""
    from utils.database import insert_log
    insert_log(
        event_type="error",
        severity="error" if error.recoverable else "critical",
        error_code=error.code.value,
        message=error.message,
        metadata=context
    )
```

**User-Facing Error Format:**
```
┌─────────────────────────────────────────────────────┐
│ ❌ This PDF is password-protected. We cannot read it.│
│                                                      │
│ 💡 Suggestion: Remove password protection and        │
│    re-upload your resume.                            │
│                                                      │
│ [🔄 Try Again]                                       │
│                                                      │
│ Error Code: E1004                                    │
└─────────────────────────────────────────────────────┘
```

**Streamlit Error Display Component:**

```python
# utils/ui_components.py

import streamlit as st
from utils.errors import AppError, ErrorCode

def show_error(error: AppError):
    """Display user-friendly error message."""
    
    with st.container():
        st.error(f"❌ {error.user_message}")
        
        if error.suggestion:
            st.info(f"💡 **Suggestion:** {error.suggestion}")
        
        if error.recoverable:
            if st.button("🔄 Try Again", key=f"retry_{error.code.value}"):
                st.rerun()
        
        st.caption(f"Error Code: {error.code.value}")

def show_warning(message: str, suggestion: str = None):
    """Display warning message."""
    st.warning(f"⚠️ {message}")
    if suggestion:
        st.info(f"💡 {suggestion}")

def show_degraded_mode(missing_feature: str):
    """Show banner when running in fallback mode."""
    st.warning(
        f"⚡ Running in limited mode. {missing_feature} is temporarily unavailable. "
        "Results may be less accurate."
    )
    if st.button("🔄 Refresh Full Analysis"):
        st.session_state.force_full_analysis = True
        st.rerun()
```

### 6.6 Test Strategy

**Test Framework & Structure:**
```
tests/
├── conftest.py                 # Pytest fixtures
├── unit/
│   ├── test_parser.py          # PDF/DOCX parsing tests
│   ├── test_skill_extractor.py # NER and keyword extraction
│   ├── test_skill_matcher.py   # Gap analysis logic
│   ├── test_score_calculator.py# Resume scoring
│   └── test_errors.py          # Error handling
├── integration/
│   ├── test_upload_flow.py     # Full upload → parse → analyze
│   ├── test_database.py        # Supabase operations
│   └── test_auth.py            # Authentication flows
├── sample_resumes/
│   ├── valid/
│   │   ├── simple_one_page.pdf
│   │   ├── complex_two_page.pdf
│   │   ├── minimal_student.pdf
│   │   ├── experienced_senior.pdf
│   │   └── sample.docx
│   ├── invalid/
│   │   ├── password_protected.pdf
│   │   ├── corrupted.pdf
│   │   ├── image_only_scanned.pdf
│   │   └── wrong_extension.txt
│   └── edge_cases/
│       ├── unicode_characters.pdf
│       ├── ten_pages.pdf
│       └── empty_sections.pdf
└── README.md                   # How to run tests
```

**Test Commands:**
```bash
# Run all tests
pytest tests/ -v

# Run unit tests only
pytest tests/unit/ -v

# Run with coverage report
pytest tests/ --cov=utils --cov-report=html

# Run specific test file
pytest tests/unit/test_parser.py -v

# Run tests matching pattern
pytest tests/ -k "test_pdf" -v
```

**Sample Test Cases (test_parser.py):**

```python
# tests/unit/test_parser.py

import pytest
from utils.parser import ResumeParser, ParseResult
from pathlib import Path

SAMPLE_DIR = Path(__file__).parent.parent / "sample_resumes"

class TestResumeParser:
    
    @pytest.fixture
    def parser(self):
        return ResumeParser()
    
    def test_parse_simple_pdf(self, parser):
        """Test parsing a simple one-page PDF."""
        result = parser.parse(SAMPLE_DIR / "valid/simple_one_page.pdf")
        
        assert result.success is True
        assert result.extracted_name is not None
        assert len(result.skills) > 0
        assert result.confidence >= 0.7
    
    def test_parse_password_protected_pdf(self, parser):
        """Test handling of password-protected PDF."""
        result = parser.parse(SAMPLE_DIR / "invalid/password_protected.pdf")
        
        assert result.success is False
        assert result.error_code == "E1004"
    
    def test_parse_corrupted_file(self, parser):
        """Test handling of corrupted PDF."""
        result = parser.parse(SAMPLE_DIR / "invalid/corrupted.pdf")
        
        assert result.success is False
        assert result.error_code in ["E1003", "E2001"]
    
    def test_parse_minimal_resume(self, parser):
        """Test parsing resume with minimal content."""
        result = parser.parse(SAMPLE_DIR / "valid/minimal_student.pdf")
        
        assert result.success is True
        assert result.builder_mode_triggered is True


class TestSkillExtraction:
    
    @pytest.fixture
    def extractor(self):
        from utils.skill_extractor import SkillExtractor
        return SkillExtractor()
    
    def test_extract_programming_skills(self, extractor):
        """Test extraction of programming languages."""
        text = "Proficient in Python, JavaScript, and SQL"
        skills = extractor.extract(text)
        
        assert "Python" in skills
        assert "JavaScript" in skills
        assert "SQL" in skills
    
    def test_skill_normalization(self, extractor):
        """Test that aliases are normalized."""
        text = "Experience with JS, React.js, and Postgres"
        skills = extractor.extract(text)
        
        assert "JavaScript" in skills
        assert "React" in skills
        assert "PostgreSQL" in skills
```

**Sample Resume Test Set:**

| File | Purpose |
|------|---------|
| simple_one_page.pdf | Happy path - basic parsing |
| minimal_student.pdf | Trigger "Builder Mode" (< 3 skills) |
| password_protected.pdf | Error handling - E1004 |
| ten_pages.pdf | Page count warning |
| unicode_characters.pdf | Special character handling |

**Manual Testing Checklist:**
- [ ] Upload flow works end-to-end
- [ ] Low-confidence fields highlighted correctly
- [ ] Radar chart renders properly
- [ ] OAuth login → data persists
- [ ] PDF preview displays in review screen
- [ ] Skill gaps show ✅/⚠️/❌ icons correctly
- [ ] Recommendations expand on click
- [ ] Export PDF works

---

## 7. Evaluation Metrics

### 7.1 System Performance

| Metric | Target | Measurement |
|--------|--------|-------------|
| Parsing Accuracy | >90% on critical fields | Manual validation on test set |
| Classification F1 | >85% weighted | Against held-out test data |
| Latency (P95) | <500ms end-to-end | Streamlit logs |
| Throughput | 10+ resumes/minute | Load testing |

### 7.2 User Behavior (Analytics)

| Category | Metrics |
|----------|---------|
| **User Growth** | Total Uploads, DAU |
| **Performance** | Avg Parsing Time, Parser Confidence |
| **Skill Trends** | Top 5 Missing Skills, Most Popular Job Goals |
| **Effectiveness** | Score Improvement Rate (v1 vs v2) ⭐ Primary success metric |
| **Friction** | Drop-off rate at Review Screen, Login |

### 7.3 Fairness Considerations

- Demographic parity testing
- Bias audit by name/gender proxies
- Documented in thesis methodology

---

## 8. Scope Prioritization (MoSCoW)

### 8.1 Must-Have (Thesis Non-Negotiables)

- [ ] PDF/DOCX Upload with validation
- [ ] BERT/NER Skill Extraction
- [ ] Resume Score Calculation
- [ ] Basic Comparison vs Market Standard
- [ ] Simple Dashboard with results

### 8.2 Should-Have (Core Value)

- [ ] Review/Edit Screen (Human-in-the-loop)
- [ ] Gap Analysis Visualization (Radar Chart)
- [ ] Exportable PDF Career Roadmap

### 8.3 Could-Have (Nice-to-Have)

- [ ] Login with Google (OAuth)
- [ ] Growth Tracking over multiple uploads
- [ ] Job Matching to active LinkedIn listings

### 8.4 Won't-Have (Out of Scope)

- ~~Automatic resume AI rewriting~~ (hallucination risk)
- ~~Video resume analysis~~
- ~~Real-time chat with career coach~~

### 8.5 Emergency Cut List (If Behind Schedule)

1. **Drop**: Complex OAuth → Use simple email-based profiles
2. **Simplify**: Radar Chart → "Top 5 Gaps" table
3. **Limit**: Advanced OCR → "Text-based PDFs only" disclaimer

---

## 9. The "One Thing" That Must Work

> **Data Extraction (Parsing)** is the moment of truth.

If the system fails to find the student's name or misses primary skills, examiners will doubt the entire methodology.

**Safety Net**: Perfect the Review Screen. Even if AI misses a skill, the user can manually add it → "valuable human-AI collaboration"

---

## 10. Future Roadmap (Thesis Appendix)

For thesis "Future Work" section:

1. **University LMS Integration**: Connect with Moodle/Canvas to suggest campus courses for identified gaps
2. **Multi-lingual Support**: Bahasa Melayu/Mandarin resume parsing for regional markets
3. **Soft Skill Inference**: Detect "Leadership" from project descriptions like "Club President"
4. **Recruiter Portal**: Allow companies to post requirements and match with student pools
5. **AI-Powered Resume Rewriting**: With human approval loop to prevent hallucination

---

## Appendix A: Technology Stack Summary

```
Frontend:        Streamlit (Python)
Backend:         Streamlit + Python
Database:        Supabase (PostgreSQL)
File Storage:    Supabase Storage
Authentication:  Supabase Auth / OAuth
ML Models:       sentence-transformers/all-MiniLM-L6-v2, spaCy NER
PDF Parsing:     pdfplumber, PyMuPDF, python-docx
OCR (Optional):  pytesseract, Google Cloud Vision
Hosting:         Streamlit Cloud
CI/CD:           GitHub → Streamlit Cloud auto-deploy
```

---

## Appendix B: Key Files to Create

```
project/
├── app.py                    # Main Streamlit application
├── requirements.txt          # Dependencies
├── .streamlit/
│   └── secrets.toml          # API keys (local dev only)
├── data/
│   ├── market_standards.json # Job category benchmarks
│   └── learning_resources.json# Curated courses/tutorials
├── models/
│   └── (cached on first run)
├── utils/
│   ├── parser.py             # PDF/DOCX extraction
│   ├── analyzer.py           # BERT/SVM processing
│   ├── skill_matcher.py      # Gap analysis logic
│   └── visualizations.py     # Charts and graphs
├── pages/
│   ├── 1_upload.py           # Upload flow
│   ├── 2_review.py           # Edit extracted data
│   ├── 3_dashboard.py        # Main results
│   ├── 4_growth.py           # Historical tracking
│   └── admin.py              # Secret admin page
└── tests/
    └── sample_resumes/       # Test PDFs
```

---

## Appendix C: Secrets Configuration

**.streamlit/secrets.toml (Local Development):**
```toml
# ⚠️ Add to .gitignore - NEVER commit

[supabase]
url = "https://your-project.supabase.co"
anon_key = "your_anon_key"
service_role_key = "your_service_role_key"

[app]
callback_url = "http://localhost:8501/"
environment = "development"

[admin]
# Generate with: python -c "import hashlib; print(hashlib.sha256('your_password'.encode()).hexdigest())"
password_hash = "sha256_hash_of_admin_password"

[youtube_api]
key = ""  # Optional - for dynamic learning resources
```

**Streamlit Cloud Secrets (Production):**
- Configure via Dashboard → Settings → Secrets
- Same structure as local, with production values
- Secrets auto-injected at runtime via `st.secrets`

**.gitignore entries:**
```
# Secrets - NEVER commit
.streamlit/secrets.toml
*.env
.env.*

# Cache
__pycache__/
*.pyc
.pytest_cache/

# Models (downloaded at runtime)
models/
*.pkl
*.joblib

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
```

---

**Document Status**: ✅ Complete - Ready for Implementation  
**Last Updated**: 2026-01-12  
**Version**: 2.0 (with full technical details)
