"""
File Validation Module
=======================
Validates uploaded files for type, size, and integrity.

Implements security checks and file validation as specified in
OUTPUT_SPECIFICATION.md sections 5.5 and 6.1.3.
"""

import magic
from pathlib import Path
from typing import Tuple
from utils.errors import ErrorCode, AppError, get_error


# ==============================================================================
# Constants
# ==============================================================================

ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILENAME_LENGTH = 100

# File size limits (in bytes)
MAX_FILE_SIZE_ANONYMOUS = 5 * 1024 * 1024  # 5 MB
MAX_FILE_SIZE_AUTHENTICATED = 10 * 1024 * 1024  # 10 MB


# ==============================================================================
# Validation Functions
# ==============================================================================

def validate_file(
    file_bytes: bytes,
    filename: str,
    is_authenticated: bool = False
) -> Tuple[bool, AppError | None]:
    """
    Validate uploaded file for security and format.
    
    Args:
        file_bytes: File content as bytes
        filename: Original filename
        is_authenticated: Whether user is authenticated (affects size limit)
    
    Returns:
        Tuple of (is_valid, error)
        - If valid: (True, None)
        - If invalid: (False, AppError)
    """
    # Check if file is empty
    if len(file_bytes) == 0:
        return False, get_error(ErrorCode.EMPTY_FILE)
    
    # Check file extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, get_error(ErrorCode.INVALID_FILE_TYPE)
    
    # Check file size
    max_size = (MAX_FILE_SIZE_AUTHENTICATED if is_authenticated 
                else MAX_FILE_SIZE_ANONYMOUS)
    if len(file_bytes) > max_size:
        error = get_error(ErrorCode.FILE_TOO_LARGE)
        max_mb = max_size / 1024 / 1024
        error.user_message = f"Your file is too large. Maximum size is {max_mb:.0f}MB."
        return False, error
    
    # Verify MIME type matches extension
    try:
        detected_mime = magic.from_buffer(file_bytes[:2048], mime=True)
        if detected_mime not in ALLOWED_MIME_TYPES:
            return False, get_error(ErrorCode.INVALID_FILE_TYPE)
    except Exception as e:
        # If magic fails, we'll allow it and let the parser handle it
        pass
    
    # Check filename length
    if len(filename) > MAX_FILENAME_LENGTH:
        return False, AppError(
            code=ErrorCode.INVALID_FILE_TYPE,
            message=f"Filename too long (>{MAX_FILENAME_LENGTH} chars)",
            user_message=f"Filename too long. Maximum {MAX_FILENAME_LENGTH} characters.",
            suggestion="Rename your file to a shorter name.",
            recoverable=True
        )
    
    return True, None


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename for safe storage.
    
    Rules:
    - Lowercase
    - Replace spaces with underscores
    - Remove special characters
    - Limit to 80 characters (+ extension)
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    import re
    
    # Remove special characters, keep only alphanumeric, dots, dashes, underscores
    safe = re.sub(r'[^\w\-\.]', '_', filename)
    safe = safe.lower()
    
    # Split into name and extension
    path = Path(safe)
    name = path.stem
    ext = path.suffix
    
    # Truncate name if too long
    if len(name) > 80:
        name = name[:80]
    
    return f"{name}{ext}"


def check_pdf_password_protected(file_bytes: bytes) -> bool:
    """
    Check if a PDF is password-protected.
    
    Args:
        file_bytes: PDF file content as bytes
    
    Returns:
        True if password-protected, False otherwise
    """
    try:
        import PyPDF2
        from io import BytesIO
        
        pdf_file = BytesIO(file_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        # If PDF is encrypted, it will have is_encrypted attribute
        return pdf_reader.is_encrypted
    except Exception:
        # If we can't check, assume it's not password-protected
        # The parser will catch actual issues
        return False


def get_file_size_limit(is_authenticated: bool) -> int:
    """
    Get maximum file size in bytes for a user.
    
    Args:
        is_authenticated: Whether user is authenticated
    
    Returns:
        Maximum file size in bytes
    """
    return (MAX_FILE_SIZE_AUTHENTICATED if is_authenticated 
            else MAX_FILE_SIZE_ANONYMOUS)
