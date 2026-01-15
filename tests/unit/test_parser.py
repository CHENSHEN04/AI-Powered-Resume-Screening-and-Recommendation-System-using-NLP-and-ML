"""
Test Parser Module
==================
Unit tests for resume parsing functionality.
"""

import pytest
from pathlib import Path
from utils.parser import ResumeParser, ParseResult
from utils.errors import ErrorCode


class TestResumeParser:
    """Test the ResumeParser class."""
    
    @pytest.fixture
    def parser(self):
        """Create a ResumeParser instance."""
        return ResumeParser()
    
    def test_parser_initialization(self, parser):
        """Test that parser initializes correctly."""
        assert parser is not None
        assert isinstance(parser, ResumeParser)
    
    def test_parse_result_dataclass(self):
        """Test ParseResult dataclass."""
        result = ParseResult(
            success=True,
            text="Test text",
            page_count=1,
            confidence=0.9
        )
        assert result.success is True
        assert result.text == "Test text"
        assert result.page_count == 1
        assert result.confidence == 0.9
        assert result.metadata == {}
    
    def test_calculate_confidence_short_text(self, parser):
        """Test confidence calculation with short text."""
        confidence = parser._calculate_confidence("Short text", 1)
        assert 0.0 <= confidence <= 1.0
        assert confidence < 0.8  # Short text should have lower confidence
    
    def test_calculate_confidence_long_text(self, parser):
        """Test confidence calculation with long text."""
        long_text = "education experience skills " * 50
        confidence = parser._calculate_confidence(long_text, 1)
        assert 0.0 <= confidence <= 1.0
        assert confidence > 0.5  # Longer text with keywords should have higher confidence
    
    def test_calculate_confidence_with_resume_keywords(self, parser):
        """Test that resume keywords boost confidence."""
        text_with_keywords = """
        John Doe
        Education: Bachelor of Science in Computer Science
        Experience: Software Engineer at Tech Company
        Skills: Python, JavaScript, SQL
        Projects: Built an e-commerce platform
        """
        confidence = parser._calculate_confidence(text_with_keywords, 1)
        assert confidence > 0.7  # Should have high confidence with many resume keywords
    
    def test_invalid_file_type(self, parser):
        """Test parsing with invalid file type."""
        result = parser.parse(b"test content", "test.txt")
        assert result.success is False
        assert result.error_code == ErrorCode.INVALID_FILE_TYPE.value


class TestPDFParsing:
    """Test PDF parsing functionality."""
    
    @pytest.fixture
    def parser(self):
        """Create a ResumeParser instance."""
        return ResumeParser()
    
    def test_empty_pdf_bytes(self, parser):
        """Test parsing with empty PDF bytes."""
        result = parser.parse_pdf(b"")
        assert result.success is False
        # Should fail with extraction error or no text extracted
    
    def test_corrupted_pdf_bytes(self, parser):
        """Test parsing with corrupted PDF bytes."""
        result = parser.parse_pdf(b"This is not a valid PDF")
        assert result.success is False
        assert result.error is not None


class TestDOCXParsing:
    """Test DOCX parsing functionality."""
    
    @pytest.fixture
    def parser(self):
        """Create a ResumeParser instance."""
        return ResumeParser()
    
    def test_empty_docx_bytes(self, parser):
        """Test parsing with empty DOCX bytes."""
        result = parser.parse_docx(b"")
        assert result.success is False
        # Should fail with extraction error
    
    def test_corrupted_docx_bytes(self, parser):
        """Test parsing with corrupted DOCX bytes."""
        result = parser.parse_docx(b"This is not a valid DOCX")
        assert result.success is False
        assert result.error is not None


# ==============================================================================
# Integration Tests (will need actual sample files)
# ==============================================================================

class TestParserIntegration:
    """Integration tests with actual sample files."""
    
    @pytest.fixture
    def parser(self):
        """Create a ResumeParser instance."""
        return ResumeParser()
    
    @pytest.fixture
    def sample_resumes_dir(self, project_root):
        """Get the sample resumes directory."""
        return project_root / "tests" / "sample_resumes"
    
    def test_sample_pdf_exists(self, sample_resumes_dir):
        """Verify sample resumes directory structure exists."""
        assert sample_resumes_dir.exists()
        valid_dir = sample_resumes_dir / "valid"
        assert valid_dir.exists()
    
    # NOTE: These tests will be enabled once we add actual sample files
    @pytest.mark.skip(reason="Requires sample PDF file")
    def test_parse_valid_pdf(self, parser, sample_resumes_dir):
        """Test parsing a valid PDF resume."""
        pdf_path = sample_resumes_dir / "valid" / "simple_one_page.pdf"
        
        if pdf_path.exists():
            with open(pdf_path, 'rb') as f:
                file_bytes = f.read()
            
            result = parser.parse_pdf(file_bytes)
            assert result.success is True
            assert len(result.text) > 0
            assert result.page_count > 0
            assert result.confidence > 0.5
    
    @pytest.mark.skip(reason="Requires sample DOCX file")
    def test_parse_valid_docx(self, parser, sample_resumes_dir):
        """Test parsing a valid DOCX resume."""
        docx_path = sample_resumes_dir / "valid" / "sample.docx"
        
        if docx_path.exists():
            with open(docx_path, 'rb') as f:
                file_bytes = f.read()
            
            result = parser.parse_docx(file_bytes)
            assert result.success is True
            assert len(result.text) > 0
            assert result.confidence > 0.5
