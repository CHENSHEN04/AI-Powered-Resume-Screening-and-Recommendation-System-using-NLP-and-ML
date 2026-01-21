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
    if "user_id" not in st.session_state:
        st.session_state.update({
            "user_id": None,
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
    # --- Sidebar ---
    with st.sidebar:
        st.title("🚀 CV Screener")
        st.markdown("---")
        st.info("💡 **Mode:** Candidate Self-Review")
        st.write("Upload your resume to compare your skills against industry standards.")
        
        if st.session_state.get("analyzed"):
            st.markdown("---")
            st.success("Analysis Complete ✅")
            if st.button("🔄 Reset Analysis"):
                for key in ["analyzed", "parse_result", "skill_data", "prediction", "gap_analysis"]:
                    st.session_state[key] = None
                st.rerun()

    # --- Header ---
    st.title("AI Resume Analysis Dashboard")
    st.markdown("Optimize your profile for the modern job market with AI-driven insights.")

    # --- File Upload Section (Only if not analyzed) ---
    if not st.session_state.get("analyzed"):
        with st.container():
            st.markdown("### 1. Upload Resume")
            uploaded_file = st.file_uploader(
                "Drag and drop your PDF or DOCX file here", 
                type=["pdf", "docx"],
                help="Max size: 5MB"
            )

            if uploaded_file:
                # Validate File
                file_bytes = uploaded_file.getvalue()
                is_valid, error = validate_file(file_bytes, uploaded_file.name)
                
                if not is_valid:
                    show_error(error)
                else:
                    st.success(f"✅ Ready: {uploaded_file.name}")
                    
                    if st.button("� Analyze Now", type="primary", use_container_width=True):
                        with st.spinner("🔍 Reading file, extracting entities, and running classifiers..."):
                            # 1. Parse
                            from utils.parser import ResumeParser
                            parser = ResumeParser()
                            # Reset pointer
                            uploaded_file.seek(0)
                            file_bytes = uploaded_file.read()
                            
                            parse_result = parser.parse(file_bytes, uploaded_file.name)
                            
                            if parse_result.success:
                                st.session_state["parse_result"] = parse_result
                                
                                # 2. Extract
                                from utils.skill_extractor import SkillExtractor
                                extractor = SkillExtractor()
                                skill_data = extractor.extract_skills(parse_result.text)
                                st.session_state["skill_data"] = skill_data
                                st.session_state["skill_categories"] = extractor.map_to_category(skill_data["all_skills"])
                                
                                # 3. Classify
                                from utils.classifier import JobClassifier
                                classifier = JobClassifier()
                                prediction = classifier.predict(parse_result.text)
                                st.session_state["prediction"] = prediction
                                
                                # 4. Gap Analysis
                                from utils.gap_analyzer import GapAnalyzer
                                gap_analyzer = GapAnalyzer()
                                
                                # Determine role
                                top_skill_cat = list(st.session_state["skill_categories"].keys())[0] if st.session_state["skill_categories"] else "Unknown"
                                target_role = prediction["top_category"] if prediction["top_category"] != "Unknown" else top_skill_cat
                                
                                analysis = gap_analyzer.analyze_gaps(skill_data["all_skills"], target_role)
                                st.session_state["gap_analysis"] = analysis
                                st.session_state["analyzed"] = True
                                st.rerun()
                            else:
                                st.error(f"Parsing failed: {parse_result.error.user_message}")

    # --- Dashboard View (If analyzed) ---
    else:
        analysis = st.session_state["gap_analysis"]
        pred = st.session_state["prediction"]
        skill_data = st.session_state["skill_data"]
        
        # Row 1: Key Metrics
        st.markdown("### 📊 Executive Summary")
        m1, m2, m3, m4 = st.columns(4)
        
        with m1:
            role_title = analysis.get("role", "Unknown").replace("_", " ").title()
            st.metric("Target Role", role_title, help="Detected based on your skills and content")
        with m2:
            score = analysis.get("match_percentage", 0)
            st.metric("Match Score", f"{score:.0f}%", delta=f"{score-100:.0f}%" if score < 100 else "Perfect")
        with m3:
            st.metric("Technical Skills", skill_data["count"])
        with m4:
            gaps = len(analysis.get("missing_required", []))
            st.metric("Critical Gaps", gaps, delta=-gaps, delta_color="inverse")

        st.markdown("---")

        # Row 2: Charts
        c1, c2 = st.columns([1, 1])
        
        with c1:
            st.subheader("Skill Fit Radar")
            fig_radar = Visualizer.plot_radar_chart([], analysis)
            st.plotly_chart(fig_radar, use_container_width=True)
            
        with c2:
            st.subheader("Gap Breakdown")
            fig_bar = Visualizer.plot_skill_gap_chart(analysis)
            st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")

        # Row 3: Details Tabs
        t1, t2, t3 = st.tabs(["✅ Extracted Skills", "❌ Gaps Analysis", "🎓 Learning Plan"])
        
        with t1:
            st.markdown(f"**Found {skill_data['count']} skills:**")
            st.markdown(" ".join([f"`{s}`" for s in skill_data["all_skills"]]))
            with st.expander("Show extracted text"):
                st.text(st.session_state["parse_result"].text[:2000])
        
        with t2:
            col_req, col_rec = st.columns(2)
            with col_req:
                st.error("Missing Required Skills")
                if analysis["missing_required"]:
                    for s in analysis["missing_required"]:
                        st.markdown(f"- **{s}**")
                else:
                    st.success("None! You hit all the requirements.")
            
            with col_rec:
                st.warning("Missing Recommended Skills")
                if analysis["missing_recommended"]:
                    for s in analysis["missing_recommended"]:
                        st.markdown(f"- {s}")
                else:
                    st.success("Great job! No major gaps here.")

        with t3:
            st.info("💡 **AI Recommendation:** " + " ".join(analysis["recommendations"]))
            
            if analysis["learning_paths"]:
                st.write("#### Recommended Resources")
                for skill, resources in analysis["learning_paths"].items():
                    with st.expander(f"📚 Learn {skill}"):
                        for res in resources:
                            st.markdown(f"- [{res['title']}]({res['url']}) *({res['type']})*")
            else:
                st.write("No specific resources found for your missing skills.")

if __name__ == "__main__":
    main()
