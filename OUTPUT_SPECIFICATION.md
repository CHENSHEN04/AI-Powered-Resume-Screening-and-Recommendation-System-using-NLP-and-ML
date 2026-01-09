# AI-Powered Resume Screening System - Output Specification

> **Document Version**: 1.0  
> **Last Updated**: 2026-01-10  
> **Status**: Requirements Complete - Ready for Implementation

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
│                         INPUT LAYER                                  │
├─────────────────────────────────────────────────────────────────────┤
│  Supported Formats: PDF, DOCX (1-2 pages, max 5-10MB)               │
│  Parsing Stack:                                                      │
│   ├── PDF: pdfplumber, PyMuPDF (fitz)                               │
│   ├── DOCX: python-docx                                              │
│   ├── OCR (Secondary): pytesseract, Google Cloud Vision              │
│   ├── NER: spaCy (en_core_web_sm) or custom model                   │
│   └── Fallback: textract                                             │
│  File Validation: magic library for MIME type verification          │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    HYBRID PROCESSING LAYER                           │
├─────────────────────────────────────────────────────────────────────┤
│  Model Integration: CASCADE APPROACH                                 │
│   Step 1: TF-IDF/SVM fast filter (<50ms)                            │
│   Step 2: BERT semantic ranking for top candidates (100-200ms)       │
│   Step 3: Combined score with configurable weights                   │
│                                                                      │
│  Recommended Model: sentence-transformers/all-MiniLM-L6-v2          │
│   - 22M parameters, ~20ms latency, optimized for semantic similarity│
│                                                                      │
│  Skill-Gap Pipeline:                                                 │
│   1. Extract skills using NER + keyword matching                     │
│   2. Compare against Market Standard JSON database                   │
│   3. Detect "Skill Clusters" for missing link analysis              │
│   4. Calculate gap score + generate coaching recommendations         │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         OUTPUT LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│  Framework: Streamlit (Desktop-first hybrid)                         │
│  Visualization: Radar Chart + Checklist + Action Cards              │
│  Explainability: SHAP, LIME, Attention Visualization                │
│  Export: PDF Career Roadmap                                          │
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

---

## 3. Data Architecture

### 3.1 Three-Layer Storage Model (Supabase)

| Layer | Content | Storage Type | Purpose |
|-------|---------|--------------|---------|
| **Source** | Original PDF/DOCX files | Supabase Storage (GCS) | Audit trail, re-parsing |
| **Analytical** | Extracted JSON (skills, education, experience) | PostgreSQL | Skill-gap analysis, recommendations |
| **Historical** | Resume Score snapshots per upload | PostgreSQL | Growth tracking, progress visualization |

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
│  LANDING PAGE                                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │           [Upload Your Resume]  ← Primary CTA               │    │
│  │                                                              │    │
│  │           Already have an account? [Login]                   │    │
│  └─────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  ANONYMOUS UPLOAD (No login required)                                │
│                                                                      │
│  1. User uploads PDF/DOCX                                           │
│  2. Prompted for Target Job Category                                │
│  3. System parses and shows "TEASER" analysis:                      │
│     ┌─────────────────────────────────────────────────────────────┐ │
│     │ "Your Technical Score is 75%! We found 3 missing keywords  │ │
│     │  for your target role. [Claim Profile to see full analysis]"│ │
│     └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  REVIEW SCREEN (Before saving profile)                               │
│  ┌────────────────────────┬────────────────────────────────────┐    │
│  │   ORIGINAL PDF         │   EXTRACTED DATA (Editable)        │    │
│  │   (Left Panel)         │   (Right Panel)                    │    │
│  │                        │                                    │    │
│  │   [PDF Preview]        │   Name: [___________] ✅           │    │
│  │                        │   Email: [__________] ⚠️ Needs check│    │
│  │                        │   Grad Year: [______] ❓ Conflict   │    │
│  │                        │   Skills: [Tag Cloud with ratings]  │    │
│  │                        │                                    │    │
│  │                        │   [+ Add Missing Section]           │    │
│  └────────────────────────┴────────────────────────────────────┘    │
│                                                                      │
│  Features:                                                           │
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

### 6.2 Model Loading Strategy

```python
@st.cache_resource
def load_model():
    # Cached lazy loading - loads once, shared across sessions
    with st.spinner("Loading AI models..."):
        return SentenceTransformer('all-MiniLM-L6-v2')
```

**Recommendations:**
- Use DistilBERT/MiniLM to save RAM
- Always show `st.spinner` during loading
- Add "Reset Session" button for demo emergencies

### 6.3 Market Standards Database

**Source**: Preprocessed from HuggingFace dataset + manual validation

```json
// market_standards.json
{
  "Junior Frontend Developer": {
    "required_skills": ["JavaScript", "React", "CSS", "HTML", "Git"],
    "recommended_skills": ["TypeScript", "Testing", "Next.js"],
    "market_context": "Malaysia/Singapore 2026"
  }
}
```

**Update Cadence**: Static for thesis; monthly refresh for production

### 6.4 Learning Resources Database

**Hybrid Approach:**
- **Core Skills**: Hardcoded high-quality links (FreeCodeCamp, Harvard CS50)
- **Long-Tail**: Dynamic API (YouTube Data API, Coursera API) with safety filter

**Link Rot Prevention:**
- Weekly GitHub Action to ping all URLs
- Auto-hide flagged links (404/500)
- "Report Broken Link" button for users

### 6.5 Logging & Monitoring

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

**Document Status**: ✅ Complete - Ready for Implementation Planning
