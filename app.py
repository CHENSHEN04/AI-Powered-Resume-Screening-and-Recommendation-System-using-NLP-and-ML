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
                # Placeholder - actual implementation in Milestone 2
                st.warning("⚠️ Full analysis coming in Milestone 2!")


if __name__ == "__main__":
    main()
