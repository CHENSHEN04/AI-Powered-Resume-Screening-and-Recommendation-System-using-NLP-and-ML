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
    from utils.ai_assistant import AIAssistant, AIFeedbackGenerator, AIRoleStandardGenerator
except ImportError:
    AIAssistant = None
    AIFeedbackGenerator = None
    AIRoleStandardGenerator = None


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
def _get_db():
    """Get DB client scoped to the current user session."""
    if "db_client" not in st.session_state:
        st.session_state["db_client"] = DatabaseManager()
    return st.session_state["db_client"]


def _sync_session_analysis_to_db(db, user_id):
    """Automatically persist a completed guest/session resume analysis to the database upon user login/signup."""
    if (st.session_state.get("gap_analysis") and 
        st.session_state.get("parse_result") and 
        st.session_state.get("uploaded_file_name")):
        
        filename = st.session_state["uploaded_file_name"]
        parse_result = st.session_state["parse_result"]
        target_role = st.session_state.get("target_role", "Unknown")
        analysis = st.session_state["gap_analysis"]
        skill_data = st.session_state["skill_data"]
        
        # Save to database
        db.save_resume_analysis(user_id, {
            "filename": filename,
            "storage_path": f"resumes/{user_id}/{filename}",
            "parsed_text": parse_result.text,
            "page_count": parse_result.page_count,
            "confidence_score": parse_result.confidence,
            "predicted_role": target_role,
            "match_score": analysis["match_percentage"],
            "skills": [{"name": s, "category": "extracted"} for s in skill_data["all_skills"]]
        })
        st.toast("💾 Guest resume analysis successfully saved to your account!", icon="📥")




def render_sidebar():
    db = _get_db()
    with st.sidebar:
        st.markdown("# 🎯 Career Coach")
        st.caption("AI-Powered Resume Analysis")
        st.markdown("---")

        user = st.session_state.get("user")
        is_anon = st.session_state.get("is_anonymous", False)

        if not user:
            st.info("👋 Welcome!")
            st.caption("Please sign in or continue as guest in the main window to get started.")
            return db

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
                            _sync_session_analysis_to_db(db, res.user.id)
                            if st.session_state.get("gap_analysis"):
                                st.session_state["app_stage"] = "dashboard"
                            st.rerun()
                    else:
                        res, err = db.sign_up(email, password, full_name)
                        if err:
                            st.error(err)
                        else:
                            st.success("📧 Verification email sent!")
            
            if auth_mode == "Login":
                with st.expander("🔑 Forgot Password?"):
                    reset_email = st.text_input("Enter email to reset password", key="sidebar_reset_email")
                    if st.button("Send Reset Link", key="sidebar_reset_btn", use_container_width=True):
                        if reset_email:
                            _, err = db.reset_password(reset_email)
                            if err:
                                st.error(f"❌ {err}")
                            else:
                                st.success("✉️ Password reset link sent!")
                        else:
                            st.warning("Please enter email.")

        st.markdown("---")
        stages = {"upload": "1️⃣ Upload", "teaser": "2️⃣ Preview",
                  "review": "3️⃣ Review", "dashboard": "4️⃣ Dashboard"}
        current = st.session_state["app_stage"]
        has_analysis = st.session_state.get("gap_analysis") is not None
        
        for key, label in stages.items():
            if key == current:
                st.button(f"👉 {label}", key=f"nav_{key}", use_container_width=True, type="primary", disabled=True)
            else:
                disabled = (key != "upload" and not has_analysis)
                if st.button(label, key=f"nav_{key}", use_container_width=True, disabled=disabled):
                    st.session_state["app_stage"] = key
                    st.rerun()

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
        st.markdown("### 💼 Paste Job Description")
        jd_text = st.text_area(
            "Paste the full job description here",
            value=st.session_state.get("jd_text", ""),
            height=220,
            placeholder="e.g. We are looking for a Python Developer with 3+ years experience in Django, REST APIs, PostgreSQL...",
            help="The more complete the JD, the more accurate the match score.",
            key="jd_input"
        )
        if jd_text:
            word_count = len(jd_text.split())
            if word_count < 50:
                st.warning(f"⚠️ JD is short ({word_count} words). A longer description gives more accurate results.")
            else:
                st.caption(f"✅ {word_count} words — good length for analysis.")

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
            show_role_selector_dialog(file_bytes, uploaded_file.name, jd_text.strip())


@st.dialog("🎯 Select Targeted Job Role", width="large")
def show_role_selector_dialog(file_bytes, filename, jd_text):
    db = _get_db()
    
    st.write("To customize your career match analysis, select the job role you are targeting:")
    
    # Get standard roles from GapAnalyzer
    from utils.gap_analyzer import GapAnalyzer
    analyzer = GapAnalyzer(db)
    known_roles = analyzer.get_all_known_roles() # list of (title, slug)
    
    role_titles = [r[0] for r in known_roles]
    role_slugs = [r[1] for r in known_roles]
    
    # Add custom option
    options = role_titles + ["➕ Custom / Add new role..."]
    
    selected_option = st.selectbox("Select target role:", options, index=0)
    
    if selected_option == "➕ Custom / Add new role...":
        # Render custom role fields
        custom_role = st.text_input("Enter custom job role title (e.g. Cloud Security Specialist):", placeholder="e.g. Cloud Security Specialist")
        
        # State variables for similarity confirmation flow
        if "sim_checked" not in st.session_state:
            st.session_state["sim_checked"] = False
        if "similar_role_found" not in st.session_state:
            st.session_state["similar_role_found"] = None
        if "similar_role_slug" not in st.session_state:
            st.session_state["similar_role_slug"] = None
            
        if custom_role:
            cleaned_role = custom_role.strip()
            # If they changed the text, reset the checked state
            if st.session_state.get("last_checked_role") != cleaned_role:
                st.session_state["sim_checked"] = False
                st.session_state["last_checked_role"] = cleaned_role
                
            if not st.session_state["sim_checked"]:
                # Check semantic similarity using find_best_match
                from utils.semantic_matcher import SemanticMatcher
                matcher = SemanticMatcher()
                candidates = {slug: title for title, slug in known_roles}
                best_slug, score = matcher.find_best_match(cleaned_role, candidates)
                
                if best_slug and score > 0.65:
                    st.session_state["similar_role_found"] = candidates[best_slug]
                    st.session_state["similar_role_slug"] = best_slug
                else:
                    st.session_state["similar_role_found"] = None
                    st.session_state["similar_role_slug"] = None
                st.session_state["sim_checked"] = True
            
            # If a similar role is found, prompt the user
            if st.session_state["similar_role_found"]:
                st.warning(f"🔍 We found a very similar role: **{st.session_state['similar_role_found']}** in our database.")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button(f"Yes, use {st.session_state['similar_role_found']}", type="primary", use_container_width=True):
                        st.session_state["target_role"] = st.session_state["similar_role_slug"]
                        # Clear similarity states
                        st.session_state["sim_checked"] = False
                        st.session_state["similar_role_found"] = None
                        st.session_state["similar_role_slug"] = None
                        # Run pipeline
                        _run_analysis_pipeline(file_bytes, filename, jd_text)
                with c2:
                    if st.button("No, this is a distinct new role", use_container_width=True):
                        # Proceed with AI generation
                        with st.spinner(f"🤖 Searching responsibilities for '{cleaned_role}' using AI..."):
                            from utils.ai_assistant import AIRoleStandardGenerator
                            gen = AIRoleStandardGenerator()
                            standards = gen.generate_standards(cleaned_role)
                            
                            new_slug = cleaned_role.lower().replace(" ", "_").replace("/", "_")
                            
                            # Save custom role
                            success, err = db.save_custom_role(
                                role_title=cleaned_role,
                                role_slug=new_slug,
                                required_skills=standards.get("required_skills", []),
                                recommended_skills=standards.get("recommended_skills", []),
                                nice_to_have_skills=standards.get("nice_to_have_skills", [])
                            )
                            
                            # Fallback if DB save fails
                            if not success:
                                st.session_state[f"custom_standards_{new_slug}"] = standards
                            
                            st.session_state["target_role"] = new_slug
                            # Clear states
                            st.session_state["sim_checked"] = False
                            st.session_state["similar_role_found"] = None
                            st.session_state["similar_role_slug"] = None
                            # Run pipeline
                            _run_analysis_pipeline(file_bytes, filename, jd_text)
            else:
                # No similar role found - proceed directly to AI generation
                if st.button("🚀 Analyze with Custom Role", type="primary", use_container_width=True):
                    with st.spinner(f"🤖 Searching responsibilities for '{cleaned_role}' using AI..."):
                        from utils.ai_assistant import AIRoleStandardGenerator
                        gen = AIRoleStandardGenerator()
                        standards = gen.generate_standards(cleaned_role)
                        
                        new_slug = cleaned_role.lower().replace(" ", "_").replace("/", "_")
                        
                        # Save custom role
                        success, err = db.save_custom_role(
                            role_title=cleaned_role,
                            role_slug=new_slug,
                            required_skills=standards.get("required_skills", []),
                            recommended_skills=standards.get("recommended_skills", []),
                            nice_to_have_skills=standards.get("nice_to_have_skills", [])
                        )
                        
                        # Fallback if DB save fails
                        if not success:
                            st.session_state[f"custom_standards_{new_slug}"] = standards
                        
                        st.session_state["target_role"] = new_slug
                        # Clear states
                        st.session_state["sim_checked"] = False
                        st.session_state["similar_role_found"] = None
                        st.session_state["similar_role_slug"] = None
                        # Run pipeline
                        _run_analysis_pipeline(file_bytes, filename, jd_text)
                        
    else:
        # Clear similarity states just in case they switched back
        st.session_state["sim_checked"] = False
        st.session_state["similar_role_found"] = None
        st.session_state["similar_role_slug"] = None
        
        # User selected a standard role
        role_idx = role_titles.index(selected_option)
        chosen_slug = role_slugs[role_idx]
        
        if st.button("🚀 Start AI Analysis", type="primary", use_container_width=True):
            st.session_state["target_role"] = chosen_slug
            _run_analysis_pipeline(file_bytes, filename, jd_text)


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

    # 1b. Render PDF to image & extract font metadata for Visual Polish Scanner
    if filename.lower().endswith(".pdf"):
        progress.progress(18, text="✨ Scanning visual layout & typography...")
        try:
            st.session_state["resume_image"] = parser.convert_pdf_to_image(file_bytes)
            st.session_state["font_metadata"] = parser.extract_font_metadata(file_bytes)
        except Exception as e:
            st.session_state["resume_image"] = None
            st.session_state["font_metadata"] = None
    else:
        st.session_state["resume_image"] = None
        st.session_state["font_metadata"] = None

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
    target_role = st.session_state.get("target_role")
    if not target_role:
        role_cats = extractor.map_to_category(skill_data["all_skills"])
        top_skill_cat = list(role_cats.keys())[0] if role_cats else "Unknown"
        target_role = prediction["top_category"]
        if target_role == "Unknown" or str(target_role).isdigit():
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

    # 8b. Run Visual Aesthetic Scanner
    if st.session_state.get("resume_image") is not None:
        progress.progress(90, text="✨ Auditing resume layout aesthetics...")
        try:
            from utils.ai_assistant import AIVisualEvaluator
            evaluator = AIVisualEvaluator()
            visual_analysis = evaluator.evaluate(
                st.session_state["resume_image"],
                st.session_state.get("font_metadata")
            )
            st.session_state["visual_analysis"] = visual_analysis
        except Exception as e:
            st.warning(f"Visual audit unavailable: {e}")
    else:
        st.session_state["visual_analysis"] = None

    # 9. Growth tracking
    progress.progress(93, text="📈 Calculating growth...")
    from utils.growth_tracker import GrowthTracker
    user = st.session_state.get("user")
    is_auth = bool(user and not st.session_state.get("is_anonymous"))
    previous = db.get_previous_version(user.id, filename) if is_auth else None
    growth = GrowthTracker.calculate_growth(analysis, skill_data["all_skills"], previous)
    st.session_state["growth_data"] = growth

    # 10. Save (authenticated users)
    if is_auth:
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

    # Section scores + score calculation breakdown
    if score_result and st.session_state.get("jd_match_result"):
        section_scores = st.session_state["jd_match_result"].get("section_scores", {})
        if section_scores:
            st.markdown("<br>**Section Breakdown:**", unsafe_allow_html=True)
            s1, s2, s3, s4 = st.columns(4)
            for col, (sec, val) in zip([s1, s2, s3, s4], section_scores.items()):
                with col:
                    st.metric(sec.title(), f"{val:.0f}%")

    if score_result:
        with st.expander("🔢 How was this score calculated?", expanded=False):
            comps = score_result.get("component_scores", {})
            
            def get_score_color(val):
                if val >= 80:
                    return "#43E97B" # 🟢 Strong Green
                elif val >= 55:
                    # LERP transition from yellow (#ffa421 -> RGB 255, 164, 33) to green (#43E97B -> RGB 67, 233, 123)
                    ratio = (val - 55) / 25.0
                    r = int(255 + (67 - 255) * ratio)
                    g = int(164 + (233 - 164) * ratio)
                    b = int(33 + (123 - 33) * ratio)
                    return f"#{r:02X}{g:02X}{b:02X}"
                else:
                    return "#FF6584" # 🔴 Weak Red
                    
            bert_val = comps.get("bert_semantic", 0) / 0.5
            skill_val = comps.get("skill_overlap", 0) / 0.3
            svm_val = comps.get("svm_confidence", 0) / 0.1
            edu_val = comps.get("education_match", 0) / 0.1
            total_val = score_result.get("final_score", 0)
            
            bert_color = get_score_color(bert_val)
            skill_color = get_score_color(skill_val)
            svm_color = get_score_color(svm_val)
            edu_color = get_score_color(edu_val)
            total_color = get_score_color(total_val)
            
            st.markdown(f"""<table style="width:100%; border-collapse: collapse; margin: 15px 0; background: rgba(255,255,255,0.01); border-radius: 8px; overflow: hidden; border: 1px solid rgba(255,255,255,0.08); font-size: 1.05rem;">
<thead>
<tr style="background: rgba(255,255,255,0.04); text-align: left; border-bottom: 1px solid rgba(255,255,255,0.08);">
<th style="padding: 12px; font-weight: 700; color: #FAFAFA;">Component</th>
<th style="padding: 12px; font-weight: 700; color: #FAFAFA; width: 90px;">Weight</th>
<th style="padding: 12px; font-weight: 700; color: #FAFAFA; width: 130px;">Your Score</th>
<th style="padding: 12px; font-weight: 700; color: #FAFAFA; width: 130px;">Contribution</th>
</tr>
</thead>
<tbody>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
<td style="padding: 12px; color: #C0C6D0;">Profile & Job Alignment</td>
<td style="padding: 12px; color: #C0C6D0;">50%</td>
<td style="padding: 12px; font-weight: 700; color: {bert_color};">{bert_val:.1f}%</td>
<td style="padding: 12px; font-weight: 700; color: {bert_color};">{comps.get("bert_semantic", 0):.1f}%</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
<td style="padding: 12px; color: #C0C6D0;">Technical Skills Match</td>
<td style="padding: 12px; color: #C0C6D0;">30%</td>
<td style="padding: 12px; font-weight: 700; color: {skill_color};">{skill_val:.1f}%</td>
<td style="padding: 12px; font-weight: 700; color: {skill_color};">{comps.get("skill_overlap", 0):.1f}%</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
<td style="padding: 12px; color: #C0C6D0;">Industry Target Accuracy</td>
<td style="padding: 12px; color: #C0C6D0;">10%</td>
<td style="padding: 12px; font-weight: 700; color: {svm_color};">{svm_val:.1f}%</td>
<td style="padding: 12px; font-weight: 700; color: {svm_color};">{comps.get("svm_confidence", 0):.1f}%</td>
</tr>
<tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
<td style="padding: 12px; color: #C0C6D0;">Academic Background Alignment</td>
<td style="padding: 12px; color: #C0C6D0;">10%</td>
<td style="padding: 12px; font-weight: 700; color: {edu_color};">{edu_val:.1f}%</td>
<td style="padding: 12px; font-weight: 700; color: {edu_color};">{comps.get("education_match", 0):.1f}%</td>
</tr>
<tr style="background: rgba(255,255,255,0.03); border-top: 1px solid rgba(255,255,255,0.1);">
<td style="padding: 12px; font-weight: 700; color: #FAFAFA;">Total</td>
<td style="padding: 12px; font-weight: 700; color: #FAFAFA;">100%</td>
<td style="padding: 12px;"></td>
<td style="padding: 12px; font-weight: 700; color: {total_color};">{total_val:.1f}%</td>
</tr>
</tbody>
</table>

<div style="font-size: 1.05rem; margin-top: 10px; font-weight: 600; color: #FAFAFA; display: flex; gap: 15px; align-items: center;">
<span>Thresholds:</span>
<span style="color: #43E97B;">🟢 Strong &ge; 80%</span>
<span style="color: #ffa421;">🟡 Moderate &ge; 55%</span>
<span style="color: #FF6584;">🔴 Weak &lt; 55%</span>
</div>""", unsafe_allow_html=True)
            st.caption("Industry accuracy score starts at 0% on your first run while systems warm up. Re-run analysis to see the updated score.")

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

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("⬅️ Back to Upload", use_container_width=True):
            st.session_state["app_stage"] = "upload"
            st.rerun()
    with c2:
        if st.button("✏️ Edit Extracted Data", use_container_width=True):
            st.session_state["app_stage"] = "review"
            st.rerun()
    with c3:
        if st.button("📊 Go to Dashboard", type="primary", use_container_width=True):
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
        db = _get_db()
        from utils.gap_analyzer import GapAnalyzer
        analyzer = GapAnalyzer(db)
        
        # Load all standard and custom categories dynamically
        known_roles = analyzer.get_all_known_roles() # list of (title, slug)
        
        # Also include any custom roles saved in session state (offline fallback)
        known_slugs = {slug for title, slug in known_roles}
        for k in st.session_state.keys():
            if k.startswith("custom_standards_"):
                slug = k.removeprefix("custom_standards_")
                if slug not in known_slugs:
                    title = slug.replace("_", " ").title()
                    known_roles.append((title, slug))
                    known_slugs.add(slug)
                    
        # Sort alphabetically
        known_roles = sorted(known_roles, key=lambda x: x[0])
        
        categories = [r[1] for r in known_roles]
        cat_display = [r[0] for r in known_roles]

        current_idx = 0
        target_lower = target_role.lower().replace(" ", "_") if target_role else ""
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
    
    col_nav1, col_nav2 = st.columns([1, 4])
    with col_nav1:
        if st.button("⬅️ Back to Review", use_container_width=True):
            st.session_state["app_stage"] = "review"
            st.rerun()

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
            sc1.metric("Profile Alignment (50%)", f"{comps['bert_semantic']:.1f}%")
            sc2.metric("Skills Match (30%)", f"{comps['skill_overlap']:.1f}%")
            sc3.metric("Industry Accuracy (10%)", f"{comps['svm_confidence']:.1f}%")
            sc4.metric("Academic Alignment (10%)", f"{comps['education_match']:.1f}%")
            st.caption("Final score = Alignment×50% + Skills Match×30% + Industry Accuracy×10% + Academic Alignment×10%")
            
        # Build dynamic roadmap items list
        roadmap_items = []
        
        comps_map = score_result.get("component_scores", {})
        bert_val = comps_map.get("bert_semantic", 0) / 0.5
        skill_val = comps_map.get("skill_overlap", 0) / 0.3
        svm_val = comps_map.get("svm_confidence", 0) / 0.1
        edu_val = comps_map.get("education_match", 0) / 0.1
        
        if bert_val < 80:
            roadmap_items.append(f"""<li style="margin-bottom: 1.3rem; padding-bottom: 1.0rem; border-bottom: 1px solid rgba(255,255,255,0.06);">
<div style="font-weight: 700; color: #FAFAFA; font-size: 1.1rem; margin-bottom: 0.3rem;">🧠 1. Boost Profile & Job Alignment (Current Score: {bert_val:.1f}% | 50% weight)</div>
<div style="color: #D1D1D6; font-size: 0.95rem; line-height: 1.55; margin-left: 1.5rem;">
<strong>Why it is low:</strong> Your descriptions might be too brief, use passive/generic terms, or lack context matching the job description's phrasing.
<br><span style="color: #43E97B; font-weight: 600;">💡 Core Action:</span> Elaborate on your accomplishments using the <span style="color: #6C63FF; font-weight: 700;">STAR method</span> (Situation, Task, Action, Result). Mimic active verbs (e.g. <em>orchestrated</em>, <em>engineered</em>, <em>streamlined</em>) from the Job Description to instantly raise alignment score.
</div>
</li>""")
            
        if skill_val < 80:
            missing_skills_list = st.session_state.get("missing_skills", [])
            missing_text = " Go to the <span style='color: #6C63FF; font-weight: 700;'>Skill Gaps</span> tab below and check the list of <span style='color: #FF6584; font-weight: 700;'>❌ Missing Skills</span>."
            if missing_skills_list:
                missing_text = f" We detected that you are missing key skills like: <strong>{', '.join(list(missing_skills_list)[:3])}</strong>."
            roadmap_items.append(f"""<li style="margin-bottom: 1.3rem; padding-bottom: 1.0rem; border-bottom: 1px solid rgba(255,255,255,0.06);">
<div style="font-weight: 700; color: #FAFAFA; font-size: 1.1rem; margin-bottom: 0.3rem;">🎯 2. Boost Technical Skills Match (Current Score: {skill_val:.1f}% | 30% weight)</div>
<div style="color: #D1D1D6; font-size: 0.95rem; line-height: 1.55; margin-left: 1.5rem;">
<strong>Why it is low:</strong> You are missing specific technical tools, programming languages, or platforms required by the employer.
<br><span style="color: #43E97B; font-weight: 600;">💡 Core Action:</span>{missing_text} Weave these exact keywords naturally into your resume’s skill inventory and experience bullets.
</div>
</li>""")
            
        if svm_val < 80:
            roadmap_items.append(f"""<li style="margin-bottom: 1.3rem; padding-bottom: 1.0rem; border-bottom: 1px solid rgba(255,255,255,0.06);">
<div style="font-weight: 700; color: #FAFAFA; font-size: 1.1rem; margin-bottom: 0.3rem;">💼 3. Boost Industry Target Accuracy (Current Score: {svm_val:.1f}% | 10% weight)</div>
<div style="color: #D1D1D6; font-size: 0.95rem; line-height: 1.55; margin-left: 1.5rem;">
<strong>Why it is low:</strong> Your overall profile reads too broadly or matches multiple professional categories, dropping classifier confidence for your target role.
<br><span style="color: #43E97B; font-weight: 600;">💡 Core Action:</span> Open your resume with a clear <span style="color: #6C63FF; font-weight: 700;">professional summary header</span> containing your target job title (e.g., <em>"{target_role.replace('_', ' ').title()} with 2+ years of experience..."</em>). Focus your experience descriptions purely on tasks specific to this professional domain.
</div>
</li>""")
            
        if edu_val < 80:
            roadmap_items.append(f"""<li style="margin-bottom: 0;">
<div style="font-weight: 700; color: #FAFAFA; font-size: 1.1rem; margin-bottom: 0.3rem;">🎓 4. Boost Academic Background Alignment (Current Score: {edu_val:.1f}% | 10% weight)</div>
<div style="color: #D1D1D6; font-size: 0.95rem; line-height: 1.55; margin-left: 1.5rem;">
<strong>Why it is low:</strong> Your educational field (major or degree title) is missing or parsed differently than standard major profiles.
<br><span style="color: #43E97B; font-weight: 600;">💡 Core Action:</span> Clearly define your <span style="color: #6C63FF; font-weight: 700;">degree name and field of study</span> under your education section (e.g., <em>"B.S. in Computer Science"</em> or <em>"M.S. in Business Analytics"</em>), matching conventional academic naming.
</div>
</li>""")
            
        if not roadmap_items:
            roadmap_items.append(f"""<li style="margin-bottom: 0; text-align: center; padding: 1.5rem;">
<div style="font-weight: 700; color: #43E97B; font-size: 1.25rem; margin-bottom: 0.5rem;">🎉 Outstanding Profile!</div>
<div style="color: #D1D1D6; font-size: 1.0rem; line-height: 1.6;">
Your resume is highly optimized and demonstrates exceptionally strong alignment across all four matching dimensions! Focus on practicing standard interview simulations in our <strong>AI Coach</strong> tab to finalize your prep.
</div>
</li>""")
            
        roadmap_content = "\n".join(roadmap_items)
        st.markdown(f"""<div class="glass-panel" style="padding: 1.7rem; border-radius: 12px; border: 1px solid rgba(255,255,255,0.08); background: rgba(17,17,21,0.65); margin-top: 1rem; margin-bottom: 1rem;">
<h4 style="margin-top: 0; color: #43E97B; font-size: 1.3rem; display: flex; align-items: center; gap: 8px;">🛠️ Actionable Roadmap to Boost Your Score</h4>
<p style="color: #A1A1AA; font-size: 1.0rem; margin-bottom: 1.3rem; line-height: 1.6;">
{"Your profile requires some targeted enhancements to maximize alignment with employer expectations. Focus on the custom items below:" if bert_val < 80 or skill_val < 80 or svm_val < 80 or edu_val < 80 else "Your profile is fully optimized! Review your alignment indicators below:"}
</p>
<ul style="list-style-type: none; padding-left: 0; margin-bottom: 0;">
{roadmap_content}
</ul>
</div>""", unsafe_allow_html=True)

    # ── Section scores bar chart ──
    if jd_match and jd_match.get("section_scores"):
        with st.expander("📊 Section-Level Alignment Scores", expanded=True):
            st.markdown("""
            This chart displays how closely each distinct section of your resume (Education, Experience, Skills, and Summary) semantically aligns with the context and intent of the Job Description. **Higher/greener bars indicate stronger relevance and a closer contextual match to the employer's expectations.**
            """)
            
            section_scores = jd_match["section_scores"]
            
            # Draw beautiful custom HTML bar chart
            bars_html = ""
            for sec, val in section_scores.items():
                # Get dynamic color
                if val >= 80:
                    color = "#43E97B" # 🟢 Strong Green
                elif val >= 55:
                    ratio = (val - 55) / 25.0
                    r = int(255 + (67 - 255) * ratio)
                    g = int(164 + (233 - 164) * ratio)
                    b = int(33 + (123 - 33) * ratio)
                    color = f"#{r:02X}{g:02X}{b:02X}"
                else:
                    color = "#FF6584" # 🔴 Weak Red
                    
                height_pct = max(val, 5) # Ensure visible bar
                
                # Convert hex to RGB values for gradient shadow
                r_val = int(color[1:3], 16)
                g_val = int(color[3:5], 16)
                b_val = int(color[5:7], 16)
                
                bars_html += f"""<div style="display: flex; flex-direction: column; align-items: center; width: 22%;">
<div style="height: 220px; width: 100%; display: flex; align-items: flex-end; background: rgba(255,255,255,0.03); border-radius: 8px; position: relative;">
<div style="height: {height_pct}%; width: 100%; background: linear-gradient(180deg, {color}, rgba({r_val}, {g_val}, {b_val}, 0.1)); border-radius: 6px; box-shadow: 0 0 15px rgba({r_val}, {g_val}, {b_val}, 0.3); transition: all 0.3s ease;">
<span style="position: absolute; top: -25px; left: 50%; transform: translateX(-50%); color: #FAFAFA; font-weight: 700; font-size: 0.95rem;">{val:.0f}%</span>
</div>
</div>
<span style="color: #FAFAFA; font-weight: 600; font-size: 1rem; margin-top: 10px; text-transform: capitalize; text-align: center;">{sec}</span>
</div>"""
                
            st.markdown(f"""<div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 2rem 1.5rem 1.5rem 1.5rem; margin-top: 1rem;">
<div style="display: flex; justify-content: space-between; align-items: flex-end; height: 260px;">
{bars_html}
</div>
</div>""", unsafe_allow_html=True)
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
    tab_labels = ["✅ Your Skills", "❌ Skill Gaps", "🤖 AI Feedback", "🎨 Visual Polish", "🎓 Learning Plan", "💬 AI Coach"]
    tab_skills, tab_gaps, tab_feedback, tab_visual, tab_plan, tab_ai = st.tabs(tab_labels)

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
            source = ai_feedback.get("_source", "rule_based")
            _provider_labels = {
                "claude":     ("✅", "Powered by Anthropic Claude"),
                "claude_api": ("✅", "Powered by Anthropic Claude"),
                "gemini":     ("✅", "Powered by Google Gemini"),
                "rule_based": ("ℹ️", "Rule-based feedback — add GEMINI_API_KEY or ANTHROPIC_API_KEY to .streamlit/secrets.toml for AI-powered feedback"),
            }
            _icon, _label = _provider_labels.get(source, ("ℹ️", f"Provider: {source}"))
            if source == "rule_based":
                st.info(f"{_icon} {_label}")
                if st.session_state.get("gemini_error"):
                    st.error(f"⚠️ **Gemini API Error Details:** {st.session_state['gemini_error']}")
            else:
                st.success(f"{_icon} {_label}")

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
                    
            # Interview Questions (fufilling 3.4.3 research specification)
            if ai_feedback.get("interview_questions"):
                st.markdown("<br>#### 🎯 Custom Interview Prep", unsafe_allow_html=True)
                st.caption("Customized technical and behavioral questions based on your profile and gaps:")
                for i, q in enumerate(ai_feedback["interview_questions"], 1):
                    st.markdown(f"""
                    <div class="glass-panel" style="padding:0.8rem; margin-bottom: 0.6rem; border-left: 3px solid #43E97B; background: rgba(255,255,255,0.02)">
                        <strong>Q{i}:</strong> {q}
                    </div>
                    """, unsafe_allow_html=True)
        elif not jd_text:
            st.info("💡 Paste a job description on the upload page to get AI recruiter feedback.")
        else:
            st.warning("AI feedback was not generated. Check your ANTHROPIC_API_KEY in Streamlit secrets.")

    with tab_visual:
        st.markdown("### 🎨 Resume Visual Polish Scanner")
        
        if st.session_state.get("resume_image") is None:
            st.info("ℹ️ Visual Polish Scanner is only available for PDF resumes. Please upload a PDF resume file to enable interactive visual layout analysis.")
        elif not st.session_state.get("visual_analysis"):
            st.warning("⚠️ Visual analysis report was not generated. Ensure your GEMINI_API_KEY is configured in Streamlit secrets.")
        else:
            visual_analysis = st.session_state["visual_analysis"]
            
            # 1. Scorecard Columns
            c_score1, c_score2, c_score3 = st.columns(3)
            with c_score1:
                st.metric("✨ Visual Polish Score", f"{visual_analysis.get('visual_polish_score', 0)}/100")
            with c_score2:
                st.metric("📏 Style Consistency", f"{visual_analysis.get('consistency_score', 0)}/100")
            with c_score3:
                st.metric("👀 Scannability & Hierarchy", f"{visual_analysis.get('hierarchy_score', 0)}/100")
                
            # 2. Layout Recruiter Summary
            st.markdown("#### 💡 Expert Recruiter Summary")
            st.markdown(f"""
            <div class="glass-panel" style="padding:1.1rem; border-left:4px solid #43E97B; margin-bottom: 1.5rem;">
                {visual_analysis.get('recruiter_notes', 'No layout notes available.')}
            </div>
            """, unsafe_allow_html=True)
            
            # 3. Split-view: Image Hotspots vs Red Flags List
            vis_left, vis_right = st.columns([5, 4], gap="large")
            
            with vis_left:
                st.markdown("#### 📄 Interactive Resume Hotspots")
                st.caption("Hover over the transparent-red highlight boxes on your resume to inspect specific design issues:")
                
                # Dynamic HTML component injection
                try:
                    import base64
                    img_bytes = st.session_state["resume_image"]
                    img_b64 = base64.b64encode(img_bytes).decode("utf-8")
                    
                    html_content = """
                    <style>
                    .resume-wrapper {
                        position: relative;
                        display: inline-block;
                        width: 100%;
                        max-width: 650px;
                        border-radius: 8px;
                        overflow: hidden;
                        border: 1px solid rgba(255,255,255,0.15);
                        background: #111115;
                        box-shadow: 0 8px 32px rgba(0,0,0,0.5);
                    }
                    .resume-image {
                        display: block;
                        width: 100%;
                        height: auto;
                    }
                    .hotspot {
                        position: absolute;
                        background: rgba(255, 101, 132, 0.18);
                        border: 1.5px dashed rgba(255, 101, 132, 0.7);
                        border-radius: 4px;
                        cursor: pointer;
                        transition: all 0.3s ease;
                        z-index: 10;
                    }
                    .hotspot:hover {
                        background: rgba(255, 101, 132, 0.38);
                        border: 1.5px solid rgba(255, 101, 132, 1);
                        box-shadow: 0 0 15px rgba(255, 101, 132, 0.7);
                        z-index: 100;
                    }
                    .hotspot .tooltip {
                        visibility: hidden;
                        position: absolute;
                        bottom: 110%;
                        left: 50%;
                        transform: translateX(-50%);
                        background: rgba(17, 17, 21, 0.98);
                        color: #FAFAFA;
                        padding: 10px 14px;
                        border-radius: 6px;
                        font-size: 11.5px;
                        width: 240px;
                        line-height: 1.45;
                        border: 1px solid rgba(255, 101, 132, 0.5);
                        box-shadow: 0 8px 24px rgba(0,0,0,0.6);
                        z-index: 999;
                        opacity: 0;
                        transition: opacity 0.25s ease-in-out;
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        pointer-events: none;
                    }
                    .hotspot:hover .tooltip {
                        visibility: visible;
                        opacity: 1;
                    }
                    .hotspot .tooltip-title {
                        font-weight: 700;
                        color: #FF6584;
                        margin-bottom: 4px;
                        font-size: 12.5px;
                    }
                    </style>
                    <div class="resume-wrapper">
                        <img src="data:image/png;base64,{img_base64}" class="resume-image" />
                    """
                    
                    red_flags = visual_analysis.get("red_flags", [])
                    for flag in red_flags:
                        box = flag.get("box_2d")
                        if box and len(box) == 4:
                            ymin, xmin, ymax, xmax = box
                            top = ymin / 10.0
                            left = xmin / 10.0
                            height = (ymax - ymin) / 10.0
                            width = (xmax - xmin) / 10.0
                            
                            issue_esc = flag.get("issue", "").replace('"', '&quot;')
                            reason_esc = flag.get("reason", "").replace('"', '&quot;')
                            
                            html_content += f"""
                            <div class="hotspot" style="top: {top}%; left: {left}%; width: {width}%; height: {height}%;">
                                <div class="tooltip">
                                    <div class="tooltip-title">⚠️ {issue_esc}</div>
                                    <div>{reason_esc}</div>
                                </div>
                            </div>
                            """
                    html_content += "</div>"
                    st.components.v1.html(html_content.replace("{img_base64}", img_b64), height=820)
                except Exception as html_err:
                    st.error(f"Failed to render interactive image: {html_err}")
                    
            with vis_right:
                st.markdown("#### 🚨 Layout Formatting Audit")
                red_flags = visual_analysis.get("red_flags", [])
                if red_flags:
                    for i, flag in enumerate(red_flags, 1):
                        st.markdown(f"""
                        <div class="glass-panel" style="padding:0.9rem; margin-bottom: 0.8rem; border-left:3px solid #FF6584; background:rgba(255,101,132,0.02)">
                            <strong style="color:#FF6584">⚠️ {i}. {flag.get('issue')}</strong>
                            <div style="font-size:0.86rem; color:#A1A1AA; margin-top:0.3rem;">{flag.get('reason')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.success("🎉 No layout formatting issues detected! Your resume design is flawless.")

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
            top_keywords = [k[0] for k in expl.get("positive", [])[:6]]
            
            st.markdown(f"### 🤝 Match Analysis for **{role_display}**")
            
            if top_keywords:
                kw_badges = " ".join([f'<span style="background: rgba(108, 99, 255, 0.15); color: #8F8AFF; border: 1px solid rgba(108, 99, 255, 0.3); padding: 4px 10px; border-radius: 20px; font-size: 0.85rem; margin: 4px; display: inline-block; font-weight: 500;">{k}</span>' for k in top_keywords])
                
                st.markdown(f"""
                <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.5rem; margin-bottom: 1.5rem;">
                    <h5 style="color: #43E97B; margin-top: 0; font-size: 1.1rem; display: flex; align-items: center; gap: 8px;">
                        <span>✨ Recruiter Assessment</span>
                    </h5>
                    <p style="color: #E4E4E7; font-size: 1rem; line-height: 1.6; margin-bottom: 1rem;">
                        Our semantic match engine analyzed your resume against the industry standards for a <b>{role_display}</b>. 
                        Your profile demonstrates a strong foundational alignment, heavily anchored by key domain concepts and technical competencies detected in your experience and projects.
                    </p>
                    <div style="margin-top: 1rem;">
                        <span style="color: #A1A1AA; font-size: 0.9rem; font-weight: 600; display: block; margin-bottom: 8px;">Key Influence Keywords:</span>
                        <div>{kw_badges}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown("#### Domain Alignment Analysis")
                p_df = pd.DataFrame(expl["positive"][:10], columns=["Keyword", "Impact"])
                st.markdown("<p style='color: #A1A1AA; font-size: 0.95rem; margin-bottom: 1rem;'>Visual breakdown of the semantic weight and relevance score of each matching concept extracted from your resume:</p>", unsafe_allow_html=True)
                
                for idx, row in p_df.iterrows():
                    kw = row["Keyword"]
                    val = row["Impact"]
                    max_val = p_df["Impact"].max() if p_df["Impact"].max() > 0 else 1.0
                    pct = min(int((val / max_val) * 100), 100)
                    st.markdown(f"""
                    <div style="margin-bottom: 0.75rem;">
                        <div style="display: flex; justify-content: space-between; font-size: 0.9rem; margin-bottom: 3px; font-weight: 500;">
                            <span style="color: #E4E4E7;">{kw}</span>
                            <span style="color: #8F8AFF;">Semantic Relevance: {pct}%</span>
                        </div>
                        <div style="background: rgba(255,255,255,0.05); border-radius: 4px; height: 8px; width: 100%; overflow: hidden;">
                            <div style="background: linear-gradient(90deg, #6C63FF, #43E97B); width: {pct}%; height: 100%; border-radius: 4px;"></div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; padding: 1.5rem;">
                    <p style="color: #A1A1AA; font-size: 1rem;">No strong direct keyword correlations could be extracted. The match score is primarily determined by general semantic role mapping.</p>
                </div>
                """, unsafe_allow_html=True)

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
# Welcome Screen Component (Main Landing Page)
# ==============================================================================
def render_welcome_stage():
    """Glow-effect welcome page with integrated sign-in/up/guest onboarding."""
    st.markdown("""
    <div class="hero-container animate-in" style="text-align: center; padding: 2rem 1rem;">
        <h1 style="font-size: 2.8rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, #6C63FF, #43E97B); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">🎯 Deep Career Coach</h1>
        <p class="hero-subtitle" style="font-size: 1.15rem; max-width: 750px; margin: 0 auto 1.5rem auto; color: #A1A1AA; line-height: 1.6;">
            Get an instant AI-powered match score, deep skill gap analysis, 
            personalized learning roadmaps, and chat with your smart career coach.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div class="glass-panel animate-in animate-in-delay-1" style="padding: 1.5rem; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); background: rgba(17,17,21,0.6); margin-bottom: 1.5rem;">
            <h3 style="text-align: center; margin-top: 0; color: #FAFAFA; font-size: 1.3rem;">🚀 Get Started</h3>
            <p style="text-align: center; color: #71717A; font-size: 0.9rem; margin-bottom: 0;">Please sign in or continue as guest to begin your resume analysis.</p>
        </div>
        """, unsafe_allow_html=True)

        tabs = st.tabs(["🔑 Sign In", "📝 Sign Up", "👻 Continue as Guest"])
        
        with tabs[0]:
            with st.form("welcome_login_form"):
                email = st.text_input("Email", placeholder="your-email@example.com", key="welcome_login_email")
                password = st.text_input("Password", type="password", key="welcome_login_pwd")
                submitted = st.form_submit_button("Sign In", type="primary", use_container_width=True)
                if submitted:
                    db = _get_db()
                    res, err = db.sign_in(email, password)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.session_state["user"] = res.user
                        st.session_state["is_anonymous"] = False
                        _sync_session_analysis_to_db(db, res.user.id)
                        st.toast(f"Welcome back, {res.user.email}! 👋", icon="✅")
                        st.rerun()

            with st.expander("🔑 Forgot Password?"):
                reset_email = st.text_input("Enter email to receive reset link", key="welcome_reset_email")
                if st.button("Send Reset Link", key="welcome_reset_btn", use_container_width=True):
                    if reset_email:
                        db = _get_db()
                        _, err = db.reset_password(reset_email)
                        if err:
                            st.error(f"❌ {err}")
                        else:
                            st.success("✉️ Password reset link sent to your email!")
                    else:
                        st.warning("Please enter your email address first.")

        with tabs[1]:
            with st.form("welcome_signup_form"):
                email = st.text_input("Email Address", placeholder="name@domain.com", key="welcome_signup_email")
                password = st.text_input("Choose Password", type="password", key="welcome_signup_pwd")
                full_name = st.text_input("Full Name", placeholder="Jane Doe", key="welcome_signup_name")
                submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)
                if submitted:
                    db = _get_db()
                    res, err = db.sign_up(email, password, full_name)
                    if err:
                        st.error(f"❌ {err}")
                    else:
                        st.success("📧 Verification email sent! Please check your inbox.")

        with tabs[2]:
            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown("""
            <div style="text-align: center; margin-bottom: 1.5rem; font-size: 0.9rem; color: #A1A1AA; line-height: 1.5;">
                Perfect for a quick test run. We will score your resume and show 
                your gaps immediately, but you won't be able to save your history.
            </div>
            """, unsafe_allow_html=True)
            if st.button("👻 Start in Guest Mode", type="primary", use_container_width=True):
                class GuestUser:
                    def __init__(self):
                        self.id = "guest_session"
                        self.email = "guest@local"
                st.session_state["user"] = GuestUser()
                st.session_state["is_anonymous"] = True
                st.toast("Entered Guest Mode! 👻", icon="👻")
                st.rerun()


# ==============================================================================
# Router
# ==============================================================================
def main():
    db = render_sidebar()
    
    # --- PKCE Password Reset Handler ---
    if "code" in st.query_params:
        code = st.query_params["code"]
        res, err = db.exchange_code(code)
        if err:
            st.error(f"❌ Reset Link Auth Failed: {err}")
        else:
            st.session_state["user"] = res.user
            st.session_state["is_anonymous"] = False
            st.session_state["reset_password_mode"] = True
            # Clear params so we don't repeat exchange on rerun
            st.query_params.clear()
            st.toast("🔑 Authenticated via recovery link! Please set your new password.", icon="🔑")
            st.rerun()

    # --- Reset Password Form Mode ---
    if st.session_state.get("reset_password_mode"):
        st.markdown("""
        <div class="glass-panel" style="padding: 2rem; border-radius: 16px; border: 1px solid rgba(255,255,255,0.08); background: rgba(17,17,21,0.6); margin-top: 2rem; margin-bottom: 2rem;">
            <h3 style="color: #6C63FF; margin-top: 0;">🔄 Reset Your Password</h3>
            <p style="color: #A1A1AA; font-size: 0.9rem;">You have been securely authenticated via recovery link. Please choose a strong new password below.</p>
        </div>
        """, unsafe_allow_html=True)
        with st.form("reset_password_form"):
            new_pwd = st.text_input("New Password", type="password")
            confirm_pwd = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Update Password", type="primary", use_container_width=True):
                if not new_pwd:
                    st.error("Password cannot be empty.")
                elif new_pwd != confirm_pwd:
                    st.error("Passwords do not match.")
                else:
                    try:
                        db.supabase.auth.update_user({"password": new_pwd})
                        st.session_state["reset_password_mode"] = False
                        st.success("🎉 Password updated successfully! You can now use your new password.")
                        st.toast("Password reset successful! 🎉", icon="✅")
                    except Exception as e:
                        st.error(f"Failed to update password: {e}")
        return

    user = st.session_state.get("user")
    
    if not user:
        render_welcome_stage()
        return

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
