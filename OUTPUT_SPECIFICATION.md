# AI-Powered Resume Screening System - Output Specification

> **Document Version**: 3.0 (Pivot to Career Coach)
> **Last Updated**: 2026-02-08
> **Status**: Implementation Phase

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
   - 2.1 Three-Layer Architecture
   - 2.2 Model Decision Logic (Accuracy First)
   - 2.3 Training Data & Model Pipeline
3. [Data Architecture](#3-data-architecture)
   - 3.1 Storage & Schema
   - 3.2 Dynamic Skill Gap Analysis (Model-Based)
   - 3.3 Skill Rating System
4. [User Experience Flow](#4-user-experience-flow)
   - 4.1 Teaser Marketing Funnel
   - 4.2 Main Dashboard ("Coach" Persona)
5. [Edge Case Handling](#5-edge-case-handling)
6. [Technical Implementation](#6-technical-implementation)
   - 6.1 Deployment Stack
   - 6.2 Learning Resources
   - 6.3 Logging & Error Handling
7. [Evaluation Metrics](#7-evaluation-metrics)
8. [Future Roadmap](#8-future-roadmap)

---

## 1. Executive Summary

### 1.1 Project Vision
A **"Deep Career Coach"** for students and fresh graduates. Unlike traditional ATS filters that prioritize speed, this system prioritizes **insight and accuracy**. It acts as a mentor, analyzing resumes against dynamic market standards to provide actionable advice on how to bridge skill gaps.

### 1.2 Core Value Proposition
-   **Depth > Speed**: Users are willing to wait (5-10s) for high-quality, personalized feedback.
-   **Dynamic Market Standards**: Uses AI to understand evolving job requirements, not just static lists.
-   **"Teaser" Funnel**: Frictionless onboarding that proves value before asking for commitment.
-   **Transparency**: Explains *why* a resume fits (or doesn't fit) a role.

### 1.3 Target Users
| User Type | Primary Goals |
|-----------|---------------|
| University Students | Identify what to learn *next* to get an internship. |
| Fresh Graduates | optimize their resume to beat the ATS for specific roles. |
| Career Switchers | Map existing skills to new domains (Feature: Skill Transferability). |

---

## 2. System Architecture

### 2.1 Three-Layer Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│  Supported Formats: PDF, DOCX (1-2 pages recommended, max 10MB)      │
│  Validation:                                                        │
│   ├── MIME type check (python-magic) to prevent extension spoofing  │
│   ├── Password protection check (reject if locked)                  │
│   └── Page Count Warning: If > 3 pages, warn user "Recruiters       │
│       prefer 1-2 pages."                                            │
│  Parsing Stack:                                                     │
│   ├── PDF: pdfplumber, PyMuPDF (fitz)                               │
│   ├── DOCX: python-docx                                             │
│   └── Fallback: OCR (Tesseract) for scanned documents               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    INTELLIGENT PROCESSING LAYER                     │
├─────────────────────────────────────────────────────────────────────┤
│  1. Classification (Hybrid):                                        │
│     - TF-IDF/SVM for broad category filtering (fast).               │
│     - BERT/Transformer for semantic nuance.                         │
│     - *Fallback*: If BERT fails/times out, degrade gracefully to    │
│       SVM-only results (Silver Standard).                           │
│                                                                     │
│  2. Dynamic Skill Gap Analysis (The "Coach"):                       │
│     - Extract skills from resume.                                   │
│     - Query Model/Embeddings: "What are the standard skills for     │
│       [Predicted Role] that [Resume Skills] is missing?"            │
│     - Calculate "Hireability Score" based on critical missing gaps. │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                                │
├─────────────────────────────────────────────────────────────────────┤
│  Framework: Streamlit (React-like interactivity)                    │
│  Interface: "Teaser" Landing → "Deep Dive" Dashboard                │
│  Features:                                                          │
│   - Skill Graph (Visualizing strengths/weaknesses)                  │
│   - Actionable Todo List ("Learn PyTorch", "Fix Resume Header")     │
│   - PDF Report Generation                                           │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Model Decision Logic (Accuracy First)

**Priority:** Accuracy > Speed.

1.  **Ensemble Classification**: Combine SVM probabilities with BERT similarity scores.
2.  **Ranking & Tie-Breaking**:
    *   Rank results by confidence score.
    *   Display **Top 3** matches to the user.
    *   *Tie-Breaker*: If top 2 scores are within 5% of each other, present both as equal options ("Twice the opportunity!").
3.  **Confidence Threshold**:
    *   If Confidence > 85%: Auto-select role.
    *   If Confidence < 85%: **Ask User** ("We think you're a *Data Analyst*, is that right?").
    *   *Override*: Always allow user to manually select specific target role to compare against, regardless of auto-match.

### 2.3 Training Data & Model Pipeline

*   **Dataset**: `ahmedheakl/resume-atlas` (HuggingFace).
*   **Preprocessing**: Text cleaning, lemmatization.
    *   *Multi-language*: Extract text -> Detect Language -> Translate to English -> Process.
    *   *Localization*: Manually add local requirements (e.g., "PDPA" for Malaysia data roles) to `market_standards.json`.
*   **Runtime**: Models loaded once via `@st.cache_resource` (Lazy Loading).

---

## 3. Data Architecture

### 3.1 Storage Model (Supabase)

| Table | Purpose |
|-------|---------|
| `users` | Auth & Profile data. |
| `resumes` | Metadata, parsed text, and scores. |
| `analysis_results` | Detailed breakdown of gaps and recommendations. |
| `skills` | (Minimal) Known canonical skills for auto-complete. |
| `learning_resources` | Curated links for specific skills. |

### 3.2 Dynamic Skill Gap Analysis (Model-Based)

Instead of a static SQL table of "Required Skills" (which goes stale), we use a **Hybrid Approach**:

1.  **Core Canon (Static)**: Hard-coded "Must Haves" for top 20 roles (e.g., Data Scientist = Python, SQL).
2.  **Dynamic Expansion (Embedding-based)**:
    *   Compute user's skill vector $V_{user}$.
    *   Compare against the average vector of the target role $V_{role}$.
    *   identify semantic "holes" in the vector space.
    *   *Implementation*: `semantic_matcher.py` uses `SentenceTransformer` to find distance between "User Skills" and "Role Description".

### 3.3 Skill Rating System & "Reality Check"

**Logic**:
1.  **Extraction**: Get list of skills and self-ratings.
    *   *Section weights (Student Focus)*: Education/Skills (1.0) > Projects (0.9) > Work Experience (0.6).
    *   *Temporal Logic*: No decay. Old skills treated as valid (assume lifelong learning).
2.  **Normalization**: 
    *   Convert all ratings to 1-5 scale.
    *   *Term Mapping*: "Novice/Beginner" -> 1, "Competent/Intermediate" -> 3, "Proficient/Advanced" -> 4, "Expert/Master" -> 5.
    *   *Default*: If skill is listed but no level provided, **Default = 3** (Competent).
3.  **Student Dampening Factor (The "Reality Check")**:
    *   *Scenario*: User claims "Expert" (5/5) in Java but only lists it in "Coursework".
    *   *Action*: Internally treat as "Beginner" (2/5) for matching.
    *   *Feedback*: "You rated yourself 'Expert', but we only found academic experience. Recruiters may see this as 'Beginner'. Add a complex project to back this up!"
4.  **Scoring Matrix**:
    *   **Found in Resume**: 100% match (after dampening).
    *   **Inferred**: (e.g., used "Pandas" -> infer "Python") 80% confidence.
    *   **Missing**: 0% (Gap).

### 3.4 Job Category & "Other" Handling

**Custom Job Logic**:
1.  **UI**: Dropdown with "Other" option -> Text Input.
2.  **Semantic De-duplication**:
    *   When user submits "ML Engineer", system computes embedding.
    *   If similarity > 0.9 with existing "Machine Learning Engineer", ask: *"Did you mean 'Machine Learning Engineer'?"*
    *   If confirmed unique, save to `pending_job_categories`.
3.  **Admin Review**: Monthly manual review to promote `pending` -> `official`.

---

## 4. User Experience Flow

### 4.1 "Teaser" Marketing Funnel (Critical)

The goal is to show value *before* requiring signup.

**Step 1: The Hook (Landing Page)**
*   UI: Clean, minimal. "Upload Resume to see your Hireability Score."
*   *Builder Mode*: If resume is empty (< 50 words), switch to "Character Creation" mode. Ask 3 rapid-fire questions ("Dream Job?", "Current Major?", "Hobbies?") to seed the analysis.

**Step 2: The Teaser (Anonymous)**
*   System: Parses, classifies, and computes *basic* score.
*   UI:
    *   **"Your Resume Score: 78/100"** (Big, animated number).
    *   **"Top Match: Data Scientist"**.
    *   **"Critical Gaps: We found 3 missing 'Must-Have' skills for this role..."** (Pixelated/Blurred list).
    *   CTA: "Unlock Full Report & Personal Study Plan (Free)".

**Step 3: Conversion (Auth)**
*   User signs up (Email/Google).
*   System: Merges anonymous upload ID with new User ID.

**Step 4: The Unveil (Dashboard)**
*   UI reveals the blurred content.
*   Shows full analysis.

### 4.2 Main Dashboard ("Coach" Persona)

**Tone**: Encouraging, specific, actionable.

**Sections**:
1.  **The Diagnosis**: "You are a strong candidate for *Junior Developer*, but your lack of *Docker* is holding you back."
2.  **Skill Radar**: Visualizes "You" vs "Market Average".
3.  **The Prescription (Action Plan)**:
    *   High Priority: "Learn Docker fundamentals (est. 4 hours)."
    *   Medium Priority: "Add a project description for your SQL work."
4.  **Growth Tracking**: "You've improved 15% since last upload!"
    *   *Gamification*: "Badges" for closing gaps (e.g., "SQL Slayer").
    *   *Metrics*: Gap Reduction %, Score History.

### 4.3 Responsive Design Strategy
*   **Desktop**: Split-view (PDF left, Data right) for review. Three-column dashboard.
*   **Mobile**: Stacked layout. Use `st.expander` heavily to save space. PDF preview hidden behind "View Resume" button.

---

## 5. Edge Case Handling

| Edge Case | Handling Strategy |
|-----------|-------------------|
| **Low Confidence / Verification** | **Critical Field Modal**: If Name/Email confidence < 30%, force modal confirmation before proceeding. |
| **Parsing Failure (Scanned PDF)** | Show error: "We can't read scanned images yet. Please upload a digital PDF." (OCR fallback secondary). |
| **Empty/Junk File** | Trigger **Builder Mode** (Manual input wizard). |
| **Missing "Required" Section** | If no "Education" found, prompt user: "Did we miss your education? Add it manually." |
| **Conflicting Dates** | **Heuristics**: Trust 'Education' over 'Summary'. If conflict persists, show UI Flag with Radio Button toggle. |

---

## 6. Technical Implementation

### 6.1 Deployment Stack
*   **Frontend**: Streamlit.
    *   *Development Tool*: **Stitch MCP** (Google Stitch) for rapid UI generation and design iteration.
*   **Compute**: Python 3.9+, standard CPU.
    *   *Resiliency*: "Fallback Pipeline" - if BERT times out, return partial results (basic parsing) with "Refresh" option.
*   **Database**: Supabase (PostgreSQL).
*   **Storage**: Supabase Storage (for raw PDF retention).

### 6.2 Learning Resources
*   **Table**: `learning_resources`
*   **Fields**: `skill_name`, `url`, `type` (Course/Article/Video), `difficulty`.
*   **Population**: Mixed.
*   **Population**: Mixed.
    *   Top 50 skills: Manually curated high-quality links.
    *   Tail skills: Generic search query link ("Learn [Skill] on FreeCodeCamp").
    *   *Maintenance*: Weekly "Link Rot" script checking for 404s. User "Upvote/Downvote" on quality.

### 6.3 Logging & Error Handling
*   **Log Everything**: Store parser failures in `system_logs`.
*   **Admin Dashboard**: Secret URL (`/admin`) to view Fail-Log and user stats (DAU, Parsing Time).
*   **User Feedback**: "Report Issue" button.

---

## 7. Evaluation Metrics

**Success = Accuracy + Usefulness.**

1.  **Classification Accuracy**: % of resumes assigned to the correct "Human Truth" job category. (Target: >85%).
2.  **Gap Detection Rate**: "Did the system correctly identify that I was missing Skill X?" (Target: Precision > 80%).
3.  **Conversion Rate**: % of Anonymous Uploads that convert to Registered Users.

---

## 8. Future Roadmap

1.  **LLM Integration**: Replace static logic with a small LLM (e.g., Llama-3-8B) for generating conversational advice.
2.  **Interview Prep**: Generate custom interview questions based on the specific gaps found.
3.  **Resume Rewriter**: "Click to rewrite this bullet point."
