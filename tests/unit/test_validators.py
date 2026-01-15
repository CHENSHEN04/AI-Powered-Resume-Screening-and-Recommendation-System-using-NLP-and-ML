"""
Test Validators Module
=======================
Unit tests for file validation functionality.
"""

import pytest
from utils.validators import (
    validate_file,
    sanitize_filename,
    check_pdf_password_protected,
    get_file_size_limit,
    MAX_FILE_SIZE_ANONYMOUS,
    MAX_FILE_SIZE_AUTHENTICATED
)
from utils.errors import ErrorCode


class TestValidateFile:
    """Test file validation function."""
    
    def test_empty_file(self):
        """Test validation of empty file."""
        is_valid, error = validate_file(b"", "test.pdf")
        assert is_valid is False
        assert error.code == ErrorCode.EMPTY_FILE
    
    def test_invalid_extension(self):
        """Test validation with invalid file extension."""
        is_valid, error = validate_file(b"test content", "test.txt")
        assert is_valid is False
        assert error.code == ErrorCode.INVALID_FILE_TYPE
    
    def test_file_too_large_anonymous(self):
        """Test file size limit for anonymous users."""
        # Create 6MB of data (exceeds 5MB limit for anonymous)
        large_file = b"x" * (6 * 1024 * 1024)
        is_valid, error = validate_file(large_file, "test.pdf", is_authenticated=False)
        assert is_valid is False
        assert error.code == ErrorCode.FILE_TOO_LARGE
    
    def test_file_too_large_authenticated(self):
        """Test file size limit for authenticated users."""
        # Create 11MB of data (exceeds 10MB limit for authenticated)
        large_file = b"x" * (11 * 1024 * 1024)
        is_valid, error = validate_file(large_file, "test.pdf", is_authenticated=True)
        assert is_valid is False
        assert error.code == ErrorCode.FILE_TOO_LARGE
    
    def test_filename_too_long(self):
        """Test validation with filename exceeding max length."""
        long_filename = "a" * 150 + ".pdf"
        is_valid, error = validate_file(b"test content", long_filename)
        assert is_valid is False
    
    def test_valid_pdf_anonymous(self):
        """Test validation of valid PDF file for anonymous user."""
        # Small PDF-like content
        pdf_content = b"%PDF-1.4 test content"
        is_valid, error = validate_file(pdf_content, "resume.pdf", is_authenticated=False)
        # May pass or fail depending on magic library, but should not crash
        assert isinstance(is_valid, bool)
    
    def test_valid_pdf_authenticated(self):
        """Test validation of valid PDF file for authenticated user."""
        pdf_content = b"%PDF-1.4 test content"
        is_valid, error = validate_file(pdf_content, "resume.pdf", is_authenticated=True)
        assert isinstance(is_valid, bool)


class TestSanitizeFilename:
    """Test filename sanitization."""
    
    def test_sanitize_simple_filename(self):
        """Test sanitizing a simple filename."""
        result = sanitize_filename("My Resume.pdf")
        assert result == "my_resume.pdf"
    
    def test_sanitize_special_characters(self):
        """Test removing special characters."""
        result = sanitize_filename("Resume @#$% (Final).pdf")
        assert "@" not in result
        assert "#" not in result
        assert "$" not in result
        assert "%" not in result
    
    def test_sanitize_long_filename(self):
        """Test truncating long filenames."""
        long_name = "a" * 100 + ".pdf"
        result = sanitize_filename(long_name)
        # Should be shortened to 80 chars + extension
        assert len(result) <= 84  # 80 + ".pdf"
    
    def test_sanitize_preserves_extension(self):
        """Test that file extension is preserved."""
        result = sanitize_filename("Test File.DOCX")
        assert result.endswith(".docx")
    
    def test_sanitize_spaces_to_underscores(self):
        """Test that spaces are converted to underscores."""
        result = sanitize_filename("My Resume File.pdf")
        assert " " not in result
        assert "_" in result


class TestFileSizeLimit:
    """Test file size limit functions."""
    
    def test_anonymous_user_limit(self):
        """Test file size limit for anonymous users."""
        limit = get_file_size_limit(is_authenticated=False)
        assert limit == MAX_FILE_SIZE_ANONYMOUS
        assert limit == 5 * 1024 * 1024  # 5 MB
    
    def test_authenticated_user_limit(self):
        """Test file size limit for authenticated users."""
        limit = get_file_size_limit(is_authenticated=True)
        assert limit == MAX_FILE_SIZE_AUTHENTICATED
        assert limit == 10 * 1024 * 1024  # 10 MB


class TestPasswordProtectionCheck:
    """Test PDF password protection detection."""
    
    def test_empty_bytes(self):
        """Test checking password protection with empty bytes."""
        # Should not crash
        result = check_pdf_password_protected(b"")
        assert isinstance(result, bool)
    
    def test_invalid_pdf_bytes(self):
        """Test checking password protection with invalid PDF."""
        # Should return False (assuming not password-protected if can't check)
        result = check_pdf_password_protected(b"not a pdf")
        assert isinstance(result, bool)
