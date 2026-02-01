"""
AI-Powered Resume Screening and Recommendation System
======================================================
Main Streamlit application entry point (Dashboard View).
"""

import streamlit as st
import pandas as pd
import time
from datetime import datetime
from pathlib import Path
from utils.visualizer import Visualizer
from utils.validators import validate_file
from utils.ui_components import show_error
from utils.db_handler import DatabaseManager
from utils.rate_limiter import RateLimiter, show_rate_limit_info

# ==============================================================================
# Page Configuration
# ==============================================================================
st.set_page_config(
    page_title="AI Resume Screener",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==============================================================================
# Custom CSS
# ==============================================================================
st.markdown("""
<style>
    .main .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { color: #1E3A5F; }
    .stCard {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# Session State
# ==============================================================================
def init_session_state():
    if "user" not in st.session_state:
        st.session_state.update({
            "user": None,
            "uploaded_file_name": None,
            "analyzed": False,
            "parse_result": None,
            "skill_data": None,
            "prediction": None,
            "gap_analysis": None,
            "is_anonymous": False,
            "growth_data": None,
            "explanation": None
        })

init_session_state()

# ==============================================================================
# Main Dashboard
# ==============================================================================
def main():
    db = DatabaseManager()
    
    # --- Sidebar ---
    with st.sidebar:
        st.title("🚀 CV Screener")
        st.markdown("---")
        
        # --- Authentication Section ---
        user = st.session_state.get("user")
        is_anon = st.session_state.get("is_anonymous", False)

        if user and not is_anon:
            # Logged in User
            st.success(f"Logged in: {user.email}")
            if st.button("🚪 Log Out"):
                db.sign_out()
                st.session_state["user"] = None
                st.session_state["is_anonymous"] = False
                st.rerun()
        
        else:
            # Guest or Not Logged In
            auth_mode = "Sign Up" # Default for guest conversion
            
            if is_anon:
                st.info("☁️ Guest Mode")
                st.caption("Sign up to save your history!")
            else:
                st.markdown("### Get Started")
                if st.button("👻 Continue as Guest", use_container_width=True):
                    # Use Local Guest Mode (No Supabase Auth required)
                    # We create a dummy user object to satisfy structure requirements
                    class GuestUser:
                        def __init__(self):
                            self.id = "guest_session"
                            self.email = "guest@local"
                    
                    st.session_state["user"] = GuestUser()
                    st.session_state["is_anonymous"] = True
                    st.toast("Entered Guest Mode. Data will not be saved permanently.", icon="👻")
                    st.rerun()
                        
                st.markdown("---")
                auth_mode = st.radio("Account", ["Login", "Sign Up"], horizontal=True)

            with st.form("auth_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                full_name = st.text_input("Full Name") if auth_mode == "Sign Up" else ""
                
                if st.form_submit_button(auth_mode):
                    if auth_mode == "Login":
                        res, err = db.sign_in(email, password)
                        if err: st.error(err)
                        else:
                            st.session_state["user"] = res.user
                            st.session_state["is_anonymous"] = False
                            st.rerun()
                    else:
                        # Sign Up
                        res, err = db.sign_up(email, password, full_name)
                        if err: st.error(err)
                        else:
                            # If previously anonymous, merge data
                            if is_anon and user:
                                old_id = user.id
                                new_id = res.user.id if res.user else None
                                if new_id:
                                    db.merge_anonymous_data(old_id, new_id)
                            
                            st.success("Verification email sent! Please check inbox.")

        st.markdown("---")
        st.info("💡 **Mode:** Candidate Self-Review")
        
        if st.session_state.get("analyzed"):
            if st.button("🔄 New Analysis"):
                for key in ["analyzed", "parse_result", "skill_data", "prediction", "gap_analysis"]:
                    st.session_state[key] = None
                st.rerun()

    # --- Header ---
    st.title("AI Resume Analysis Dashboard")
    
    # --- Tabs ---
    if st.session_state["user"]:
        main_tabs = st.tabs(["🚀 Analysis", "📜 History"])
    else:
        main_tabs = [st.container()] # Just a container if not logged in
        st.warning("🔒 Log in to save analysis and view history")

    # --- ANALYSIS TAB ---
    with main_tabs[0]:
        if not st.session_state.get("analyzed"):
            st.markdown("### 1. Upload Resume")
            
            # Show rate limit quota
            if st.session_state.get("is_anonymous"):
                user_id = st.session_state["user"].id
                is_authenticated = False
            elif st.session_state.get("user"):
                user_id = st.session_state["user"].email
                is_authenticated = True
            else:
                user_id = "anonymous"
                is_authenticated = False
                
            show_rate_limit_info(user_id, is_authenticated)
            
            uploaded_file = st.file_uploader(
                "Upload your PDF or DOCX file", 
                type=["pdf", "docx"]
            )

            if uploaded_file:
                # Check rate limit BEFORE processing
                # Check rate limit BEFORE processing
                limiter = RateLimiter()
                
                if st.session_state.get("is_anonymous"):
                    user_id = st.session_state["user"].id
                    is_authenticated = False
                elif st.session_state.get("user"):
                    user_id = st.session_state["user"].email
                    is_authenticated = True
                else:
                    user_id = "anonymous"
                    is_authenticated = False
                
                is_allowed, error_msg = limiter.check_rate_limit(user_id, is_authenticated)
                
                if not is_allowed:
                    st.error(error_msg)
                    st.info("💡 **Tip**: Create an account to get higher upload limits!")
                else:
                    file_bytes = uploaded_file.getvalue()
                    
                    # Check file size
                    max_size = limiter.get_file_size_limit(is_authenticated)
                    if len(file_bytes) > max_size:
                        st.error(f"📁 File too large. Maximum size: {max_size // (1024*1024)} MB")
                    else:
                        is_valid, error = validate_file(file_bytes, uploaded_file.name)
                        
                        if not is_valid:
                            show_error(error)
                        else:
                            st.success(f"✅ Ready: {uploaded_file.name}")
                            if st.button("🚀 Analyze Now", type="primary"):
                                with st.spinner("Analyzing..."):
                                    # 1. Parse
                                    from utils.parser import ResumeParser
                                    parser = ResumeParser()
                                    uploaded_file.seek(0)
                                    parse_result = parser.parse(uploaded_file.read(), uploaded_file.name)
                                    
                                    if parse_result.success:
                                        st.session_state["parse_result"] = parse_result
                                        
                                        # 2. Extract
                                        from utils.skill_extractor import SkillExtractor
                                        extractor = SkillExtractor()
                                        skill_data = extractor.extract_skills(parse_result.text)
                                        st.session_state["skill_data"] = skill_data
                                        
                                        # 3. Classify
                                        from utils.classifier import JobClassifier
                                        classifier = JobClassifier()
                                        prediction = classifier.predict(parse_result.text)
                                        st.session_state["prediction"] = prediction
                                        st.session_state["explanation"] = classifier.explain_prediction(parse_result.text)
                                        
                                        # 4. Gap Analysis
                                        from utils.gap_analyzer import GapAnalyzer
                                        analyzer = GapAnalyzer(db)
                                        role_cats = extractor.map_to_category(skill_data["all_skills"])
                                        top_skill_cat = list(role_cats.keys())[0] if role_cats else "Unknown"
                                        
                                        # Smart Fallback: Use skill-based role if model returns "Unknown" or numeric garbage (e.g. "6")
                                        target_role = prediction["top_category"]
                                        if target_role == "Unknown" or str(target_role).isdigit():
                                            target_role = top_skill_cat
                                        
                                        st.session_state["target_role"] = target_role # Store for global access

                                        # Use skill_data["all_skills"] which exists
                                        analysis = analyzer.analyze_gaps(skill_data["all_skills"], target_role)
                                        st.session_state["gap_analysis"] = analysis
                                        st.session_state["analyzed"] = True

                                        # 5. Calculate Growth Logic
                                        from utils.growth_tracker import GrowthTracker
                                        previous_version = None
                                        if st.session_state.get("user"):
                                            previous_version = db.get_previous_version(st.session_state["user"].id, uploaded_file.name)
                                        
                                        growth = GrowthTracker.calculate_growth(analysis, skill_data["all_skills"], previous_version)
                                        st.session_state["growth_data"] = growth

                                        # 6. Save to DB if logged in
                                        if st.session_state["user"]:
                                            db.save_resume_analysis(
                                                st.session_state["user"].id,
                                                {
                                                    "filename": uploaded_file.name,
                                                    "storage_path": f"resumes/{st.session_state['user'].id}/{uploaded_file.name}",
                                                    "parsed_text": parse_result.text,
                                                    "page_count": parse_result.page_count,
                                                    "confidence_score": parse_result.confidence,
                                                    "predicted_role": target_role,
                                                    "match_score": analysis["match_percentage"],
                                                    "skills": [{"name": s, "category": "extracted"} for s in skill_data["all_skills"]]
                                                }
                                            )
                                        st.rerun()

        else:
            # Show Dashboard (Similar to before)
            analysis = st.session_state["gap_analysis"]
            skill_data = st.session_state["skill_data"]
            target_role = st.session_state.get("target_role", "Unknown") # Retrieve from session
            
            # Row 0: Growth Metrics
            if st.session_state.get("growth_data"):
                from utils.growth_tracker import GrowthTracker
                GrowthTracker.render_growth_metrics(st.session_state["growth_data"])
                st.markdown("---")

            # Row 1: Metrics
            st.markdown("### 📊 Executive Summary")
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.metric("Target Role", target_role.replace("_", " ").title())
            with m2: st.metric("Match Score", f"{analysis['match_percentage']:.0f}%")
            with m3: st.metric("Technical Skills", skill_data["count"])
            with m4: st.metric("Critical Gaps", len(analysis["missing_required"]))
            
            # Guest CTA
            if st.session_state.get("is_anonymous") or not st.session_state.get("user"):
                 st.info("💡 **Want to save this report?** Sign up or Log in via the sidebar to save your progress and track growth over time!")
            
            st.markdown("---")
            
            # Export Section
            from utils.pdf_generator import PDFGenerator
            pdf_gen = PDFGenerator()
            
            # Prepare data for PDF
            pdf_data = {
                "role": target_role,
                "match_percentage": analysis["match_percentage"],
                "missing_required": analysis["missing_required"],
                "missing_recommended": analysis["missing_recommended"],
                "learning_paths": analysis["learning_paths"],
                "recommendations": analysis["recommendations"]
            }
            
            user_name = st.session_state["user"].email if st.session_state["user"] else "Guest"
            pdf_buffer = pdf_gen.generate_report(pdf_data, user_name)
            
            st.download_button(
                label="📄 Download Career Roadmap (PDF)",
                data=pdf_buffer,
                file_name=f"Career_Roadmap_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                type="primary"
            )

            st.markdown("---")
            
            # Explainability Section
            if st.session_state.get("explanation"):
                with st.expander("❓ Why this role?"):
                    expl = st.session_state["explanation"]
                    if expl["positive"]:
                        st.caption("Top matching keywords found in your resume:")
                        # Simple bar chart using pandas
                        p_df = pd.DataFrame(expl["positive"], columns=["Keyword", "Impact"])
                        st.bar_chart(p_df.set_index("Keyword"), color="#2E86C1")
                    elif expl["negative"]:
                        st.caption("These keywords negatively impacted the match:")
                        n_df = pd.DataFrame(expl["negative"], columns=["Keyword", "Impact"])
                        st.bar_chart(n_df.set_index("Keyword"), color="#E74C3C")
                    else:
                        st.info("No specific keywords dominated the decision (likely based on general semantic context).")

            # Row 2: Charts
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Skill Fit Radar")
                st.plotly_chart(Visualizer.plot_radar_chart([], analysis), use_container_width=True)
            with c2:
                st.subheader("Gap Breakdown")
                st.plotly_chart(Visualizer.plot_skill_gap_chart(analysis), use_container_width=True)

            # Row 3: Tabs
            st.markdown("---")
            t1, t2, t3 = st.tabs(["✅ Skills", "❌ Gaps", "🎓 Plan"])
            with t1: 
                if skill_data["all_skills"]:
                    for skill in skill_data["all_skills"]:
                        st.markdown(f"- {skill}")
                else:
                    st.info("No technical skills detected")
            with t2:
                st.markdown("**Missing Required:**")
                if analysis["missing_required"]:
                    for skill in analysis["missing_required"]:
                        st.markdown(f"- {skill}")
                else:
                    st.success("✅ You have all required skills!")
                    
                st.markdown("**Missing Recommended:**")
                if analysis["missing_recommended"]:
                    for skill in analysis["missing_recommended"]:
                        st.markdown(f"- {skill}")
                else:
                    st.success("✅ You have all recommended skills!")
            with t3:
                for skill, res in analysis["learning_paths"].items():
                    with st.expander(f"📚 {skill}"):
                        for r in res: st.markdown(f"- [{r['title']}]({r['url']})")

    # --- HISTORY TAB ---
    if st.session_state["user"]:
        with main_tabs[1]:
            st.markdown("### 📜 Your Analysis History")
            
            if st.session_state.get("is_anonymous"):
                st.warning("⚠️ You are in Guest Mode. History will be cleared when you close the session. Sign up to save permanently!")
                
            history = db.get_user_history(st.session_state["user"].id)
            if history:
                df = pd.DataFrame(history)
                st.dataframe(df[["created_at", "filename", "predicted_role", "match_score"]])
                
                selected_id = st.selectbox("View details for:", [h["id"] for h in history])
                if selected_id:
                    selected = next(h for h in history if h["id"] == selected_id)
                    st.json(selected)
            else:
                st.info("No history found. Try analyzing a resume!")

if __name__ == "__main__":
    main()
