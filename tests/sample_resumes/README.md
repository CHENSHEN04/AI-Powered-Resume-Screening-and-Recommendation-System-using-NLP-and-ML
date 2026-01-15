# Sample Resumes for Testing

This directory contains test resume files organized by category:

## Directory Structure

```
sample_resumes/
├── valid/             # Valid resumes for happy path testing
├── invalid/           # Invalid files for error handling tests
└── edge_cases/        # Edge case resumes for boundary testing
```

## Test Files Needed

### valid/
- `simple_one_page.pdf` - Basic single-page resume
- `complex_two_page.pdf` - Multi-section two-page resume
- `minimal_student.pdf` - Sparse content (<3 skills) to trigger Builder Mode
- `experienced_senior.pdf` - Full content for extraction testing
- `sample.docx` - DOCX format resume

### invalid/
- `password_protected.pdf` - For E1004 error testing
- `corrupted.pdf` - For E1003/E2001 error testing
- `image_only_scanned.pdf` - For OCR fallback testing
- `wrong_extension.txt` - For file type validation

### edge_cases/
- `unicode_characters.pdf` - Special character handling
- `ten_pages.pdf` - Page count warning
- `empty_sections.pdf` - Missing sections handling

## Creating Test Files

You can create these test files by:
1. Converting real resumes (anonymized) to PDF
2. Using online resume generators
3. Creating minimal test documents programmatically
