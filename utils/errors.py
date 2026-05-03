"""
Error Handling Module
=====================
Centralized error codes and error handling for the AI Resume Screening System.

This module defines all error codes, error messages, and error handling utilities
as specified in OUTPUT_SPECIFICATION.md section 6.5.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional


# ==============================================================================
# Error Code Enumeration
# ==============================================================================

class ErrorCode(Enum):
    """Error codes organized by category (E1xxx-E5xxx)."""
    
    # File Upload Errors (E1xxx)
    INVALID_FILE_TYPE = "E1001"
    FILE_TOO_LARGE = "E1002"
    FILE_CORRUPTED = "E1003"
    PASSWORD_PROTECTED = "E1004"
    EMPTY_FILE = "E1005"
    
    # Parsing Errors (E2xxx)
    PDF_EXTRACTION_FAILED = "E2001"
    DOCX_EXTRACTION_FAILED = "E2002"
    OCR_FAILED = "E2003"
    NER_EXTRACTION_FAILED = "E2004"
    NO_TEXT_EXTRACTED = "E2005"
    LOW_CONFIDENCE_PARSE = "E2006"
    
    # Analysis Errors (E3xxx)
    BERT_MODEL_ERROR = "E3001"
    SVM_MODEL_ERROR = "E3002"
    SKILL_MATCHING_ERROR = "E3003"
    TIMEOUT_ERROR = "E3004"
    INSUFFICIENT_DATA = "E3005"
    PROCESSING_ERROR = "E3006"
    
    # Database Errors (E4xxx)
    DB_CONNECTION_FAILED = "E4001"
    DB_QUERY_FAILED = "E4002"
    STORAGE_UPLOAD_FAILED = "E4003"
    STORAGE_DOWNLOAD_FAILED = "E4004"
    
    # Auth Errors (E5xxx)
    SESSION_EXPIRED = "E5001"
    INVALID_TOKEN = "E5002"
    OAUTH_FAILED = "E5003"
    EMAIL_NOT_VERIFIED = "E5004"


# ==============================================================================
# Error Data Class
# ==============================================================================

@dataclass
class AppError:
    """Application error with user-friendly messaging."""
    code: ErrorCode
    message: str
    user_message: str
    suggestion: Optional[str] = None
    recoverable: bool = True


# ==============================================================================
# Error Message Mappings
# ==============================================================================

ERROR_MESSAGES = {
    ErrorCode.INVALID_FILE_TYPE: AppError(
        code=ErrorCode.INVALID_FILE_TYPE,
        message="File MIME type not in allowed list",
        user_message="Please upload a PDF or DOCX file only.",
        suggestion="Convert your file to PDF and try again.",
        recoverable=True
    ),
    ErrorCode.FILE_TOO_LARGE: AppError(
        code=ErrorCode.FILE_TOO_LARGE,
        message="File exceeds size limit",
        user_message="Your file is too large. Maximum size is 10MB.",
        suggestion="Compress images in your resume or reduce page count.",
        recoverable=True
    ),
    ErrorCode.FILE_CORRUPTED: AppError(
        code=ErrorCode.FILE_CORRUPTED,
        message="File appears to be corrupted",
        user_message="This file appears to be corrupted.",
        suggestion="Try re-exporting your resume and upload again.",
        recoverable=True
    ),
    ErrorCode.PASSWORD_PROTECTED: AppError(
        code=ErrorCode.PASSWORD_PROTECTED,
        message="PDF is password-protected",
        user_message="This PDF is password-protected. We cannot read it.",
        suggestion="Remove password protection and re-upload.",
        recoverable=True
    ),
    ErrorCode.EMPTY_FILE: AppError(
        code=ErrorCode.EMPTY_FILE,
        message="File has zero bytes",
        user_message="The uploaded file is empty.",
        suggestion="Please upload a valid resume file.",
        recoverable=True
    ),
    ErrorCode.PDF_EXTRACTION_FAILED: AppError(
        code=ErrorCode.PDF_EXTRACTION_FAILED,
        message="PDF extraction failed",
        user_message="We couldn't read this PDF file.",
        suggestion="Try converting to a different format or re-exporting the PDF.",
        recoverable=True
    ),
    ErrorCode.DOCX_EXTRACTION_FAILED: AppError(
        code=ErrorCode.DOCX_EXTRACTION_FAILED,
        message="DOCX extraction failed",
        user_message="We couldn't read this DOCX file.",
        suggestion="Try saving as PDF or re-saving the document.",
        recoverable=True
    ),
    ErrorCode.NO_TEXT_EXTRACTED: AppError(
        code=ErrorCode.NO_TEXT_EXTRACTED,
        message="No text content found in document",
        user_message="We couldn't extract any text from your file.",
        suggestion="This may be a scanned image. Try uploading a text-based PDF.",
        recoverable=True
    ),
    ErrorCode.BERT_MODEL_ERROR: AppError(
        code=ErrorCode.BERT_MODEL_ERROR,
        message="BERT inference failed",
        user_message="Advanced analysis temporarily unavailable.",
        suggestion="Click 'Retry Analysis' or use basic results.",
        recoverable=True
    ),
    ErrorCode.SESSION_EXPIRED: AppError(
        code=ErrorCode.SESSION_EXPIRED,
        message="User session has expired",
        user_message="Your session has expired. Please log in again.",
        suggestion=None,
        recoverable=True
    ),
}


# ==============================================================================
# Helper Functions
# ==============================================================================

def get_error(code: ErrorCode) -> AppError:
    """Get error details for a given error code."""
    return ERROR_MESSAGES.get(code, AppError(
        code=code,
        message="Unknown error occurred",
        user_message="An unexpected error occurred.",
        suggestion="Please try again or contact support.",
        recoverable=True
    ))


def log_error(error: AppError, context: dict = None):
    """
    Log error for monitoring and debugging.
    
    In production, this would write to system_logs table.
    For now, we'll just print to console.
    """
    import logging
    
    logger = logging.getLogger(__name__)
    logger.error(
        f"[{error.code.value}] {error.message}",
        extra={'context': context}
    )
