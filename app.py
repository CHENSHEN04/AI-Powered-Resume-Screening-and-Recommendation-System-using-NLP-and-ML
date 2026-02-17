"""
AI-Powered Resume Screening and Recommendation System
======================================================
Main Streamlit entry point – implements the "Teaser" funnel:

    Upload → Anonymous Score → Login/Register → Full Report

Flow controlled by `st.session_state["app_stage"]`:
    "upload"  → hero + file uploader
    "teaser"  → anonymous score card + CTA
    "review"  → split-view data verification
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
    from utils.ai_assistant import AIAssistant
except ImportError:
    AIAssistant = None


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
    "app_stage": "upload",        # upload → teaser → review → dashboard
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
    "reviewed_skills": None,      # User-edited skill list after review
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ==============================================================================
# Sidebar – Auth + Navigation
# ==============================================================================
def render_sidebar():
    db = DatabaseManager()
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
                            # Go straight to dashboard if analysis exists
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
        # Stage indicator
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
                st.session_state["user"] = user  # Keep user logged in
                st.session_state["is_anonymous"] = is_anon
                st.rerun()

    return db

# ==============================================================================
# Stage 1: Upload (Hero + File Uploader)
# ==============================================================================
def render_upload_stage():
    st.markdown("""
    <div class="hero-container animate-in">
        <h1>Deep Career Coach</h1>
        <p class="hero-subtitle">
            Upload your resume and get an instant AI-powered career analysis with
            personalized skill gap insights, learning paths, and growth tracking.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Feature cards
    cols = st.columns(3)
    features = [
        ("🔍", "Smart Parsing", "PDF & DOCX with confidence scoring"),
        ("🧠", "AI Classification", "Hybrid SVM + BERT job matching"),
        ("📊", "Gap Analysis", "Personalized skill roadmap"),
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

    # Upload
    uploaded_file = st.file_uploader(
        "📄 Drop your resume here (PDF or DOCX)",
        type=["pdf", "docx"],
        help="Max 10MB. We support PDF and DOCX formats."
    )

    if uploaded_file:
        file_bytes = uploaded_file.getvalue()

        # Rate limits
        user = st.session_state.get("user")
        if user:
            user_id = user.email if not st.session_state.get("is_anonymous") else user.id
            is_auth = not st.session_state.get("is_anonymous")
        else:
            user_id = "anonymous"
            is_auth = False

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

        if st.button("🚀 Analyze Now", type="primary", use_container_width=True):
            st.session_state["file_bytes"] = file_bytes
            st.session_state["uploaded_file_name"] = uploaded_file.name
            _run_analysis_pipeline(file_bytes, uploaded_file.name)


def _run_analysis_pipeline(file_bytes: bytes, filename: str):
    """Run the full analysis pipeline and advance to teaser stage."""
    db = DatabaseManager()
    progress = st.progress(0, text="Starting analysis...")

    # 1. Parse
    progress.progress(15, text="📄 Parsing resume...")
    from utils.parser import ResumeParser
    parser = ResumeParser()
    parse_result = parser.parse(file_bytes, filename)

    if not parse_result.success:
        st.session_state["parse_result"] = parse_result
        if parse_result.error:
            show_error(parse_result.error)
        return

    st.session_state["parse_result"] = parse_result

    # Check for empty / minimal resume → Builder Mode
    if parse_result.confidence < 0.3 or len(parse_result.text.strip()) < 100:
        st.session_state["app_stage"] = "builder"
        st.rerun()
        return

    # 2. Extract Skills
    progress.progress(35, text="🧠 Extracting skills...")
    from utils.skill_extractor import SkillExtractor
    extractor = SkillExtractor()
    skill_data = extractor.extract_skills(parse_result.text)
    st.session_state["skill_data"] = skill_data

    # 3. Classify
    progress.progress(55, text="🔮 Identifying career match...")
    from utils.classifier import JobClassifier
    classifier = JobClassifier()
    prediction = classifier.predict(parse_result.text)
    st.session_state["prediction"] = prediction
    st.session_state["explanation"] = classifier.explain_prediction(parse_result.text)

    # 4. Gap Analysis
    progress.progress(75, text="📊 Analyzing skill gaps...")
    from utils.gap_analyzer import GapAnalyzer
    analyzer = GapAnalyzer(db)
    role_cats = extractor.map_to_category(skill_data["all_skills"])
    top_skill_cat = list(role_cats.keys())[0] if role_cats else "Unknown"

    target_role = prediction["top_category"]
    if target_role == "Unknown" or str(target_role).isdigit():
        target_role = top_skill_cat
    st.session_state["target_role"] = target_role

    analysis = analyzer.analyze_gaps(skill_data["all_skills"], target_role)
    st.session_state["gap_analysis"] = analysis

    # 5. Growth
    progress.progress(90, text="📈 Calculating growth...")
    from utils.growth_tracker import GrowthTracker
    user = st.session_state.get("user")
    previous = None
    if user:
        previous = db.get_previous_version(user.id, filename)
    growth = GrowthTracker.calculate_growth(analysis, skill_data["all_skills"], previous)
    st.session_state["growth_data"] = growth

    # 6. Save (if authenticated)
    if user:
        db.save_resume_analysis(user.id, {
            "filename": filename,
            "storage_path": f"resumes/{user.id}/{filename}",
            "parsed_text": parse_result.text,
            "page_count": parse_result.page_count,
            "confidence_score": parse_result.confidence,
            "predicted_role": target_role,
            "match_score": analysis["match_percentage"],
            "skills": [{"name": s, "category": "extracted"} for s in skill_data["all_skills"]]
        })

    progress.progress(100, text="✅ Done!")
    time.sleep(0.3)

    # Advance stage
    st.session_state["app_stage"] = "teaser"
    st.rerun()


# ==============================================================================
# Stage 2: Teaser (Anonymous Score Card + CTA)
# ==============================================================================
def render_teaser_stage():
    analysis = st.session_state["gap_analysis"]
    skill_data = st.session_state["skill_data"]
    target_role = st.session_state.get("target_role", "Unknown")
    score = analysis["match_percentage"]

    st.markdown("<div class='animate-in'>", unsafe_allow_html=True)
    st.markdown("## 🎯 Your Career Match Preview")

    # Score Card
    color = "#43E97B" if score >= 70 else "#ffa421" if score >= 40 else "#FF6584"
    st.markdown(f"""
    <div class="teaser-score animate-in animate-in-delay-1">
        <div class="score-number" style="-webkit-text-fill-color: {color}">{score:.0f}%</div>
        <div class="score-label">Match for <strong>{target_role.replace('_', ' ').title()}</strong></div>
    </div>
    """, unsafe_allow_html=True)

    # Quick Stats
    cols = st.columns(3)
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
            <div class="metric-value">{len(analysis['missing_required'])}</div>
            <div class="metric-label">Critical Gaps</div>
        </div>
        """, unsafe_allow_html=True)
    with cols[2]:
        st.markdown(f"""
        <div class="metric-card animate-in animate-in-delay-3">
            <div class="metric-value">{len(analysis.get('recommendations', []))}</div>
            <div class="metric-label">Action Items</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Blurred preview of top skills
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

    # CTA: Review or Dashboard
    c1, c2 = st.columns(2)
    with c1:
        if st.button("✏️ Review & Edit Extracted Data", use_container_width=True):
            st.session_state["app_stage"] = "review"
            st.rerun()
    with c2:
        if st.button("📊 Go to Full Dashboard", type="primary", use_container_width=True):
            st.session_state["app_stage"] = "dashboard"
            st.rerun()

    # Guest CTA
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
    skill_data = st.session_state["skill_data"]
    target_role = st.session_state.get("target_role", "Unknown")

    # Desktop: 2-column split view
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
        conf_color = "#43E97B" if conf >= 0.7 else "#ffa421" if conf >= 0.4 else "#FF6584"
        st.progress(conf, text=f"{conf*100:.0f}% confidence")
        if conf < 0.7:
            show_warning(
                "Low confidence parsing. Please double-check critical fields.",
                "The AI may have missed some information due to formatting."
            )

    with right:
        st.markdown("### 🧠 Extracted Data")

        # Target Role Override
        st.markdown("#### 🎯 Predicted Target Role")
        # Load categories for dropdown
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

        # Skills Editor
        st.markdown("#### 🛠️ Skills Found")
        current_skills = skill_data.get("all_skills", [])

        # Editable list
        edited_skills = st.text_area(
            "Edit skills (one per line):",
            value="\n".join(current_skills),
            height=200,
            key="skill_editor"
        )

        # Add new skill
        new_skill = st.text_input("➕ Add a skill:", key="add_skill_input")
        if new_skill:
            lines = edited_skills.strip().split("\n") if edited_skills.strip() else []
            if new_skill not in lines:
                lines.append(new_skill)
                edited_skills = "\n".join(lines)

    st.markdown("---")

    # Action buttons
    c1, c2 = st.columns(2)
    with c1:
        if st.button("⬅️ Back to Preview", use_container_width=True):
            st.session_state["app_stage"] = "teaser"
            st.rerun()
    with c2:
        if st.button("✅ Confirm & View Dashboard", type="primary", use_container_width=True):
            # Save reviewed skills
            final_skills = [s.strip() for s in edited_skills.strip().split("\n") if s.strip()]
            st.session_state["reviewed_skills"] = final_skills
            st.session_state["skill_data"]["all_skills"] = final_skills
            st.session_state["skill_data"]["count"] = len(final_skills)

            # Re-run gap analysis with new role + skills
            from utils.gap_analyzer import GapAnalyzer
            db = DatabaseManager()
            analyzer = GapAnalyzer(db)
            new_analysis = analyzer.analyze_gaps(
                final_skills,
                st.session_state["target_role"]
            )
            st.session_state["gap_analysis"] = new_analysis

            st.session_state["app_stage"] = "dashboard"
            st.rerun()


# ==============================================================================
# Stage 3b: Builder Mode (Empty / Minimal Resumes)
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
            graduation_year = st.selectbox(
                "🎓 Expected Graduation",
                [str(y) for y in range(2024, 2030)]
            )
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

        submitted = st.form_submit_button("🚀 Generate My Profile", type="primary",
                                          use_container_width=True)

    if submitted:
        skills_list = [s.strip() for s in known_skills.strip().split("\n") if s.strip()]

        # Build synthetic skill data
        st.session_state["skill_data"] = {
            "all_skills": skills_list,
            "count": len(skills_list),
            "detailed_skills": [{"name": s, "sources": ["self_reported"], "weight_score": 0.5} for s in skills_list]
        }

        # Use dream role or interest-based mapping
        target = dream_role.lower().replace(" ", "_") if dream_role else "software_engineer"
        st.session_state["target_role"] = target
        st.session_state["prediction"] = {
            "top_category": target,
            "confidence": 0.5,
            "all_scores": {target: 0.5}
        }

        # Run gap analysis
        from utils.gap_analyzer import GapAnalyzer
        db = DatabaseManager()
        analyzer = GapAnalyzer(db)
        analysis = analyzer.analyze_gaps(skills_list, target)
        st.session_state["gap_analysis"] = analysis

        # No growth data for builder mode
        st.session_state["growth_data"] = {
            "score_delta": 0, "skills_added": [], "is_improved": False, "first_upload": True
        }

        st.session_state["app_stage"] = "dashboard"
        st.rerun()


# ==============================================================================
# Stage 4: Full Dashboard (Deep Coach)
# ==============================================================================
def render_dashboard_stage():
    analysis = st.session_state["gap_analysis"]
    skill_data = st.session_state["skill_data"]
    target_role = st.session_state.get("target_role", "Unknown")
    prediction = st.session_state.get("prediction", {})
    growth_data = st.session_state.get("growth_data")

    # --- Header ---
    role_display = target_role.replace("_", " ").title()
    st.markdown(f"## 🎯 Career Dashboard — {role_display}")

    # --- Growth Banner ---
    if growth_data:
        from utils.growth_tracker import GrowthTracker
        GrowthTracker.render_growth_metrics(growth_data)

    st.markdown("---")

    # --- Row 1: Executive Metrics ---
    m1, m2, m3, m4 = st.columns(4)
    score = analysis["match_percentage"]
    with m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{score:.0f}%</div>
            <div class="metric-label">Match Score</div>
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
            <div class="metric-value">{len(analysis['missing_required'])}</div>
            <div class="metric-label">Critical Gaps</div>
        </div>
        """, unsafe_allow_html=True)
    with m4:
        conf = prediction.get("confidence", 0)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{conf*100:.0f}%</div>
            <div class="metric-label">AI Confidence</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # --- Export ---
    try:
        from utils.pdf_generator import PDFGenerator
        pdf_gen = PDFGenerator()
        pdf_data = {
            "role": target_role,
            "match_percentage": analysis["match_percentage"],
            "missing_required": analysis["missing_required"],
            "missing_recommended": analysis["missing_recommended"],
            "learning_paths": analysis["learning_paths"],
            "recommendations": analysis["recommendations"]
        }
        user_name = st.session_state["user"].email if st.session_state.get("user") else "Guest"
        pdf_buffer = pdf_gen.generate_report(pdf_data, user_name)
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

    # --- Row 2: Charts ---
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

    # --- Row 3: Tabs (Skills / Gaps / Learning Plan / AI Coach) ---
    tab_skills, tab_gaps, tab_plan, tab_ai = st.tabs(["✅ Your Skills", "❌ Skill Gaps", "🎓 Learning Plan", "🤖 AI Coach"])

    with tab_skills:
        if skill_data["all_skills"]:
            pills = " ".join(
                [f'<span class="skill-pill present">{s}</span>' for s in skill_data["all_skills"]]
            )
            st.markdown(pills, unsafe_allow_html=True)
        else:
            st.info("No skills detected.")

    with tab_gaps:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🔴 Missing Required")
            if analysis["missing_required"]:
                pills = " ".join(
                    [f'<span class="skill-pill missing">{s}</span>' for s in analysis["missing_required"]]
                )
                st.markdown(pills, unsafe_allow_html=True)
            else:
                st.success("None! Excellent coverage. 🎉")
        with c2:
            st.markdown("#### 🟡 Missing Recommended")
            if analysis["missing_recommended"]:
                pills = " ".join(
                    [f'<span class="skill-pill missing">{s}</span>' for s in analysis["missing_recommended"]]
                )
                st.markdown(pills, unsafe_allow_html=True)
            else:
                st.success("None! Great fit. 🌟")

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
        st.markdown("### 🤖 Neural Career Coach")
        st.caption("Powered by Stitch Memory & GPT-Neo")
        
        if not AIAssistant:
            st.warning("⚠️ AI Assistant dependencies not found.")
        else:
            if "ai_agent" not in st.session_state:
                st.session_state["ai_agent"] = AIAssistant()
                
            for msg in st.session_state["chat_history"]:
                role = "user" if msg["role"] == "user" else "assistant"
                with st.chat_message(role):
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

    # --- Explainability ---
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
                p_df = p_df.sort_values("Impact", ascending=False)
                st.bar_chart(p_df.set_index("Keyword"), color="#6C63FF")

    # --- History Tab ---
    user = st.session_state.get("user")
    if user and not st.session_state.get("is_anonymous"):
        with st.expander("📜 Your Analysis History"):
            db = DatabaseManager()
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
