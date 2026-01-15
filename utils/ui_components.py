"""
UI Components Module
====================
Reusable Streamlit UI components for error handling and user feedback.

Implements user-facing error displays as specified in OUTPUT_SPECIFICATION.md section 6.5.
"""

import streamlit as st
from utils.errors import AppError, ErrorCode


# ==============================================================================
# Error Display Components
# ==============================================================================

def show_error(error: AppError):
    """
    Display user-friendly error message with suggestions.
    
    Args:
        error: AppError instance with error details
    """
    with st.container():
        st.error(f"❌ {error.user_message}")
        
        if error.suggestion:
            st.info(f"💡 **Suggestion:** {error.suggestion}")
        
        if error.recoverable:
            if st.button("🔄 Try Again", key=f"retry_{error.code.value}"):
                st.rerun()
        
        st.caption(f"Error Code: {error.code.value}")


def show_warning(message: str, suggestion: str = None):
    """
    Display warning message with optional suggestion.
    
    Args:
        message: Warning message to display
        suggestion: Optional suggestion text
    """
    st.warning(f"⚠️ {message}")
    if suggestion:
        st.info(f"💡 {suggestion}")


def show_degraded_mode(missing_feature: str):
    """
    Show banner when running in fallback mode.
    
    Args:
        missing_feature: Description of unavailable feature
    """
    st.warning(
        f"⚡ Running in limited mode. {missing_feature} is temporarily unavailable. "
        "Results may be less accurate."
    )
    if st.button("🔄 Refresh Full Analysis"):
        st.session_state.force_full_analysis = True
        st.rerun()


# ==============================================================================
# Success Display Components
# ==============================================================================

def show_success(message: str):
    """
    Display success message.
    
    Args:
        message: Success message to display
    """
    st.success(f"✅ {message}")


# ==============================================================================
# File Info Display
# ==============================================================================

def show_file_info(filename: str, file_size: int, file_type: str):
    """
    Display uploaded file information.
    
    Args:
        filename: Name of the file
        file_size: Size in bytes
        file_type: MIME type
    """
    file_details = {
        "Filename": filename,
        "File size": f"{file_size / 1024:.1f} KB",
        "File type": file_type
    }
    
    with st.expander("📄 File Details", expanded=False):
        for key, value in file_details.items():
            st.write(f"**{key}:** {value}")


# ==============================================================================
# Parse Result Display
# ==============================================================================

def show_parse_result(parse_result):
    """
    Display parsing results with metadata.
    
    Args:
        parse_result: ParseResult instance from parser
    """
    if parse_result.success:
        st.success(f"✅ Successfully parsed resume!")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Pages", parse_result.page_count)
        
        with col2:
            st.metric("Confidence", f"{parse_result.confidence * 100:.0f}%")
        
        with col3:
            st.metric("Text Length", f"{len(parse_result.text)} chars")
        
        # Show warnings for low confidence
        if parse_result.confidence < 0.7:
            show_warning(
                "Parsing confidence is below 70%. Some information may be missing.",
                "You'll have a chance to review and correct extracted data."
            )
        
        # Show text preview
        with st.expander("📝 Extracted Text Preview", expanded=False):
            preview_text = parse_result.text[:500]
            if len(parse_result.text) > 500:
                preview_text += "..."
            st.text(preview_text)
    
    else:
        if parse_result.error:
            show_error(parse_result.error)


# ==============================================================================
# Loading Spinners
# ==============================================================================

def show_processing(message: str = "Processing..."):
    """
    Display processing spinner.
    
    Args:
        message: Message to show during processing
    
    Returns:
        Context manager for spinner
    """
    return st.spinner(message)
