"""
AI-Powered Resume Screening and Recommendation System
======================================================
Main Streamlit application entry point (Dashboard View).
"""

import streamlit as st
import pandas as pd
import time
from pathlib import Path
from utils.visualizer import Visualizer
from utils.validators import validate_file
from utils.ui_components import show_error
from utils.database import DatabaseManager

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
            "gap_analysis": None
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
        if st.session_state["user"]:
            user = st.session_state["user"]
            st.success(f"Logged in: {user.email}")
            if st.button("🚪 Log Out"):
                db.sign_out()
                st.session_state["user"] = None
                st.rerun()
        else:
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
                            st.rerun()
                    else:
                        res, err = db.sign_up(email, password, full_name)
                        if err: st.error(err)
                        else:
                            st.success("Verification email sent!")

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
            uploaded_file = st.file_uploader(
                "Upload your PDF or DOCX file", 
                type=["pdf", "docx"]
            )

            if uploaded_file:
                file_bytes = uploaded_file.getvalue()
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
                                
                                # 4. Gap Analysis
                                from utils.gap_analyzer import GapAnalyzer
                                gap_analyzer = GapAnalyzer()
                                role_cats = extractor.map_to_category(skill_data["all_skills"])
                                top_skill_cat = list(role_cats.keys())[0] if role_cats else "Unknown"
                                target_role = prediction["top_category"] if prediction["top_category"] != "Unknown" else top_skill_cat
                                
                                analysis = gap_analyzer.analyze_gaps(skill_data["all_skills"], target_role)
                                st.session_state["gap_analysis"] = analysis
                                st.session_state["analyzed"] = True

                                # 5. Save to DB if logged in
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
            
            # Row 1: Metrics
            st.markdown("### 📊 Executive Summary")
            m1, m2, m3, m4 = st.columns(4)
            with m1: st.metric("Target Role", analysis.get("role", "Unknown").replace("_", " ").title())
            with m2: st.metric("Match Score", f"{analysis['match_percentage']:.0f}%")
            with m3: st.metric("Technical Skills", skill_data["count"])
            with m4: st.metric("Critical Gaps", len(analysis["missing_required"]))
            
            st.markdown("---")
            
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
            with t1: st.write(skill_data["all_skills"])
            with t2:
                st.write("**Missing Required:**", analysis["missing_required"])
                st.write("**Missing Recommended:**", analysis["missing_recommended"])
            with t3:
                for skill, res in analysis["learning_paths"].items():
                    with st.expander(f"📚 {skill}"):
                        for r in res: st.markdown(f"- [{r['title']}]({r['url']})")

    # --- HISTORY TAB ---
    if st.session_state["user"]:
        with main_tabs[1]:
            st.markdown("### 📜 Your Analysis History")
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
