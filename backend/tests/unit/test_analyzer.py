"""Unit tests for the Analyzer orchestrator.

Tests cover validation and normalization functionality (Task 5.1).

Requirements: 1.1, 1.2, 1.3, 1.4
"""

import pytest

from app.services.analyzer import Analyzer, ValidationError


class TestAnalyzerValidation:
    """Tests for Analyzer._validate() method.
    
    Requirements: 1.3, 1.4
    """
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analyzer = Analyzer()
    
    def test_validate_accepts_valid_text(self) -> None:
        """Valid non-empty text should pass validation."""
        # Should not raise
        self.analyzer._validate("This is valid text with financial claims.")
    
    def test_validate_accepts_single_character(self) -> None:
        """Single character text should pass validation."""
        self.analyzer._validate("a")
    
    def test_validate_accepts_text_at_max_length(self) -> None:
        """Text exactly at max length should pass validation."""
        text = "a" * 50000
        self.analyzer._validate(text)
    
    def test_validate_rejects_empty_string(self) -> None:
        """Empty string should raise ValidationError (Req 1.3)."""
        with pytest.raises(ValidationError) as exc_info:
            self.analyzer._validate("")
        
        assert "Non-empty text is required" in str(exc_info.value)
    
    def test_validate_rejects_whitespace_only_spaces(self) -> None:
        """Whitespace-only text (spaces) should raise ValidationError (Req 1.3)."""
        with pytest.raises(ValidationError) as exc_info:
            self.analyzer._validate("     ")
        
        assert "Non-empty text is required" in str(exc_info.value)
    
    def test_validate_rejects_whitespace_only_tabs(self) -> None:
        """Whitespace-only text (tabs) should raise ValidationError (Req 1.3)."""
        with pytest.raises(ValidationError) as exc_info:
            self.analyzer._validate("\t\t\t")
        
        assert "Non-empty text is required" in str(exc_info.value)
    
    def test_validate_rejects_whitespace_only_newlines(self) -> None:
        """Whitespace-only text (newlines) should raise ValidationError (Req 1.3)."""
        with pytest.raises(ValidationError) as exc_info:
            self.analyzer._validate("\n\n\n")
        
        assert "Non-empty text is required" in str(exc_info.value)
    
    def test_validate_rejects_whitespace_only_mixed(self) -> None:
        """Whitespace-only text (mixed) should raise ValidationError (Req 1.3)."""
        with pytest.raises(ValidationError) as exc_info:
            self.analyzer._validate("  \t\n  \r\n  ")
        
        assert "Non-empty text is required" in str(exc_info.value)
    
    def test_validate_rejects_text_exceeding_max_length(self) -> None:
        """Text exceeding 50,000 chars should raise ValidationError (Req 1.4)."""
        text = "a" * 50001
        
        with pytest.raises(ValidationError) as exc_info:
            self.analyzer._validate(text)
        
        assert "exceeds maximum allowed length" in str(exc_info.value)
        assert "50,000" in str(exc_info.value)
        assert "50,001" in str(exc_info.value)
    
    def test_validate_rejects_very_long_text(self) -> None:
        """Very long text should raise ValidationError with correct counts."""
        text = "x" * 100000
        
        with pytest.raises(ValidationError) as exc_info:
            self.analyzer._validate(text)
        
        assert "100,000" in str(exc_info.value)
    
    def test_validate_custom_max_length(self) -> None:
        """Custom max_input_length should be respected."""
        analyzer = Analyzer(max_input_length=100)
        
        # Should pass at exactly 100
        analyzer._validate("a" * 100)
        
        # Should fail at 101
        with pytest.raises(ValidationError):
            analyzer._validate("a" * 101)


class TestAnalyzerNormalization:
    """Tests for Analyzer._normalize() method.
    
    Requirements: 1.2
    """
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analyzer = Analyzer()
    
    def test_normalize_trims_leading_whitespace(self) -> None:
        """Leading whitespace should be trimmed (Req 1.2)."""
        result = self.analyzer._normalize("   Hello world")
        assert result == "Hello world"
    
    def test_normalize_trims_trailing_whitespace(self) -> None:
        """Trailing whitespace should be trimmed (Req 1.2)."""
        result = self.analyzer._normalize("Hello world   ")
        assert result == "Hello world"
    
    def test_normalize_trims_both_ends(self) -> None:
        """Both leading and trailing whitespace should be trimmed (Req 1.2)."""
        result = self.analyzer._normalize("   Hello world   ")
        assert result == "Hello world"
    
    def test_normalize_collapses_consecutive_spaces(self) -> None:
        """Consecutive spaces should be collapsed to single space (Req 1.2)."""
        result = self.analyzer._normalize("Hello    world")
        assert result == "Hello world"
    
    def test_normalize_collapses_tabs(self) -> None:
        """Tabs should be collapsed to single space (Req 1.2)."""
        result = self.analyzer._normalize("Hello\t\tworld")
        assert result == "Hello world"
    
    def test_normalize_collapses_newlines(self) -> None:
        """Newlines should be collapsed to single space (Req 1.2)."""
        result = self.analyzer._normalize("Hello\n\nworld")
        assert result == "Hello world"
    
    def test_normalize_collapses_mixed_whitespace(self) -> None:
        """Mixed whitespace should be collapsed to single space (Req 1.2)."""
        result = self.analyzer._normalize("Hello \t\n  world")
        assert result == "Hello world"
    
    def test_normalize_handles_complex_whitespace(self) -> None:
        """Complex whitespace patterns should be normalized (Req 1.2)."""
        result = self.analyzer._normalize("  \t Line1 \n\n\n Line2  \t  Line3  ")
        assert result == "Line1 Line2 Line3"
    
    def test_normalize_preserves_single_spaces(self) -> None:
        """Single spaces between words should be preserved (Req 1.2)."""
        result = self.analyzer._normalize("Hello world foo bar")
        assert result == "Hello world foo bar"
    
    def test_normalize_preserves_content_order(self) -> None:
        """Non-whitespace content order should be preserved (Req 1.2)."""
        result = self.analyzer._normalize("  A   B   C   D  ")
        assert result == "A B C D"
    
    def test_normalize_handles_carriage_returns(self) -> None:
        """Carriage returns should be normalized (Req 1.2)."""
        result = self.analyzer._normalize("Hello\r\nworld")
        assert result == "Hello world"
    
    def test_normalize_empty_after_trim_returns_empty(self) -> None:
        """Text that becomes empty after trim should return empty string."""
        result = self.analyzer._normalize("   ")
        assert result == ""


class TestAnalyzerAnalyze:
    """Tests for Analyzer.analyze() method.
    
    Requirements: 1.1, 1.2, 1.3, 1.4
    """
    
    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.analyzer = Analyzer()
    
    @pytest.mark.asyncio
    async def test_analyze_validates_input(self) -> None:
        """analyze() should validate input before processing (Req 1.3, 1.4)."""
        # Empty text should raise ValidationError
        with pytest.raises(ValidationError):
            await self.analyzer.analyze("")
        
        # Whitespace-only should raise ValidationError
        with pytest.raises(ValidationError):
            await self.analyzer.analyze("   ")
        
        # Oversized text should raise ValidationError
        with pytest.raises(ValidationError):
            await self.analyzer.analyze("x" * 60000)
    
    @pytest.mark.asyncio
    async def test_analyze_returns_response_for_valid_input(self) -> None:
        """analyze() should return AnalysisResponse for valid input (Req 1.1)."""
        response = await self.analyzer.analyze("The stock rose 10% yesterday.")
        
        # Check response structure
        assert response is not None
        assert hasattr(response, 'claims')
        assert hasattr(response, 'overall_classification')
        assert hasattr(response, 'trust_score')
        assert hasattr(response, 'explanation')
        assert hasattr(response, 'sources')
        assert hasattr(response, 'disclaimer')
    
    @pytest.mark.asyncio
    async def test_analyze_no_claims_response(self) -> None:
        """analyze() should return no-claims response when no claims found (Req 12.1)."""
        response = await self.analyzer.analyze("Test financial claim.")
        
        # When no claim extractor is configured, no claims are found
        assert response.claims == []
        assert response.overall_classification is None
        assert response.trust_score is None
        assert response.trust_score_breakdown is None
        assert response.sources == []
        # Should indicate no claims were detected
        assert "No financial claims" in response.explanation
    
    @pytest.mark.asyncio
    async def test_analyze_normalizes_input(self) -> None:
        """analyze() should normalize input text (Req 1.2)."""
        # Text with extra whitespace - should be normalized before processing
        response = await self.analyzer.analyze("  Hello   world  ")
        
        # The response should be valid (no claims found since no extractor)
        assert response.claims == []
        # Explanation should be present
        assert response.explanation is not None
        assert len(response.explanation) > 0


class TestValidationError:
    """Tests for ValidationError exception class."""
    
    def test_validation_error_message(self) -> None:
        """ValidationError should store and expose message."""
        error = ValidationError("Test error message")
        
        assert error.message == "Test error message"
        assert str(error) == "Test error message"
    
    def test_validation_error_is_exception(self) -> None:
        """ValidationError should be an Exception subclass."""
        error = ValidationError("Test")
        
        assert isinstance(error, Exception)
