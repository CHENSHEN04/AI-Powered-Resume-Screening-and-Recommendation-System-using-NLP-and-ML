"""
AI-Powered Resume Screening and Recommendation System
======================================================
Main Streamlit application entry point.

This system helps students and fresh graduates:
- Upload and parse resumes (PDF/DOCX)
- Extract skills using NLP
- Compare against market standards
- Get actionable career recommendations
"""

import streamlit as st

# ==============================================================================
# Page Configuration (must be first Streamlit command)
# ==============================================================================
st.set_page_config(
    page_title="AI Resume Screener",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "AI-Powered Resume Screening System - Helping students build better resumes"
    }
)

# ==============================================================================
# Custom CSS Styling
# ==============================================================================
st.markdown("""
<style>
    /* Main container padding */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }
    
    /* Header styling */
    h1 {
        color: #1E3A5F;
    }
    
    /* Card-like containers */
    .stCard {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    /* Success message styling */
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        color: #155724;
    }
    
    /* Warning message styling */
    .warning-box {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        border-radius: 5px;
        padding: 1rem;
        color: #856404;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)


# ==============================================================================
# Session State Initialization
# ==============================================================================
def init_session_state():
    """Initialize session state variables."""
    defaults = {
        "user_id": None,
        "is_anonymous": True,
        "uploaded_file": None,
        "parsed_data": None,
        "analysis_results": None,
        "current_step": "upload",  # upload -> review -> dashboard
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# ==============================================================================
# Main Application
# ==============================================================================
def main():
    """Main application entry point."""
    
    # Sidebar navigation
    with st.sidebar:
        st.image("https://via.placeholder.com/150x50?text=Logo", width=150)
        st.title("Navigation")
        
        st.markdown("---")
        
        # Show current status
        if st.session_state.parsed_data:
            st.success("✅ Resume Uploaded")
        else:
            st.info("📤 Upload a resume to begin")
        
        st.markdown("---")
        st.caption("AI Resume Screener v1.0")
    
    # Main content area
    st.title("🎯 AI-Powered Resume Screening")
    st.markdown(
        "Analyze your resume, discover skill gaps, and get personalized "
        "recommendations for your target career."
    )
    
    # Hero section with key features
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="stCard">
            <h3>📄 Smart Parsing</h3>
            <p>Upload PDF or DOCX resumes. Our AI extracts skills, education, and experience.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="stCard">
            <h3>📊 Gap Analysis</h3>
            <p>Compare your skills against market standards for your target role.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="stCard">
            <h3>🎓 Career Coaching</h3>
            <p>Get actionable recommendations and curated learning resources.</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Call to action
    st.subheader("🚀 Get Started")
    st.markdown("Upload your resume to receive instant analysis and personalized feedback.")
    
    # File uploader (basic implementation for Milestone 1)
    uploaded_file = st.file_uploader(
        "Upload your resume",
        type=["pdf", "docx"],
        help="Supported formats: PDF, DOCX (Max 10MB)"
    )
    
    if uploaded_file:
        st.session_state.uploaded_file = uploaded_file
        
        # Display file info
        file_details = {
            "Filename": uploaded_file.name,
            "File size": f"{uploaded_file.size / 1024:.1f} KB",
            "File type": uploaded_file.type
        }
        
        st.success("✅ File uploaded successfully!")
        st.json(file_details)
        
        # Placeholder for next steps (will be implemented in later milestones)
        st.info(
            "📝 **Next Steps** (Coming in Milestone 2):\n"
            "- Parse resume content\n"
            "- Extract skills and education\n"
            "- Analyze against market standards"
        )
        

        if st.button("🔍 Analyze Resume", type="primary"):
            with st.spinner("Analyzing your resume..."):
                # 1. Parse Resume
                from utils.parser import ResumeParser
                parser = ResumeParser()
                # Reset pointer to start
                uploaded_file.seek(0)
                file_bytes = uploaded_file.read()
                
                parse_result = parser.parse(file_bytes, uploaded_file.name)
                
                if parse_result.success:
                    # Show parse success
                    st.success(f"✅ Parsed {parse_result.page_count} pages with {parse_result.confidence*100:.0f}% confidence")
                    
                    # 2. Extract Skills
                    from utils.skill_extractor import SkillExtractor
                    extractor = SkillExtractor()
                    
                    with st.expander("📝 Extracted Text Preview", expanded=False):
                        st.text(parse_result.text[:500] + "...")
                        
                    skill_data = extractor.extract_skills(parse_result.text)
                    
                    # 3. Classify Job Role (Milestone 4)
                    from utils.classifier import JobClassifier
                    classifier = JobClassifier()
                    prediction = classifier.predict(parse_result.text)
                    
                    st.divider()
                    st.subheader("🤖 AI Classification")
                    
                    if prediction["top_category"] != "Unknown":
                        c1, c2 = st.columns([1, 2])
                        with c1:
                            st.metric(
                                "Predicted Role", 
                                prediction["top_category"],
                                f"{prediction['confidence']*100:.1f}% Confidence"
                            )
                        with c2:
                            # Show all scores as a chart
                            if prediction["all_scores"]:
                                st.caption("Category Probability Distribution")
                                st.bar_chart(prediction["all_scores"])
                    else:
                        st.warning("⚠️ Could not classify job role. Models might be missing.")

                    # 4. Skills Display (Updated)
                    st.divider()
                    st.subheader("🧠 Skills Analysis")
                    
                    if skill_data["all_skills"]:
                        # Group categories based on skill match
                        categories = extractor.map_to_category(skill_data["all_skills"])
                        top_skill_cat = list(categories.keys())[0] if categories else "Unknown"
                        
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.write(f"**Found {skill_data['count']} technical skills:**")
                            st.markdown(
                                " ".join([f"`{s}`" for s in skill_data["all_skills"]]),
                                unsafe_allow_html=True
                            )
                        
                        with col2:
                            st.metric("Skill-based Match", top_skill_cat.replace("_", " ").title(), 
                                     f"{categories.get(top_skill_cat, 0)*100:.0f}% Match")
                            
                        with st.expander("📊 Classification Details"):
                            st.write("**Model Prediction:** Uses text content (TF-IDF + SVM)")
                            st.write("**Skill Match:** Uses specific extracted keywords")
                            if prediction["top_category"] != "Unknown":
                                st.write(f"Model and Skill Analysis agree: **{'Yes' if prediction['top_category'].lower().replace(' ', '_') == top_skill_cat else 'No'}**")
                                
                        # 5. Gap Analysis (Milestone 5)
                        st.divider()
                        st.subheader("📈 Career Gap Analysis")
                        
                        # Determine target role (prefer prediction, fallback to skill match)
                        target_role = prediction["top_category"] if prediction["top_category"] != "Unknown" else top_skill_cat
                        
                        from utils.gap_analyzer import GapAnalyzer
                        gap_analyzer = GapAnalyzer()
                        analysis = gap_analyzer.analyze_gaps(skill_data["all_skills"], target_role)
                        
                        if "error" not in analysis:
                            # Match Score
                            st.progress(analysis["match_percentage"] / 100, 
                                      text=f"Match Score for {analysis['role']}")
                            
                            # Missing Skills
                            c1, c2 = st.columns(2)
                            with c1:
                                if analysis["missing_required"]:
                                    st.error(f"❌ Missing Required Skills: {', '.join(analysis['missing_required'])}")
                                else:
                                    st.success("✅ All required skills matched!")
                                    
                            with c2:
                                if analysis["missing_recommended"]:
                                    st.warning(f"⚠️ Consider Learning: {', '.join(analysis['missing_recommended'])}")
                            
                            # Recommendations
                            st.info("💡 **Recommendation:** " + " ".join(analysis["recommendations"]))
                            
                            # Learning Resources
                            if analysis["learning_paths"]:
                                with st.expander("📚 Recommended Learning Resources"):
                                    for skill, resources in analysis["learning_paths"].items():
                                        st.markdown(f"**{skill}**")
                                        for res in resources:
                                            st.markdown(f"- [{res['title']}]({res['url']}) ({res['type']})")
                        else:
                            st.warning(f"Could not perform gap analysis for role: {target_role}")
                            
                    else:
                        st.warning("No specific technical skills detected. Try a more detailed resume.")
                        
                else:
                    st.error(f"Failed to parse resume: {parse_result.error_code}")
                    if parse_result.error:
                        st.info(parse_result.error.user_message)



if __name__ == "__main__":
    main()
