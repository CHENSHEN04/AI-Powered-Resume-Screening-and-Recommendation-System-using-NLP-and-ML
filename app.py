"""
AI-Powered Resume Screening and Recommendation System
======================================================
Main Streamlit entry point – implements the "Teaser" funnel:

    Upload → Anonymous Score → Login/Register → Full Report

Flow controlled by `st.session_state["app_stage"]`:
    "upload"    → hero + file uploader + JD input
    "teaser"    → anonymous score card + CTA
    "review"    → split-view data verification
    "dashboard" → full Deep Coach dashboard
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from pathlib import Path

from utils.validators import validate_file
from utils.ui_components import show_error, show_warning
from utils.db_handler import DatabaseManager
from utils.rate_limiter import RateLimiter, show_rate_limit_info
try:
    from utils.ai_assistant import AIAssistant, AIFeedbackGenerator
except ImportError:
    AIAssistant = None
    AIFeedbackGenerator = None


# ==============================================================================
# Page Configuration
# ==============================================================================
st.set_page_config(
    page_title="Deep Career Coach – AI Resume Analyzer",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# Load Theme CSS
# ==============================================================================
CSS_PATH = Path("assets/theme.css")
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

# ==============================================================================
# Session State
# ==============================================================================
DEFAULTS = {
    "user": None,
    "is_anonymous": False,
    "app_stage": "upload",          # upload → teaser → review → dashboard
    "uploaded_file_name": None,
    "file_bytes": None,
    "parse_result": None,
    "skill_data": None,
    "prediction": None,
    "gap_analysis": None,
    "growth_data": None,
    "explanation": None,
    "chat_history": [],
    "target_role": None,
    "reviewed_skills": None,
    # ── NEW: JD fields ──
    "jd_text": "",                  # raw job description input
    "selected_role": None,          # user-chosen role from dropdown
    "custom_role_saved": False,     # whether a custom role was saved this session
    "similar_roles_found": [],      # similar roles found during duplicate check
    "role_creation_confirmed": False, # user confirmed they want a new role despite similar existing
    "jd_match_result": None,        # output from JDMatcher
    "weighted_score_result": None,  # output from weighted_scorer
    "ai_feedback": None,            # output from AIFeedbackGenerator
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================================================================
# Sidebar – Auth + Navigation
# ==============================================================================
@st.cache_resource
def _get_db():
    """Cached DB client — only initialised once per server process."""
    return DatabaseManager()


def render_sidebar():
    db = _get_db()
    with st.sidebar:
        st.markdown("# 🎯 Career Coach")
        st.caption("AI-Powered Resume Analysis")
        st.markdown("---")

        user = st.session_state.get("user")
        is_anon = st.session_state.get("is_anonymous", False)

        if user and not is_anon:
            st.success(f"✅ {user.email}")
            if st.button("🚪 Log Out", use_container_width=True):
                db.sign_out()
                for k in DEFAULTS:
                    st.session_state[k] = DEFAULTS[k]
                st.rerun()
        else:
            if is_anon:
                st.info("👻 Guest Mode")
                st.caption("Sign up to save your history!")
            else:
                if st.button("👻 Continue as Guest", use_container_width=True):
                    class GuestUser:
                        def __init__(self):
                            self.id = "guest_session"
                            self.email = "guest@local"
                    st.session_state["user"] = GuestUser()
                    st.session_state["is_anonymous"] = True
                    st.toast("Entered Guest Mode", icon="👻")
                    st.rerun()

            st.markdown("---")
            auth_mode = st.radio("Account", ["Login", "Sign Up"], horizontal=True)
            with st.form("auth_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                full_name = st.text_input("Full Name") if auth_mode == "Sign Up" else ""
                if st.form_submit_button(auth_mode, use_container_width=True):
                    if auth_mode == "Login":
                        res, err = db.sign_in(email, password)
                        if err:
                            st.error(err)
                        else:
                            st.session_state["user"] = res.user
                            st.session_state["is_anonymous"] = False
                            if st.session_state.get("gap_analysis"):
                                st.session_state["app_stage"] = "dashboard"
                            st.rerun()
                    else:
                        res, err = db.sign_up(email, password, full_name)
                        if err:
                            st.error(err)
                        else:
                            st.success("📧 Verification email sent!")

        st.markdown("---")
        stages = {"upload": "1️⃣ Upload", "teaser": "2️⃣ Preview",
                  "review": "3️⃣ Review", "dashboard": "4️⃣ Dashboard"}
        current = st.session_state["app_stage"]
        for key, label in stages.items():
            if key == current:
                st.markdown(f"**▶ {label}**")
            else:
                st.caption(f"  {label}")

        if st.session_state["app_stage"] != "upload":
            st.markdown("---")
            if st.button("🔄 New Analysis", use_container_width=True):
                for k in DEFAULTS:
                    st.session_state[k] = DEFAULTS[k]
                st.session_state["user"] = user
                st.session_state["is_anonymous"] = is_anon
                st.rerun()

    return db


# ==============================================================================
# Stage 1: Upload (Hero + File Uploader + JD Input)
# ==============================================================================
def render_upload_stage():
    st.markdown("""
    <div class="hero-container animate-in">
        <h1>Deep Career Coach</h1>
        <p class="hero-subtitle">
            Upload your resume and a job description to get an instant AI-powered
            match score, skill gap analysis, and personalized recommendations.
        </p>
    </div>
    """, unsafe_allow_html=True)

    cols = st.columns(3)
    features = [
        ("🔍", "Smart Parsing", "PDF & DOCX with confidence scoring"),
        ("🧠", "AI Matching", "BERT + SVM + weighted scoring"),
        ("📊", "Gap Analysis", "JD-specific skill roadmap"),
    ]
    for col, (icon, title, desc) in zip(cols, features):
        with col:
            st.markdown(f"""
            <div class="metric-card animate-in animate-in-delay-1">
                <div style="font-size:2rem">{icon}</div>
                <div class="metric-label" style="font-weight:600;font-size:1rem;color:#FAFAFA">{title}</div>
                <div class="metric-label">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Two-column input layout ──
    left_col, right_col = st.columns([1, 1], gap="large")

    with left_col:
        st.markdown("### 📄 Upload Resume")
        uploaded_file = st.file_uploader(
            "Drop your resume here (PDF or DOCX)",
            type=["pdf", "docx"],
            help="Max 10MB. We support PDF and DOCX formats."
        )

    with right_col:
        st.markdown("### 💼 Job Details")

        # ── Part 1: Role Selector ─────────────────────────────────────────────
        st.markdown("**🎯 Select the Role You Are Applying For**")
        try:
            from utils.gap_analyzer import GapAnalyzer
            _db_for_roles = _get_db()
            _analyzer_for_roles = GapAnalyzer(_db_for_roles)
            all_roles = _analyzer_for_roles.get_all_known_roles()  # [(title, slug), ...]
        except Exception:
            all_roles = []

        role_titles   = ["— Select a role —"] + [t for t, s in all_roles]
        role_slugs    = [None]                 + [s for t, s in all_roles]
        saved_role    = st.session_state.get("selected_role")
        default_idx   = 0
        if saved_role:
            for i, slug in enumerate(role_slugs):
                if slug == saved_role:
                    default_idx = i
                    break

        chosen_idx = st.selectbox(
            "Role",
            range(len(role_titles)),
            format_func=lambda i: role_titles[i],
            index=default_idx,
            key="role_selector_upload",
            label_visibility="collapsed",
        )
        if chosen_idx > 0:
            st.session_state["selected_role"] = role_slugs[chosen_idx]
            st.caption(f"✅ Selected: **{role_titles[chosen_idx]}**")
        else:
            st.session_state["selected_role"] = None

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Part 2: Add Custom Role ───────────────────────────────────────────
        with st.expander("➕ Add a New Role to the Database", expanded=False):
            st.caption("Can't find your role above? Define it here and it will be saved for future screenings.")

            new_role_title = st.text_input(
                "Role Title",
                placeholder="e.g. ML Engineer, DevOps Architect",
                key="new_role_title"
            )

            # ── Step 1: Similarity check when title changes ───────────────────
            if new_role_title.strip():
                prev = st.session_state.get("_prev_role_title_check", "")
                if new_role_title.strip().lower() != prev.lower():
                    st.session_state["similar_roles_found"]     = []
                    st.session_state["role_creation_confirmed"] = False
                    st.session_state["_prev_role_title_check"]  = new_role_title.strip()
                if not st.session_state.get("similar_roles_found") and                    not st.session_state.get("role_creation_confirmed"):
                    _similar = _get_db().find_similar_roles(new_role_title.strip())
                    st.session_state["similar_roles_found"] = _similar

            similar   = st.session_state.get("similar_roles_found", [])
            confirmed = st.session_state.get("role_creation_confirmed", False)

            # ── Step 2: "Are you referring to…?" prompt ───────────────────────
            if similar and not confirmed:
                st.warning("⚠️ Similar roles already exist in the database:")
                for s_title, s_slug in similar:
                    ca, cb = st.columns([3, 1])
                    with ca:
                        st.markdown(f"&nbsp;&nbsp;• **{s_title}**", unsafe_allow_html=True)
                    with cb:
                        if st.button("Use this", key=f"use_existing_{s_slug}"):
                            st.session_state["selected_role"]       = s_slug
                            st.session_state["similar_roles_found"] = []
                            st.session_state["role_creation_confirmed"] = False
                            st.success(f"✅ Selected **{s_title}** as your target role.")
                            st.rerun()
                st.markdown("---")
                cy, cn = st.columns(2)
                with cy:
                    if st.button("➕ No, create a new role anyway",
                                 use_container_width=True, key="confirm_new_role"):
                        st.session_state["role_creation_confirmed"] = True
                        st.session_state["similar_roles_found"]     = []
                        st.rerun()
                with cn:
                    if st.button("✖ Cancel", use_container_width=True, key="cancel_new_role"):
                        st.session_state["similar_roles_found"]     = []
                        st.session_state["role_creation_confirmed"] = False
                        st.rerun()

            # ── Step 3: Skill fields — shown only when no blocking prompt ─────
            elif not similar or confirmed:
                c1, c2 = st.columns(2)
                with c1:
                    new_req = st.text_area(
                        "Required Skills (one per line)",
                        placeholder="Python\nDocker\nKubernetes",
                        height=100, key="new_role_required"
                    )
                with c2:
                    new_rec = st.text_area(
                        "Recommended Skills (one per line)",
                        placeholder="Terraform\nAnsible\nCI/CD",
                        height=100, key="new_role_recommended"
                    )
                new_nice = st.text_area(
                    "Bonus / Nice-to-Have Skills (one per line)",
                    placeholder="Go\nRust\nDatadog",
                    height=70, key="new_role_nice"
                )
                if st.button("💾 Save Role to Database",
                             use_container_width=True, key="save_role_btn"):
                    if not new_role_title.strip():
                        st.warning("Please enter a role title.")
                    else:
                        _slug = new_role_title.strip().lower().replace(" ", "_").replace("/", "_")
                        _req  = [s.strip() for s in new_req.strip().splitlines()  if s.strip()]
                        _rec  = [s.strip() for s in new_rec.strip().splitlines()  if s.strip()]
                        _nice = [s.strip() for s in new_nice.strip().splitlines() if s.strip()]
                        with st.spinner("Saving role to database..."):
                            ok, err = _get_db().save_custom_role(
                                new_role_title.strip(), _slug, _req, _rec, _nice
                            )
                        if ok:
                            st.success(
                                f"✅ **{new_role_title.strip()}** saved! "
                                "It is now set as your target role."
                            )
                            st.session_state["custom_role_saved"]       = True
                            st.session_state["selected_role"]           = _slug
                            st.session_state["role_creation_confirmed"] = False
                            st.session_state["similar_roles_found"]     = []
                        else:
                            st.error(f"❌ Could not save role: {err}")
                            st.caption("Common causes: missing DB permissions, "
                                       "duplicate slug, or Supabase connection issue.")
        st.markdown("<br>", unsafe_allow_html=True)

        # ── Part 3: Job Description Textarea ─────────────────────────────────
        st.markdown("**📋 Paste Job Description** *(optional but recommended)*")
        jd_text = st.text_area(
            "JD",
            value=st.session_state.get("jd_text", ""),
            height=160,
            placeholder="e.g. We are looking for a Python Developer with 3+ years experience in Django, REST APIs, PostgreSQL...",
            help="The more complete the JD, the more accurate the match score.",
            key="jd_input",
            label_visibility="collapsed",
        )
        if jd_text:
            word_count = len(jd_text.split())
            if word_count < 50:
                st.warning(f"⚠️ JD is short ({word_count} words). A longer description improves accuracy.")
            else:
                st.caption(f"✅ {word_count} words — good length.")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Analyze button ──
    if uploaded_file:
        file_bytes = uploaded_file.getvalue()
        user = st.session_state.get("user")
        user_id = user.email if (user and not st.session_state.get("is_anonymous")) else (user.id if user else "anonymous")
        is_auth = bool(user and not st.session_state.get("is_anonymous"))

        limiter = RateLimiter()
        is_allowed, error_msg = limiter.check_rate_limit(user_id, is_auth)
        if not is_allowed:
            st.error(error_msg)
            return

        max_size = limiter.get_file_size_limit(is_auth)
        if len(file_bytes) > max_size:
            st.error(f"📁 File too large. Max: {max_size // (1024*1024)} MB")
            return

        is_valid, error = validate_file(file_bytes, uploaded_file.name)
        if not is_valid:
            show_error(error)
            return

        st.success(f"✅ Ready: **{uploaded_file.name}**")

        if not jd_text or len(jd_text.strip()) < 20:
            st.info("💡 Tip: Paste a job description above for a JD-specific match score. Or click Analyze to use general market standards.")

        btn_label = "🚀 Analyze vs Job Description" if jd_text and len(jd_text.strip()) >= 20 else "🚀 Analyze Resume"
        if st.button(btn_label, type="primary", use_container_width=True):
            st.session_state["jd_text"] = jd_text.strip()
            st.session_state["file_bytes"] = file_bytes
            st.session_state["uploaded_file_name"] = uploaded_file.name
            _run_analysis_pipeline(file_bytes, uploaded_file.name, jd_text.strip())


def _run_analysis_pipeline(file_bytes: bytes, filename: str, jd_text: str = ""):
    """Run the full analysis pipeline and advance to teaser stage."""
    db = _get_db()
    progress = st.progress(0, text="Starting analysis...")

    # 1. Parse
    progress.progress(10, text="📄 Parsing resume...")
    from utils.parser import ResumeParser
    parser = ResumeParser()
    parse_result = parser.parse(file_bytes, filename)

    if not parse_result.success:
        st.session_state["parse_result"] = parse_result
        if parse_result.error:
            show_error(parse_result.error)
        return

    st.session_state["parse_result"] = parse_result

    if parse_result.confidence < 0.3 or len(parse_result.text.strip()) < 100:
        st.session_state["app_stage"] = "builder"
        st.rerun()
        return

    resume_text = parse_result.text

    # 2. Extract Skills
    progress.progress(25, text="🧠 Extracting skills...")
    from utils.skill_extractor import SkillExtractor
    extractor = SkillExtractor()
    skill_data = extractor.extract_skills(resume_text)
    st.session_state["skill_data"] = skill_data

    # 3. Classify (SVM + BERT hybrid)
    progress.progress(40, text="🔮 Classifying resume...")
    from utils.classifier import JobClassifier
    classifier = JobClassifier()
    prediction = classifier.predict(resume_text)
    st.session_state["prediction"] = prediction
    st.session_state["explanation"] = classifier.explain_prediction(resume_text)

    # 4. Determine target role
    # Priority: (1) user-selected role > (2) SVM prediction > (3) skill-based fallback
    user_selected_role = st.session_state.get("selected_role")
    role_cats = extractor.map_to_category(skill_data["all_skills"])
    top_skill_cat = list(role_cats.keys())[0] if role_cats else "Unknown"
    svm_role = prediction["top_category"]

    if user_selected_role:
        # User explicitly picked a role — always honour it
        target_role = user_selected_role
    elif svm_role and svm_role != "Unknown" and not str(svm_role).isdigit():
        target_role = svm_role
    else:
        target_role = top_skill_cat

    st.session_state["target_role"] = target_role

    # 5. JD-specific BERT matching (NEW)
    jd_match_result = None
    if jd_text:
        progress.progress(55, text="🔍 Matching against job description...")
        try:
            from utils.jd_matcher import JDMatcher
            matcher = JDMatcher()
            jd_match_result = matcher.match(jd_text, resume_text)
            st.session_state["jd_match_result"] = jd_match_result
        except Exception as e:
            st.warning(f"JD matching unavailable: {e}")

    # 6. Gap Analysis
    progress.progress(65, text="📊 Analyzing skill gaps...")
    from utils.gap_analyzer import GapAnalyzer
    analyzer = GapAnalyzer(db)

    if jd_text:
        # JD-specific gap: extract skills from JD and compare
        jd_skill_data = extractor.extract_skills(jd_text)
        jd_skills = jd_skill_data.get("all_skills", [])
        resume_skills_set = set(s.lower() for s in skill_data["all_skills"])
        matched_skills = [s for s in jd_skills if s.lower() in resume_skills_set]
        missing_skills = [s for s in jd_skills if s.lower() not in resume_skills_set]
        extra_skills   = [s for s in skill_data["all_skills"] if s.lower() not in {x.lower() for x in jd_skills}]
        st.session_state["jd_skills"]      = jd_skills
        st.session_state["matched_skills"] = matched_skills
        st.session_state["missing_skills"] = missing_skills
        st.session_state["extra_skills"]   = extra_skills
    else:
        # Fall back to market-standards gap
        matched_skills = skill_data["all_skills"]
        missing_skills = []
        extra_skills   = []

    analysis = analyzer.analyze_gaps(skill_data["all_skills"], target_role)
    st.session_state["gap_analysis"] = analysis

    # 7. Weighted score (NEW)
    if jd_text and jd_match_result:
        progress.progress(75, text="⚖️ Computing weighted score...")
        try:
            from utils.weighted_scorer import compute_final_score
            score_result = compute_final_score(
                bert_score=jd_match_result["overall_score"],
                matched_skills=matched_skills,
                jd_skills=st.session_state.get("jd_skills", []),
                svm_confidence=prediction.get("confidence", 0.0),
                resume_text=resume_text,
                jd_text=jd_text,
            )
            st.session_state["weighted_score_result"] = score_result
            # Patch gap_analysis match_percentage with the improved score
            analysis["match_percentage"] = score_result["final_score"]
            st.session_state["gap_analysis"] = analysis
        except Exception as e:
            st.warning(f"Weighted scoring unavailable: {e}")

    # 8. AI Feedback (NEW — only when JD provided)
    if jd_text and AIFeedbackGenerator:
        progress.progress(85, text="🤖 Generating AI feedback...")
        try:
            feedback_gen = AIFeedbackGenerator()
            score_result = st.session_state.get("weighted_score_result", {})
            section_scores = jd_match_result.get("section_scores", {}) if jd_match_result else {}
            ai_feedback = feedback_gen.generate(
                jd_text=jd_text,
                resume_text=resume_text,
                section_scores=section_scores,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
                final_score=score_result.get("final_score", analysis["match_percentage"]),
                verdict=score_result.get("verdict", ""),
            )
            st.session_state["ai_feedback"] = ai_feedback
        except Exception as e:
            st.warning(f"AI feedback unavailable: {e}")

    # 9. Growth tracking
    progress.progress(93, text="📈 Calculating growth...")
    from utils.growth_tracker import GrowthTracker
    user = st.session_state.get("user")
    previous = db.get_previous_version(user.id, filename) if user else None
    growth = GrowthTracker.calculate_growth(analysis, skill_data["all_skills"], previous)
    st.session_state["growth_data"] = growth

    # 10. Save (authenticated users)
    if user:
        db.save_resume_analysis(user.id, {
            "filename": filename,
            "storage_path": f"resumes/{user.id}/{filename}",
            "parsed_text": resume_text,
            "page_count": parse_result.page_count,
            "confidence_score": parse_result.confidence,
            "predicted_role": target_role,
            "match_score": analysis["match_percentage"],
            "skills": [{"name": s, "category": "extracted"} for s in skill_data["all_skills"]]
        })

    progress.progress(100, text="✅ Done!")
    time.sleep(0.3)
    st.session_state["app_stage"] = "teaser"
    st.rerun()


# ==============================================================================
# Stage 2: Teaser (Anonymous Score Card + CTA)
# ==============================================================================
def render_teaser_stage():
    analysis         = st.session_state["gap_analysis"]
    skill_data       = st.session_state["skill_data"]
    target_role      = st.session_state.get("target_role", "Unknown")
    score_result     = st.session_state.get("weighted_score_result")
    jd_text          = st.session_state.get("jd_text", "")

    score   = score_result["final_score"] if score_result else analysis["match_percentage"]
    verdict = score_result["verdict"]     if score_result else ("Strong Match" if score >= 85 else "Moderate Match" if score >= 65 else "Weak Match")
    emoji   = score_result["verdict_emoji"] if score_result else ("🟢" if score >= 85 else "🟡" if score >= 65 else "🔴")

    st.markdown("<div class='animate-in'>", unsafe_allow_html=True)
    st.markdown("## 🎯 Your Career Match Preview")

    if jd_text:
        st.caption("📋 Scored against your provided job description")
    else:
        st.caption("📊 Scored against general market standards")

    color = "#43E97B" if score >= 85 else "#ffa421" if score >= 65 else "#FF6584"
    st.markdown(f"""
    <div class="teaser-score animate-in animate-in-delay-1">
        <div class="score-number" style="-webkit-text-fill-color: {color}">{score:.0f}%</div>
        <div class="score-label">{emoji} <strong>{verdict}</strong> for <strong>{target_role.replace('_', ' ').title()}</strong></div>
    </div>
    """, unsafe_allow_html=True)

    # Section scores breakdown (only when JD was provided)
    if score_result and st.session_state.get("jd_match_result"):
        section_scores = st.session_state["jd_match_result"].get("section_scores", {})
        if section_scores:
            st.markdown("<br>**Section Breakdown:**", unsafe_allow_html=True)
            s1, s2, s3, s4 = st.columns(4)
            for col, (sec, val) in zip([s1, s2, s3, s4], section_scores.items()):
                with col:
                    st.metric(sec.title(), f"{val:.0f}%")

    # Quick Stats
    st.markdown("<br>", unsafe_allow_html=True)
    cols = st.columns(3)
    matched = st.session_state.get("matched_skills", [])
    missing = st.session_state.get("missing_skills", analysis.get("missing_required", []))
    with cols[0]:
        st.markdown(f"""
        <div class="metric-card animate-in animate-in-delay-1">
            <div class="metric-value">{skill_data['count']}</div>
            <div class="metric-label">Skills Found</div>
        </div>
        """, unsafe_allow_html=True)
    with cols[1]:
        st.markdown(f"""
        <div class="metric-card animate-in animate-in-delay-2">
            <div class="metric-value">{len(matched)}</div>
            <div class="metric-label">Matched Skills</div>
        </div>
        """, unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"""
        <div class="metric-card animate-in animate-in-delay-3">
            <div class="metric-value">{len(missing)}</div>
            <div class="metric-label">Missing Skills</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    if skill_data["all_skills"]:
        st.markdown("**Top Skills Detected:**")
        pills_html = " ".join(
            [f'<span class="skill-pill present">{s}</span>' for s in skill_data["all_skills"][:8]]
        )
        if len(skill_data["all_skills"]) > 8:
            pills_html += f' <span class="skill-pill">+{len(skill_data["all_skills"]) - 8} more</span>'
        st.markdown(pills_html, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("---")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("✏️ Review & Edit Extracted Data", use_container_width=True):
            st.session_state["app_stage"] = "review"
            st.rerun()
    with c2:
        if st.button("📊 Go to Full Dashboard", type="primary", use_container_width=True):
            st.session_state["app_stage"] = "dashboard"
            st.rerun()

    if st.session_state.get("is_anonymous") or not st.session_state.get("user"):
        st.info("💡 **Sign up** to save this analysis, track growth, and download PDF reports!")

    st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# Stage 3: Review Screen (Split-View)
# ==============================================================================
def render_review_stage():
    st.markdown("## ✏️ Review & Verify Extracted Data")
    st.caption("Verify the AI's extraction. Edit any incorrect fields before proceeding.")

    parse_result = st.session_state["parse_result"]
    skill_data   = st.session_state["skill_data"]
    target_role  = st.session_state.get("target_role", "Unknown")

    left, right = st.columns([1, 1], gap="large")

    with left:
        st.markdown("### 📄 Extracted Text")
        st.markdown(f"""
        <div class="glass-panel" style="max-height:500px; overflow-y:auto; font-size:0.9rem; line-height:1.6">
            {parse_result.text[:3000].replace(chr(10), '<br>')}
            {'<br><em>...truncated</em>' if len(parse_result.text) > 3000 else ''}
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 📊 Parse Confidence")
        conf = parse_result.confidence
        st.progress(conf, text=f"{conf*100:.0f}% confidence")
        if conf < 0.7:
            show_warning(
                "Low confidence parsing. Please double-check critical fields.",
                "The AI may have missed some information due to formatting."
            )

    with right:
        st.markdown("### 🧠 Extracted Data")

        st.markdown("#### 🎯 Predicted Target Role")
        from utils.skill_extractor import SkillExtractor
        extractor = SkillExtractor()
        categories = list(extractor.standards.get("job_categories", {}).keys())
        cat_display = [c.replace("_", " ").title() for c in categories]

        current_idx = 0
        target_lower = target_role.lower().replace(" ", "_")
        for i, c in enumerate(categories):
            if c == target_lower or c == target_role:
                current_idx = i
                break

        new_role = st.selectbox(
            "Override target role if incorrect:",
            cat_display,
            index=current_idx,
            key="role_override"
        )
        if new_role:
            st.session_state["target_role"] = categories[cat_display.index(new_role)]

        st.markdown("---")

        st.markdown("#### 🛠️ Skills Found")
        current_skills = skill_data.get("all_skills", [])
        edited_skills = st.text_area(
            "Edit skills (one per line):",
            value="\n".join(current_skills),
            height=200,
            key="skill_editor"
        )
        new_skill = st.text_input("➕ Add a skill:", key="add_skill_input")
        if new_skill:
            lines = edited_skills.strip().split("\n") if edited_skills.strip() else []
            if new_skill not in lines:
                lines.append(new_skill)
                edited_skills = "\n".join(lines)

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ Back to Preview", use_container_width=True):
            st.session_state["app_stage"] = "teaser"
            st.rerun()
    with c2:
        if st.button("✅ Confirm & View Dashboard", type="primary", use_container_width=True):
            final_skills = [s.strip() for s in edited_skills.strip().split("\n") if s.strip()]
            st.session_state["reviewed_skills"] = final_skills
            st.session_state["skill_data"]["all_skills"] = final_skills
            st.session_state["skill_data"]["count"] = len(final_skills)

            from utils.gap_analyzer import GapAnalyzer
            db = _get_db()
            analyzer = GapAnalyzer(db)
            new_analysis = analyzer.analyze_gaps(final_skills, st.session_state["target_role"])
            st.session_state["gap_analysis"] = new_analysis

            st.session_state["app_stage"] = "dashboard"
            st.rerun()


# ==============================================================================
# Stage 3b: Builder Mode
# ==============================================================================
def render_builder_stage():
    st.markdown("## 🏗️ Resume Builder Mode")
    st.info(
        "Your resume appears to be **empty or very minimal**. "
        "Let's build your profile from scratch using a few questions!"
    )

    with st.form("builder_form"):
        st.markdown("### Tell us about yourself")
        col1, col2 = st.columns(2)
        with col1:
            field_of_study = st.text_input("📚 Field of Study")
            graduation_year = st.selectbox("🎓 Expected Graduation", [str(y) for y in range(2024, 2030)])
        with col2:
            dream_role = st.text_input("💼 Dream Job Title")
            experience_level = st.select_slider(
                "📊 Experience Level",
                options=["Beginner", "Some Projects", "Internship", "1+ Years"]
            )
        st.markdown("### What do you know?")
        known_skills = st.text_area(
            "List technologies/tools you've used (one per line):",
            placeholder="Python\nJavaScript\nSQL\nGit",
            height=150
        )
        st.markdown("### What interests you?")
        interests = st.multiselect(
            "Select areas of interest:",
            ["Web Development", "Data Science", "Machine Learning",
             "Mobile Development", "Cloud/DevOps", "Cybersecurity",
             "Game Development", "UI/UX Design"]
        )
        submitted = st.form_submit_button("🚀 Generate My Profile", type="primary", use_container_width=True)

    if submitted:
        skills_list = [s.strip() for s in known_skills.strip().split("\n") if s.strip()]
        st.session_state["skill_data"] = {
            "all_skills": skills_list,
            "count": len(skills_list),
            "detailed_skills": [{"name": s, "sources": ["self_reported"], "weight_score": 0.5} for s in skills_list]
        }
        target = dream_role.lower().replace(" ", "_") if dream_role else "software_engineer"
        st.session_state["target_role"] = target
        st.session_state["prediction"] = {"top_category": target, "confidence": 0.5, "all_scores": {target: 0.5}}

        from utils.gap_analyzer import GapAnalyzer
        db = _get_db()
        analyzer = GapAnalyzer(db)
        analysis = analyzer.analyze_gaps(skills_list, target)
        st.session_state["gap_analysis"] = analysis
        st.session_state["growth_data"] = {
            "score_delta": 0, "skills_added": [], "is_improved": False, "first_upload": True
        }
        st.session_state["app_stage"] = "dashboard"
        st.rerun()


# ==============================================================================
# Stage 4: Full Dashboard (Deep Coach)
# ==============================================================================
def render_dashboard_stage():
    analysis      = st.session_state["gap_analysis"]
    skill_data    = st.session_state["skill_data"]
    target_role   = st.session_state.get("target_role", "Unknown")
    prediction    = st.session_state.get("prediction", {})
    growth_data   = st.session_state.get("growth_data")
    score_result  = st.session_state.get("weighted_score_result")
    jd_match      = st.session_state.get("jd_match_result")
    ai_feedback   = st.session_state.get("ai_feedback")
    jd_text       = st.session_state.get("jd_text", "")
    matched_skills = st.session_state.get("matched_skills", [])
    missing_skills = st.session_state.get("missing_skills", analysis.get("missing_required", []))
    extra_skills   = st.session_state.get("extra_skills", [])

    role_display = target_role.replace("_", " ").title()
    st.markdown(f"## 🎯 Career Dashboard — {role_display}")

    if jd_text:
        st.caption("📋 Analysis based on your provided job description")

    if growth_data:
        from utils.growth_tracker import GrowthTracker
        GrowthTracker.render_growth_metrics(growth_data)

    st.markdown("---")

    # ── Row 1: Executive Metrics ──
    score   = score_result["final_score"] if score_result else analysis["match_percentage"]
    verdict = score_result["verdict"]     if score_result else ""
    emoji   = score_result["verdict_emoji"] if score_result else ""
    conf    = prediction.get("confidence", 0)

    m1, m2, m3, m4 = st.columns(4)
    color = "#43E97B" if score >= 85 else "#ffa421" if score >= 65 else "#FF6584"
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value" style="color:{color}">{score:.0f}%</div>
            <div class="metric-label">{emoji} {verdict or "Match Score"}</div>
        </div>
        """, unsafe_allow_html=True)
    with m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{skill_data['count']}</div>
            <div class="metric-label">Skills Found</div>
        </div>
        """, unsafe_allow_html=True)
    with m3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{len(missing_skills)}</div>
            <div class="metric-label">Missing Skills</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{conf*100:.0f}%</div>
            <div class="metric-label">SVM Confidence</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Score component breakdown ──
    if score_result:
        with st.expander("⚖️ Score Breakdown (How this was calculated)", expanded=False):
            comps = score_result["component_scores"]
            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("BERT Semantic (50%)", f"{comps['bert_semantic']:.1f}%")
            sc2.metric("Skill Overlap (30%)", f"{comps['skill_overlap']:.1f}%")
            sc3.metric("SVM Confidence (10%)", f"{comps['svm_confidence']:.1f}%")
            sc4.metric("Education Match (10%)", f"{comps['education_match']:.1f}%")
            st.caption("Final score = BERT×50% + Skills×30% + SVM×10% + Education×10%")

    # ── Section scores bar chart ──
    if jd_match and jd_match.get("section_scores"):
        with st.expander("📊 Section-Level BERT Scores", expanded=True):
            sec_df = pd.DataFrame(
                list(jd_match["section_scores"].items()),
                columns=["Section", "Score (%)"]
            )
            st.bar_chart(sec_df.set_index("Section"), color="#6C63FF")
            if jd_match.get("missing_sections"):
                st.warning(f"⚠️ Sections not detected in resume: {', '.join(jd_match['missing_sections'])}")

    # ── Export ──
    try:
        from utils.pdf_generator import PDFGenerator
        pdf_gen = PDFGenerator()
        pdf_data = {
            "role": target_role,
            "match_percentage": score,
            "missing_required": missing_skills or analysis["missing_required"],
            "missing_recommended": analysis.get("missing_recommended", []),
            "learning_paths": analysis.get("learning_paths", {}),
            "recommendations": analysis.get("recommendations", [])
        }
        user_name = st.session_state["user"].email if st.session_state.get("user") else "Guest"
        pdf_buffer = PDFGenerator().generate_report(pdf_data, user_name)
        st.download_button(
            label="📄 Download Career Roadmap (PDF)",
            data=pdf_buffer,
            file_name=f"Career_Roadmap_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf",
            type="primary"
        )
    except Exception:
        pass

    st.markdown("---")

    # ── Charts ──
    chart_left, chart_right = st.columns(2)
    with chart_left:
        st.markdown("### 🕸️ Skill Radar")
        from utils.visualizer import Visualizer
        radar = Visualizer.plot_radar_chart(skill_data["all_skills"], analysis)
        st.plotly_chart(radar, use_container_width=True, config={"displayModeBar": False})
    with chart_right:
        st.markdown("### 📊 Gap Overview")
        gap_chart = Visualizer.plot_skill_gap_chart(analysis)
        st.plotly_chart(gap_chart, use_container_width=True, config={"displayModeBar": False})

    st.markdown("---")

    # ── Tabs ──
    tab_labels = ["✅ Your Skills", "❌ Skill Gaps", "🤖 AI Feedback", "🎓 Learning Plan", "💬 AI Coach"]
    tab_skills, tab_gaps, tab_feedback, tab_plan, tab_ai = st.tabs(tab_labels)

    with tab_skills:
        if skill_data["all_skills"]:
            pills = " ".join(
                [f'<span class="skill-pill present">{s}</span>' for s in skill_data["all_skills"]]
            )
            st.markdown(pills, unsafe_allow_html=True)
        else:
            st.info("No skills detected.")

    with tab_gaps:
        if jd_text:
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("#### ✅ Matched Skills")
                if matched_skills:
                    st.markdown(" ".join([f'<span class="skill-pill present">{s}</span>' for s in matched_skills]), unsafe_allow_html=True)
                else:
                    st.info("None matched.")
            with c2:
                st.markdown("#### ❌ Missing Skills")
                if missing_skills:
                    st.markdown(" ".join([f'<span class="skill-pill missing">{s}</span>' for s in missing_skills]), unsafe_allow_html=True)
                else:
                    st.success("None missing! 🎉")
            with c3:
                st.markdown("#### ➕ Bonus Skills")
                if extra_skills:
                    st.markdown(" ".join([f'<span class="skill-pill">{s}</span>' for s in extra_skills[:15]]), unsafe_allow_html=True)
                else:
                    st.info("No extra skills detected.")
        else:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### 🔴 Missing Required")
                if analysis["missing_required"]:
                    st.markdown(" ".join([f'<span class="skill-pill missing">{s}</span>' for s in analysis["missing_required"]]), unsafe_allow_html=True)
                else:
                    st.success("None! Excellent coverage. 🎉")
            with c2:
                st.markdown("#### 🟡 Missing Recommended")
                if analysis["missing_recommended"]:
                    st.markdown(" ".join([f'<span class="skill-pill missing">{s}</span>' for s in analysis["missing_recommended"]]), unsafe_allow_html=True)
                else:
                    st.success("None! Great fit. 🌟")

    with tab_feedback:
        st.markdown("### 🤖 AI Recruiter Feedback")
        if ai_feedback:
            source = ai_feedback.get("_source", "unknown")
            if source == "claude_api":
                st.success("✅ Powered by Claude AI")
            else:
                st.info("ℹ️ Rule-based feedback (Claude API not configured)")

            # Experience gap
            if ai_feedback.get("experience_gap"):
                st.markdown("#### ⏱️ Experience Assessment")
                st.info(ai_feedback["experience_gap"])

            # Recommendation
            if ai_feedback.get("recommendation"):
                st.markdown("#### 💼 Recruiter Recommendation")
                st.markdown(f"""
                <div class="glass-panel" style="padding:1rem;border-left:4px solid #6C63FF">
                    {ai_feedback['recommendation']}
                </div>
                """, unsafe_allow_html=True)

            # Improvement suggestions
            if ai_feedback.get("improvement_suggestions"):
                st.markdown("#### 💡 Improvement Suggestions")
                for i, tip in enumerate(ai_feedback["improvement_suggestions"], 1):
                    st.markdown(f"**{i}.** {tip}")
        elif not jd_text:
            st.info("💡 Paste a job description on the upload page to get AI recruiter feedback.")
        else:
            st.warning("AI feedback was not generated. Check your ANTHROPIC_API_KEY in Streamlit secrets.")

    with tab_plan:
        st.markdown("### 📚 Recommended Learning Paths")
        if analysis.get("learning_paths"):
            for skill, resources in analysis["learning_paths"].items():
                with st.expander(f"📖 Learn: **{skill}**"):
                    for r in resources:
                        if isinstance(r, dict):
                            st.markdown(f"- [{r.get('title', 'Link')}]({r.get('url', '#')})")
                        else:
                            st.markdown(f"- {r}")
        else:
            st.info("No specific resources found yet.")
        if analysis.get("recommendations"):
            st.markdown("### 💡 Coach Recommendations")
            for rec in analysis["recommendations"]:
                st.markdown(f"- {rec}")

    with tab_ai:
        st.markdown("### 💬 Career Coach Chat")
        st.caption("Ask me anything about your career path, skills, or interview prep.")
        if not AIAssistant:
            st.warning("⚠️ AI Assistant not available.")
        else:
            if "ai_agent" not in st.session_state:
                st.session_state["ai_agent"] = AIAssistant()
            for msg in st.session_state["chat_history"]:
                with st.chat_message("user" if msg["role"] == "user" else "assistant"):
                    st.write(msg["content"])
            if prompt := st.chat_input("Ask about your career path..."):
                st.session_state["chat_history"].append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.write(prompt)
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        user = st.session_state.get("user")
                        user_id = user.id if user else "guest"
                        response = st.session_state["ai_agent"].generate_response(prompt, user_id)
                        st.write(response)
                st.session_state["chat_history"].append({"role": "assistant", "content": response})

    st.markdown("---")

    # ── Explainability ──
    if st.session_state.get("explanation"):
        expl = st.session_state["explanation"]
        with st.expander("🔍 Why This Role? (AI Explainability)"):
            st.info("Keywords that most influenced the AI's classification decision.")
            top_keywords = [k[0] for k in expl.get("positive", [])[:5]]
            if top_keywords:
                st.markdown(
                    f"Your profile aligns with **{role_display}** because of: "
                    + ", ".join([f"**{k}**" for k in top_keywords])
                )
                p_df = pd.DataFrame(expl["positive"][:10], columns=["Keyword", "Impact"])
                st.bar_chart(p_df.sort_values("Impact", ascending=False).set_index("Keyword"), color="#6C63FF")
            st.caption("Score formula: BERT(50%) + Skills(30%) + SVM(10%) + Education(10%)")

    # ── History ──
    user = st.session_state.get("user")
    if user and not st.session_state.get("is_anonymous"):
        with st.expander("📜 Your Analysis History"):
            db = _get_db()
            history = db.get_user_history(user.id)
            if history:
                df = pd.DataFrame(history)
                display_cols = [c for c in ["created_at", "filename", "predicted_role", "match_score"] if c in df.columns]
                st.dataframe(df[display_cols] if display_cols else df, use_container_width=True)
            else:
                st.caption("No previous analyses found.")


# ==============================================================================
# Router
# ==============================================================================
def main():
    db = render_sidebar()
    stage = st.session_state["app_stage"]
    if stage == "upload":
        render_upload_stage()
    elif stage == "teaser":
        render_teaser_stage()
    elif stage == "review":
        render_review_stage()
    elif stage == "builder":
        render_builder_stage()
    elif stage == "dashboard":
        render_dashboard_stage()


if __name__ == "__main__":
    main()
