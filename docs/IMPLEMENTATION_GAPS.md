# Implementation Gap Analysis & Solutions

> **Document Version**: 1.0  
> **Created**: 2026-01-12  
> **Purpose**: Address gaps identified in OUTPUT_SPECIFICATION.md before development begins

---

## Table of Contents
1. [Database Schema Definitions](#1-database-schema-definitions)
2. [Supabase Authentication Flow](#2-supabase-authentication-flow)
3. [Complete Market Standards Database](#3-complete-market-standards-database)
4. [Error Handling Standards](#4-error-handling-standards)
5. [Test Strategy](#5-test-strategy)
6. [Deployment Constraints & Memory](#6-deployment-constraints--memory)
7. [Security & Rate Limiting](#7-security--rate-limiting)
8. [Secrets Configuration Template](#8-secrets-configuration-template)

---

## 1. Database Schema Definitions

### 1.1 Entity Relationship Diagram

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

### 1.2 SQL Table Definitions

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

-- Index for fast email lookup
CREATE INDEX idx_users_email ON users(email);

-- ============================================
-- RESUMES TABLE
-- ============================================
CREATE TABLE resumes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    
    -- File metadata
    original_filename VARCHAR(255) NOT NULL,
    storage_path TEXT NOT NULL,           -- Supabase Storage path
    file_size_bytes INTEGER,
    page_count INTEGER,
    mime_type VARCHAR(100),
    
    -- Extracted personal info
    extracted_name VARCHAR(200),
    extracted_email VARCHAR(255),
    extracted_phone VARCHAR(50),
    graduation_year INTEGER,
    education_level VARCHAR(50),          -- 'high_school', 'bachelor', 'master', 'phd'
    field_of_study VARCHAR(200),
    
    -- Processing metadata
    parse_confidence DECIMAL(3,2),        -- 0.00 to 1.00
    processing_status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    parser_version VARCHAR(20),
    
    -- Timestamps
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    processed_at TIMESTAMP WITH TIME ZONE,
    
    -- Version tracking (for growth comparison)
    version_number INTEGER DEFAULT 1,
    is_latest BOOLEAN DEFAULT TRUE
);

-- Indexes
CREATE INDEX idx_resumes_user_id ON resumes(user_id);
CREATE INDEX idx_resumes_status ON resumes(processing_status);
CREATE INDEX idx_resumes_latest ON resumes(user_id, is_latest) WHERE is_latest = TRUE;

-- ============================================
-- SKILLS TABLE (Master list)
-- ============================================
CREATE TABLE skills (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    canonical_name VARCHAR(100),          -- Normalized form (e.g., "JavaScript" for "JS")
    category VARCHAR(50),                 -- 'programming', 'framework', 'soft_skill', 'tool'
    aliases TEXT[],                       -- ['JS', 'Javascript', 'ECMAScript']
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
    
    -- Proficiency
    self_rated_level INTEGER CHECK (self_rated_level BETWEEN 1 AND 5),
    inferred_level INTEGER CHECK (inferred_level BETWEEN 1 AND 5),
    final_level INTEGER CHECK (final_level BETWEEN 1 AND 5),
    
    -- Source tracking
    source_section VARCHAR(50),           -- 'skills', 'experience', 'projects', 'education'
    years_experience DECIMAL(3,1),
    extraction_confidence DECIMAL(3,2),
    
    -- User validation
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
    slug VARCHAR(100) NOT NULL UNIQUE,    -- 'junior-frontend-developer'
    display_name VARCHAR(150),            -- 'Junior Frontend Developer'
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
    
    importance_level VARCHAR(20) NOT NULL, -- 'required', 'recommended', 'nice_to_have'
    market_demand_percentage INTEGER,      -- 0-100, % of job postings requiring this
    min_proficiency_level INTEGER CHECK (min_proficiency_level BETWEEN 1 AND 5),
    
    market_context VARCHAR(100),           -- 'Malaysia/Singapore 2026'
    source VARCHAR(255),                   -- 'LinkedIn Job Postings Analysis'
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
    
    -- Scores
    overall_score INTEGER CHECK (overall_score BETWEEN 0 AND 100),
    svm_confidence DECIMAL(4,3),
    bert_similarity DECIMAL(4,3),
    combined_score DECIMAL(4,3),
    
    -- Classification results
    top_matches JSONB,                     -- [{category_id, score, rank}, ...]
    
    -- Gap analysis
    matching_skills_count INTEGER,
    missing_skills_count INTEGER,
    total_required_skills INTEGER,
    gap_details JSONB,                     -- Detailed skill gaps
    
    -- Recommendations
    recommendations JSONB,
    
    -- Performance metrics
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
    provider VARCHAR(100),                 -- 'FreeCodeCamp', 'Coursera', 'YouTube'
    url TEXT NOT NULL,
    resource_type VARCHAR(50),             -- 'course', 'tutorial', 'video', 'article', 'project'
    difficulty_level VARCHAR(20),          -- 'beginner', 'intermediate', 'advanced'
    estimated_hours DECIMAL(5,1),
    is_free BOOLEAN DEFAULT TRUE,
    
    -- Link health
    last_checked_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================
-- SYSTEM_LOGS TABLE
-- ============================================
CREATE TABLE system_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    
    event_type VARCHAR(50) NOT NULL,       -- 'upload', 'parse', 'analyze', 'error'
    severity VARCHAR(20) DEFAULT 'info',   -- 'debug', 'info', 'warning', 'error', 'critical'
    
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
    
    message TEXT,
    error_code VARCHAR(50),
    stack_trace TEXT,
    metadata JSONB,
    
    -- Performance metrics
    processing_stage VARCHAR(50),
    duration_ms INTEGER,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_logs_type ON system_logs(event_type);
CREATE INDEX idx_logs_severity ON system_logs(severity);
CREATE INDEX idx_logs_created ON system_logs(created_at DESC);

-- ============================================
-- USER_SESSIONS TABLE (for anonymous tracking)
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

### 1.3 Supabase Storage Path Convention

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

---

## 2. Supabase Authentication Flow

### 2.1 Authentication Methods

| Method | Use Case | Implementation |
|--------|----------|----------------|
| **Anonymous** | First-time users trying the product | Auto-create anonymous user, upgrade later |
| **Email Magic Link** | "Claim Profile" flow | Supabase `signInWithOtp()` |
| **Google OAuth** | Returning users, convenience | Supabase `signInWithOAuth()` |

### 2.2 Flow Diagrams

```
┌───────────────────────────────────────────────────────────────────────────┐
│                        ANONYMOUS → CLAIMED USER FLOW                       │
├───────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  Landing Page                                                             │
│       │                                                                   │
│       ▼                                                                   │
│  [Upload Resume] ─────────────────────────────────────────────┐          │
│       │                                                        │          │
│       ▼                                                        │          │
│  Create Anonymous User ───────► session_id stored in          │          │
│  (Supabase Auth)                st.session_state              │          │
│       │                                                        │          │
│       ▼                                                        │          │
│  Resume Processing ──────────► Results stored with            │          │
│       │                        user_id = anon_user_id         │          │
│       ▼                                                        │          │
│  Show Teaser Results                                          │          │
│       │                                                        │          │
│       ▼                                                        │          │
│  [Claim Profile] Button ◄─────────────────────────────────────┘          │
│       │                                                                   │
│       ├──► Email Magic Link ──► Verify ──► Link anon to email           │
│       │                                                                   │
│       └──► Google OAuth ──────► Callback ──► Merge anon user            │
│                                              with Google user            │
│                                                                           │
└───────────────────────────────────────────────────────────────────────────┘
```

### 2.3 Python Implementation (auth.py)

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
        # Create anonymous user via Supabase Auth
        response = supabase.auth.sign_in_anonymously()
        st.session_state.user_id = response.user.id
        st.session_state.is_anonymous = True
    
    return st.session_state.user_id

def claim_profile_email(email: str):
    """Upgrade anonymous user to email-based account."""
    supabase = init_supabase()
    
    # Send magic link
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
    return response.url  # Redirect user to this URL

def handle_auth_callback():
    """Process OAuth callback and merge anonymous data."""
    supabase = init_supabase()
    
    # Get session from URL parameters
    session = supabase.auth.get_session()
    
    if session and st.session_state.get("is_anonymous"):
        # Merge anonymous user's data to new authenticated user
        old_user_id = st.session_state.user_id
        new_user_id = session.user.id
        
        # Update all resumes and results
        supabase.table("resumes").update({
            "user_id": new_user_id
        }).eq("user_id", old_user_id).execute()
        
        # Mark anonymous user as merged
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

### 2.4 Callback URL Configuration

**Supabase Dashboard Settings:**
```
Site URL: https://your-app.streamlit.app
Redirect URLs:
  - https://your-app.streamlit.app/
  - https://your-app.streamlit.app/?callback=auth
  - http://localhost:8501/ (for local dev)
```

**Google Cloud Console (for OAuth):**
```
Authorized JavaScript origins:
  - https://your-app.streamlit.app
  - http://localhost:8501

Authorized redirect URIs:
  - https://<your-project>.supabase.co/auth/v1/callback
```

---

## 3. Complete Market Standards Database

### 3.1 JSON Structure (market_standards.json)

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

---

## 4. Error Handling Standards

### 4.1 Error Code System

| Code Range | Category | Example |
|------------|----------|---------|
| `E1xxx` | File Upload Errors | E1001 - Invalid file type |
| `E2xxx` | Parsing Errors | E2001 - PDF extraction failed |
| `E3xxx` | Analysis Errors | E3001 - BERT model timeout |
| `E4xxx` | Database Errors | E4001 - Connection failed |
| `E5xxx` | Authentication Errors | E5001 - Session expired |

### 4.2 Error Definition (errors.py)

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

### 4.3 Streamlit Error Display Component

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
        
        # Add retry button for recoverable errors
        if error.recoverable:
            if st.button("🔄 Try Again", key=f"retry_{error.code.value}"):
                st.rerun()
        
        # Show error code for support reference
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

---

## 5. Test Strategy

### 5.1 Test Framework & Structure

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

### 5.2 Test Commands

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

### 5.3 Sample Test Cases (test_parser.py)

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
    
    # ========== PDF Tests ==========
    
    def test_parse_simple_pdf(self, parser):
        """Test parsing a simple one-page PDF."""
        result = parser.parse(SAMPLE_DIR / "valid/simple_one_page.pdf")
        
        assert result.success is True
        assert result.extracted_name is not None
        assert len(result.skills) > 0
        assert result.confidence >= 0.7
    
    def test_parse_complex_pdf(self, parser):
        """Test parsing a multi-section PDF with projects."""
        result = parser.parse(SAMPLE_DIR / "valid/complex_two_page.pdf")
        
        assert result.success is True
        assert result.education is not None
        assert len(result.projects) >= 1
    
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
    
    # ========== DOCX Tests ==========
    
    def test_parse_docx(self, parser):
        """Test parsing a DOCX file."""
        result = parser.parse(SAMPLE_DIR / "valid/sample.docx")
        
        assert result.success is True
        assert result.extracted_name is not None
    
    # ========== Edge Cases ==========
    
    def test_parse_minimal_resume(self, parser):
        """Test parsing resume with minimal content."""
        result = parser.parse(SAMPLE_DIR / "valid/minimal_student.pdf")
        
        assert result.success is True
        assert result.builder_mode_triggered is True  # < 3 skills
    
    def test_parse_bloated_resume(self, parser):
        """Test handling of 10+ page resume."""
        result = parser.parse(SAMPLE_DIR / "edge_cases/ten_pages.pdf")
        
        assert result.success is True
        assert result.page_count_warning is True
    
    def test_parse_unicode_resume(self, parser):
        """Test handling of Unicode characters in resume."""
        result = parser.parse(SAMPLE_DIR / "edge_cases/unicode_characters.pdf")
        
        assert result.success is True
        # Should not crash on special characters

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
        
        assert "JavaScript" in skills  # Normalized from "JS"
        assert "React" in skills        # Normalized from "React.js"
        assert "PostgreSQL" in skills   # Normalized from "Postgres"
    
    def test_proficiency_extraction(self, extractor):
        """Test extraction of proficiency levels."""
        text = "Expert in Python, Beginner in Go"
        
        skills = extractor.extract_with_proficiency(text)
        
        assert skills["Python"]["level"] == 5
        assert skills["Go"]["level"] == 2
```

### 5.4 Manual Testing Checklist

```markdown
# Manual Testing Checklist

## Upload Flow
- [ ] Upload valid PDF → see processing spinner → results displayed
- [ ] Upload valid DOCX → same flow works
- [ ] Upload unsupported file (e.g., .txt) → see clear error message
- [ ] Upload file > 10MB → see file size error BEFORE upload completes
- [ ] Upload password-protected PDF → see "remove password" message

## Review Screen
- [ ] PDF preview displays correctly in left panel
- [ ] Extracted fields show on right panel
- [ ] Low-confidence fields (< 0.7) highlighted in orange
- [ ] Can edit extracted name → change persists
- [ ] "Add Missing Section" button opens input form
- [ ] Undo/Redo buttons work correctly

## Dashboard
- [ ] Resume Score displays prominently
- [ ] Top 3 job matches shown with percentages
- [ ] Clicking a job match shows skill gaps
- [ ] Radar chart renders with user vs. market data
- [ ] Skill gap checklist shows ✅/⚠️/❌ icons correctly
- [ ] Recommendations expand on click

## Authentication
- [ ] Anonymous upload → results visible
- [ ] "Claim Profile" → email input appears
- [ ] Magic link email received and works
- [ ] Google OAuth login works
- [ ] Logout clears session
- [ ] Returning user sees previous upload history

## Error Recovery
- [ ] Network disconnect during upload → retry button works
- [ ] BERT timeout → fallback message shown
- [ ] "Refresh Full Analysis" button works
```

---

## 6. Deployment Constraints & Memory

### 6.1 Streamlit Cloud Limits

| Resource | Free Tier Limit | Impact |
|----------|----------------|--------|
| **Memory** | 1 GB RAM | Models must fit in memory |
| **CPU** | Shared | No GPU for BERT |
| **Storage** | Ephemeral | Models re-download on restart |
| **Timeouts** | 10 min inactive | Session state may be lost |
| **Concurrent Users** | ~5-10 (soft limit) | May need to queue requests |

### 6.2 Memory Budget Breakdown

```
┌─────────────────────────────────────────────────┐
│           MEMORY BUDGET (1GB Limit)              │
├─────────────────────────────────────────────────┤
│                                                  │
│  Base Streamlit             ~150 MB              │
│  Python + Dependencies      ~200 MB              │
│  spaCy en_core_web_sm       ~ 12 MB              │
│  all-MiniLM-L6-v2           ~ 90 MB              │
│  TF-IDF Vectorizer (fitted) ~ 30 MB              │
│  SVM Model (fitted)         ~ 20 MB              │
│  ─────────────────────────────────               │
│  Subtotal (Fixed)           ~502 MB              │
│                                                  │
│  Available for Processing   ~498 MB              │
│  └── Per-request overhead   ~ 50 MB              │
│  └── Safety buffer          ~200 MB              │
│                                                  │
└─────────────────────────────────────────────────┘
```

### 6.3 Memory Optimization Strategies

```python
# config.py

MEMORY_CONFIG = {
    # Use smaller spaCy model
    "spacy_model": "en_core_web_sm",  # NOT en_core_web_lg (700MB)
    
    # Use sentence-transformers quantized model
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
    
    # Lazy loading
    "lazy_load_bert": True,  # Only load when needed
    
    # Batch processing
    "max_batch_size": 1,  # Process one resume at a time
    
    # Garbage collection
    "force_gc_after_analysis": True,
    
    # Model caching strategy
    "cache_models_in_session": True,  # @st.cache_resource
}
```

### 6.4 Model Loading with Memory Management

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
        # Download on first run
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

### 6.5 Scalability Considerations

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCALING STRATEGY                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PHASE 1: Thesis Demo (Current)                                 │
│  └── Streamlit Cloud Free Tier                                  │
│  └── 5-10 concurrent users max                                  │
│  └── All models local                                           │
│                                                                  │
│  PHASE 2: University Pilot                                      │
│  └── Streamlit Cloud Basic ($5/month)                           │
│  └── 50+ concurrent users                                       │
│  └── Consider async processing queue                            │
│                                                                  │
│  PHASE 3: Production (Future)                                   │
│  └── FastAPI backend + React frontend                           │
│  └── Celery for background processing                           │
│  └── Redis for caching                                          │
│  └── BERT via API (HuggingFace Inference Endpoints)            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Security & Rate Limiting

### 7.1 Rate Limiting Configuration

```python
# utils/rate_limiter.py

from datetime import datetime, timedelta
from collections import defaultdict
import streamlit as st

# Rate limits
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
        # In production, use Redis instead of in-memory
        self._requests = defaultdict(list)
    
    def check_rate_limit(self, user_id: str, is_authenticated: bool) -> tuple[bool, str]:
        """Check if user is within rate limits."""
        limits = RATE_LIMITS["authenticated" if is_authenticated else "anonymous"]
        now = datetime.now()
        
        # Get user's request history
        user_requests = self._requests[user_id]
        
        # Clean old entries
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        user_requests = [r for r in user_requests if r > day_ago]
        self._requests[user_id] = user_requests
        
        # Check hourly limit
        recent_hour = [r for r in user_requests if r > hour_ago]
        if len(recent_hour) >= limits["uploads_per_hour"]:
            wait_time = (recent_hour[0] + timedelta(hours=1) - now).seconds // 60
            return False, f"Hourly limit reached. Try again in {wait_time} minutes."
        
        # Check daily limit
        if len(user_requests) >= limits["uploads_per_day"]:
            return False, "Daily limit reached. Please try again tomorrow."
        
        # Record this request
        self._requests[user_id].append(now)
        return True, ""
    
    def get_file_size_limit(self, is_authenticated: bool) -> int:
        """Get max file size in bytes."""
        limits = RATE_LIMITS["authenticated" if is_authenticated else "anonymous"]
        return limits["max_file_size_mb"] * 1024 * 1024

# Global instance
rate_limiter = RateLimiter()
```

### 7.2 Input Validation

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
    
    # Check extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"Invalid file type. Please upload PDF or DOCX files only."
    
    # Check MIME type using magic bytes
    detected_mime = magic.from_buffer(file_bytes[:2048], mime=True)
    if detected_mime not in ALLOWED_MIME_TYPES:
        return False, f"File content doesn't match extension. Please upload a valid {ext} file."
    
    # Sanitize filename
    if len(filename) > MAX_FILENAME_LENGTH:
        return False, f"Filename too long. Maximum {MAX_FILENAME_LENGTH} characters."
    
    return True, ""

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for storage."""
    import re
    # Remove path separators and special characters
    safe = re.sub(r'[^\w\-\.]', '_', filename)
    safe = safe.lower()
    # Limit length
    name, ext = Path(safe).stem, Path(safe).suffix
    if len(name) > 80:
        name = name[:80]
    return f"{name}{ext}"
```

### 7.3 Admin Page Protection

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
            # Hash comparison to avoid timing attacks
            input_hash = hashlib.sha256(password.encode()).hexdigest()
            stored_hash = st.secrets.get("admin", {}).get("password_hash", "")
            
            if input_hash == stored_hash:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("Invalid password.")
        
        st.stop()

# At top of admin page
check_admin_access()
# ... rest of admin page code
```

---

## 8. Secrets Configuration Template

### 8.1 Local Development (.streamlit/secrets.toml)

```toml
# .streamlit/secrets.toml
# ⚠️ NEVER COMMIT THIS FILE TO GIT - Add to .gitignore

[supabase]
url = "https://your-project.supabase.co"
anon_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  # Public anon key
service_role_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."  # Server-side only

[app]
callback_url = "http://localhost:8501/"
environment = "development"

[admin]
# Generate with: python -c "import hashlib; print(hashlib.sha256('your_password'.encode()).hexdigest())"
password_hash = "5e884898da28047d9165..."

[youtube_api]
key = ""  # Optional: for dynamic learning resources

[google_oauth]
client_id = ""
client_secret = ""
```

### 8.2 Production (Streamlit Cloud Secrets)

```
# In Streamlit Cloud Dashboard → Settings → Secrets

[supabase]
url = "https://prod-project.supabase.co"
anon_key = "production_anon_key"
service_role_key = "production_service_role_key"

[app]
callback_url = "https://your-app.streamlit.app/"
environment = "production"

[admin]
password_hash = "production_password_hash"
```

### 8.3 .gitignore Entries

```gitignore
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

## Summary: Insertion Points for OUTPUT_SPECIFICATION.md

| Gap | Section to Insert | Priority |
|-----|------------------|----------|
| Database Schema | Section 3 (Data Architecture) | 🔴 High |
| Supabase Auth Flow | Section 6.1 (Deployment Stack) | 🔴 High |
| Market Standards JSON | Section 6.3 (Market Standards) | 🟡 Medium |
| Error Handling | New Section 6.6 | 🟡 Medium |
| Test Strategy | New Section 6.7 | 🟡 Medium |
| Memory Constraints | Section 6.1 (Deployment Stack) | 🔴 High |
| Rate Limiting | Section 6.1 (Deployment Stack) | 🟡 Medium |
| Secrets Template | Section 6.1 or Appendix | 🟢 Low |

---

**Document Status**: ✅ Ready for Review
