# AI-Powered Resume Screening and Recommendation System

---

## 1. Project Overview

### What is the project about?
> **Vision**: A "Deep Career Coach" for students and fresh graduates.
> **Problem**: Traditional ATS systems are "black boxes" that reject candidates without explanation. Students don't know *why* they failed or what to learn next.
> **Solution**: An AI-powered system that doesn't just "screen" resumes but **coaches** the user. It uses deep semantic analysis to identify skill gaps against dynamic market standards and provides actionable learning paths.

### Core Philosophy
*   **Depth > Speed**: We prioritize accurate, personalized advice over sub-50ms processing.
*   **Transparency**: Users see exactly which skills matched and which are missing.
*   **Growth-Oriented**: The goal isn't just to "score" a resume, but to improve the candidate's hireability.

---

## 2. Architecture & Data

### Dataset
> [!datasetused] **ahmedheakl/resume-atlas**
- **Size**: 24,000+ labeled resumes across 50+ job categories.
- **Use Case**: Training the Classification Model (BERT/Ensemble) to understand "Human Truth" job categories.

### Intelligent Processing
We use a **Hybrid Approach**:
1.  **Classification**: Combines statistical (TF-IDF/SVM) and semantic (BERT) models to accurately predict the user's target role.
2.  **Dynamic Skill Analysis**:
    *   **Old Way**: Checking against a static list of keywords.
    *   **Our Way**: Using Embeddings/LLMs to understand "Contextual Gaps". (e.g., Identifying that a "Data Scientist" needs "PyTorch" even if it wasn't on a static list).

---

## 3. User Experience (The "Teaser" Funnel)

To solve the "Cold Start" problem, we use a value-first onboarding flow:

### Phases
1.  **The Hook (Anonymous)**: User uploads a resume *without* signing up.
2.  **The Teaser**:
    *   Shows a high-level **"Hireability Score"** (e.g., 78/100).
    *   Identifies the **Top Matched Role** (e.g., "Junior Data Scientist").
    *   **Blurs** the detailed feedback to create curiosity.
3.  **The Conversion**: User creates an account to "Unlock Full Report".
4.  **The Deep Dive (Authenticated)**:
    *   **Skill Radar**: Visual strengths/weaknesses.
    *   **Action Plan**: Specific to-dos (e.g., "Add a project using React", "Learn Docker").
    *   **Resource Recommendations**: Curated links to fill identified gaps.

---

## 4. Evaluation Metrics

**Success Definition**:
1.  **Accuracy**: The system must correctly identify the user's domain (e.g., distinguishing "Java Developer" from "Android Developer").
2.  **Gap Detection**: The system must correctly identify missing *critical* skills (e.g., missing "SQL" for a Data Analyst).
3.  **User Trust**: Users should feel the feedback is "fair" and "useful".

---

## 5. Technical Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Frontend** | Streamlit | Rapid, interactive UI development. |
| **Backend** | Python | Core logic (NLP, ML inference). |
| **Database** | Supabase | User auth, persistent storage of profiles & history. |
| **Models** | HuggingFace | `all-MiniLM-L6-v2` (Embeddings), Custom Fine-tuned Classifiers. |
| **Parsing** | PyMuPDF / OCR | Robust extraction from PDF/DOCX. |

---

### ✅ Success Criteria for Next Milestone
- [ ] **Teaser Flow Working**: Anonymous users can upload -> see score -> signup -> see details.
- [ ] **Accuracy**: Classification model achieves >85% F1-score on test set.
- [ ] **Skill Gaps**: System successfully flags missing "Must-Have" skills for top 5 roles.
