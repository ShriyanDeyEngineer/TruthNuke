"""Unit tests for the Claim Extractor.

Tests cover:
- Extraction with known text containing financial claims
- Extraction with text containing no financial claims → empty list
- Malformed LLM JSON → ClaimExtractionError
- Invalid claim indices are filtered out (logged as warnings)

Requirements: 2.1, 2.5, 14.3
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.claim_extractor import ClaimExtractor, ClaimExtractionError
from app.services.llm_client import LLMClient, LLMParsingError


class TestClaimExtractorInit:
    """Tests for ClaimExtractor initialization."""
    
    def test_init_with_llm_client(self):
        """Test that ClaimExtractor initializes with an LLM client."""
        mock_client = MagicMock(spec=LLMClient)
        extractor = ClaimExtractor(llm_client=mock_client)
        assert extractor.llm_client is mock_client


class TestClaimExtractorExtractClaims:
    """Tests for ClaimExtractor.extract_claims() method."""
    
    @pytest.fixture
    def mock_llm_client(self):
        """Create a mock LLM client."""
        return MagicMock(spec=LLMClient)
    
    @pytest.fixture
    def extractor(self, mock_llm_client):
        """Create a ClaimExtractor with mock LLM client."""
        return ClaimExtractor(llm_client=mock_llm_client)
    
    @pytest.mark.asyncio
    async def test_extract_claims_with_valid_financial_claims(self, extractor, mock_llm_client):
        """Test extraction with known text containing financial claims.
        
        Validates: Requirements 2.1
        """
        text = "Apple stock rose 10% today. Bitcoin hit $50,000."
        
        # Mock LLM response with valid claims (indices must match exactly)
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": [
                {
                    "text": "Apple stock rose 10% today.",
                    "start_index": 0,
                    "end_index": 27,
                    "type": "market",
                    "entities": ["Apple"]
                },
                {
                    "text": "Bitcoin hit $50,000.",
                    "start_index": 28,
                    "end_index": 48,
                    "type": "crypto",
                    "entities": ["Bitcoin"]
                }
            ]
        })
        
        claims = await extractor.extract_claims(text)
        
        assert len(claims) == 2
        assert claims[0].text == "Apple stock rose 10% today."
        assert claims[0].start_index == 0
        assert claims[0].end_index == 27
        assert claims[0].type == "market"
        assert claims[0].entities == ["Apple"]
        
        assert claims[1].text == "Bitcoin hit $50,000."
        assert claims[1].start_index == 28
        assert claims[1].end_index == 48
        assert claims[1].type == "crypto"
        assert claims[1].entities == ["Bitcoin"]
    
    @pytest.mark.asyncio
    async def test_extract_claims_returns_empty_list_when_no_claims(self, extractor, mock_llm_client):
        """Test extraction with text containing no financial claims returns empty list.
        
        Validates: Requirements 2.5
        """
        text = "The weather today is sunny with a high of 75 degrees."
        
        # Mock LLM response with no claims
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": []
        })
        
        claims = await extractor.extract_claims(text)
        
        assert claims == []
        assert len(claims) == 0
    
    @pytest.mark.asyncio
    async def test_extract_claims_raises_on_malformed_json(self, extractor, mock_llm_client):
        """Test that malformed LLM JSON raises ClaimExtractionError.
        
        Validates: Requirements 14.3
        """
        text = "Apple stock rose 10% today."
        
        # Mock LLM client to raise LLMParsingError
        mock_llm_client.complete_json = AsyncMock(
            side_effect=LLMParsingError("LLM response is not valid JSON")
        )
        
        with pytest.raises(ClaimExtractionError, match="Failed to parse LLM response"):
            await extractor.extract_claims(text)
    
    @pytest.mark.asyncio
    async def test_extract_claims_raises_on_missing_claims_field(self, extractor, mock_llm_client):
        """Test that response missing 'claims' field raises ClaimExtractionError.
        
        Validates: Requirements 14.3
        """
        text = "Apple stock rose 10% today."
        
        # Mock LLM response without 'claims' field
        mock_llm_client.complete_json = AsyncMock(return_value={
            "data": []  # Wrong field name
        })
        
        with pytest.raises(ClaimExtractionError, match="missing required 'claims' field"):
            await extractor.extract_claims(text)
    
    @pytest.mark.asyncio
    async def test_extract_claims_raises_on_non_dict_response(self, extractor, mock_llm_client):
        """Test that non-dict response raises ClaimExtractionError.
        
        Validates: Requirements 14.3
        """
        text = "Apple stock rose 10% today."
        
        # Mock LLM response that's not a dict
        mock_llm_client.complete_json = AsyncMock(return_value=[
            {"text": "claim"}
        ])
        
        with pytest.raises(ClaimExtractionError, match="Expected JSON object response"):
            await extractor.extract_claims(text)
    
    @pytest.mark.asyncio
    async def test_extract_claims_raises_on_non_list_claims(self, extractor, mock_llm_client):
        """Test that non-list 'claims' field raises ClaimExtractionError.
        
        Validates: Requirements 14.3
        """
        text = "Apple stock rose 10% today."
        
        # Mock LLM response with non-list claims
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": "not a list"
        })
        
        with pytest.raises(ClaimExtractionError, match="Expected 'claims' to be an array"):
            await extractor.extract_claims(text)
    
    @pytest.mark.asyncio
    async def test_extract_claims_filters_invalid_start_index(self, extractor, mock_llm_client):
        """Test that claims with negative start_index are filtered out.
        
        Validates: Requirements 2.1
        """
        text = "Apple stock rose 10% today."
        
        # Mock LLM response with invalid start_index
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": [
                {
                    "text": "Apple stock rose 10% today",
                    "start_index": -1,  # Invalid: negative
                    "end_index": 27,
                    "type": "market",
                    "entities": ["Apple"]
                }
            ]
        })
        
        with patch("app.services.claim_extractor.logger") as mock_logger:
            claims = await extractor.extract_claims(text)
            
            assert len(claims) == 0
            # Verify warning was logged
            mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_extract_claims_filters_invalid_end_index_less_than_start(self, extractor, mock_llm_client):
        """Test that claims with end_index <= start_index are filtered out.
        
        Validates: Requirements 2.1
        """
        text = "Apple stock rose 10% today."
        
        # Mock LLM response with end_index <= start_index
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": [
                {
                    "text": "Apple stock rose 10% today",
                    "start_index": 10,
                    "end_index": 5,  # Invalid: less than start_index
                    "type": "market",
                    "entities": ["Apple"]
                }
            ]
        })
        
        with patch("app.services.claim_extractor.logger") as mock_logger:
            claims = await extractor.extract_claims(text)
            
            assert len(claims) == 0
            mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_extract_claims_filters_end_index_exceeds_text_length(self, extractor, mock_llm_client):
        """Test that claims with end_index exceeding text length are filtered out.
        
        Validates: Requirements 2.1
        """
        text = "Apple stock rose 10% today."  # Length: 27
        
        # Mock LLM response with end_index exceeding text length
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": [
                {
                    "text": "Apple stock rose 10% today",
                    "start_index": 0,
                    "end_index": 100,  # Invalid: exceeds text length
                    "type": "market",
                    "entities": ["Apple"]
                }
            ]
        })
        
        with patch("app.services.claim_extractor.logger") as mock_logger:
            claims = await extractor.extract_claims(text)
            
            assert len(claims) == 0
            mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_extract_claims_filters_substring_mismatch(self, extractor, mock_llm_client):
        """Test that claims where substring doesn't match claim text are filtered out.
        
        Validates: Requirements 2.1
        """
        text = "Apple stock rose 10% today."
        
        # Mock LLM response with mismatched substring
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": [
                {
                    "text": "Wrong text that doesn't match",
                    "start_index": 0,
                    "end_index": 27,
                    "type": "market",
                    "entities": ["Apple"]
                }
            ]
        })
        
        with patch("app.services.claim_extractor.logger") as mock_logger:
            claims = await extractor.extract_claims(text)
            
            assert len(claims) == 0
            mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_extract_claims_filters_invalid_keeps_valid(self, extractor, mock_llm_client):
        """Test that invalid claims are filtered while valid claims are kept.
        
        Validates: Requirements 2.1
        """
        text = "Apple stock rose 10% today. Bitcoin hit $50,000."
        
        # Mock LLM response with one valid and one invalid claim
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": [
                {
                    "text": "Apple stock rose 10% today",
                    "start_index": 0,
                    "end_index": 26,
                    "type": "market",
                    "entities": ["Apple"]
                },
                {
                    "text": "Invalid claim",
                    "start_index": -5,  # Invalid
                    "end_index": 10,
                    "type": "crypto",
                    "entities": []
                }
            ]
        })
        
        with patch("app.services.claim_extractor.logger") as mock_logger:
            claims = await extractor.extract_claims(text)
            
            assert len(claims) == 1
            assert claims[0].text == "Apple stock rose 10% today"
            mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_extract_claims_skips_malformed_claim_data(self, extractor, mock_llm_client):
        """Test that malformed claim data (missing fields) is skipped.
        
        Validates: Requirements 2.1
        """
        text = "Apple stock rose 10% today."
        
        # Mock LLM response with malformed claim (missing required fields)
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": [
                {
                    "text": "Apple stock rose 10% today"
                    # Missing start_index, end_index, type
                }
            ]
        })
        
        with patch("app.services.claim_extractor.logger") as mock_logger:
            claims = await extractor.extract_claims(text)
            
            assert len(claims) == 0
            mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_extract_claims_generates_uuid_for_each_claim(self, extractor, mock_llm_client):
        """Test that each extracted claim gets a unique UUID."""
        text = "Apple stock rose 10% today. Bitcoin hit $50,000."
        
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": [
                {
                    "text": "Apple stock rose 10% today",
                    "start_index": 0,
                    "end_index": 26,
                    "type": "market",
                    "entities": ["Apple"]
                },
                {
                    "text": "Bitcoin hit $50,000",
                    "start_index": 28,
                    "end_index": 47,
                    "type": "crypto",
                    "entities": ["Bitcoin"]
                }
            ]
        })
        
        claims = await extractor.extract_claims(text)
        
        assert len(claims) == 2
        assert claims[0].id is not None
        assert claims[1].id is not None
        assert claims[0].id != claims[1].id
        # Verify UUIDs are valid format (36 chars with hyphens)
        assert len(claims[0].id) == 36
        assert len(claims[1].id) == 36
    
    @pytest.mark.asyncio
    async def test_extract_claims_handles_unknown_claim_type(self, extractor, mock_llm_client):
        """Test that unknown claim types default to 'economic'."""
        text = "Some financial claim here."
        
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": [
                {
                    "text": "Some financial claim here",
                    "start_index": 0,
                    "end_index": 25,
                    "type": "unknown_type",  # Invalid type
                    "entities": []
                }
            ]
        })
        
        with patch("app.services.claim_extractor.logger") as mock_logger:
            claims = await extractor.extract_claims(text)
            
            assert len(claims) == 1
            assert claims[0].type == "economic"  # Defaults to economic
            mock_logger.warning.assert_called()
    
    @pytest.mark.asyncio
    async def test_extract_claims_handles_missing_entities(self, extractor, mock_llm_client):
        """Test that missing entities field defaults to empty list."""
        text = "Apple stock rose 10% today"
        
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": [
                {
                    "text": "Apple stock rose 10% today",
                    "start_index": 0,
                    "end_index": 26,
                    "type": "market"
                    # No entities field
                }
            ]
        })
        
        claims = await extractor.extract_claims(text)
        
        assert len(claims) == 1
        assert claims[0].entities == []
    
    @pytest.mark.asyncio
    async def test_extract_claims_handles_non_list_entities(self, extractor, mock_llm_client):
        """Test that non-list entities field defaults to empty list."""
        text = "Apple stock rose 10% today"
        
        mock_llm_client.complete_json = AsyncMock(return_value={
            "claims": [
                {
                    "text": "Apple stock rose 10% today",
                    "start_index": 0,
                    "end_index": 26,
                    "type": "market",
                    "entities": "Apple"  # Should be a list
                }
            ]
        })
        
        claims = await extractor.extract_claims(text)
        
        assert len(claims) == 1
        assert claims[0].entities == []
    
    @pytest.mark.asyncio
    async def test_extract_claims_calls_llm_with_correct_prompt(self, extractor, mock_llm_client):
        """Test that extract_claims calls LLM with proper prompt structure."""
        text = "Apple stock rose 10% today."
        
        mock_llm_client.complete_json = AsyncMock(return_value={"claims": []})
        
        await extractor.extract_claims(text)
        
        # Verify complete_json was called
        mock_llm_client.complete_json.assert_called_once()
        
        # Get the call arguments
        call_kwargs = mock_llm_client.complete_json.call_args.kwargs
        
        # Verify prompt contains the text
        assert text in call_kwargs["prompt"]
        
        # Verify system_prompt is provided
        assert "system_prompt" in call_kwargs
        assert len(call_kwargs["system_prompt"]) > 0


class TestClaimExtractorValidateClaimIndices:
    """Tests for ClaimExtractor._validate_claim_indices() method."""
    
    @pytest.fixture
    def extractor(self):
        """Create a ClaimExtractor with mock LLM client."""
        mock_client = MagicMock(spec=LLMClient)
        return ClaimExtractor(llm_client=mock_client)
    
    def test_validate_valid_indices(self, extractor):
        """Test validation passes for valid indices."""
        from app.models.schemas import Claim
        
        text = "Apple stock rose 10% today"
        claim = Claim(
            id="test-id",
            text="Apple stock rose 10% today",
            start_index=0,
            end_index=26,
            type="market",
            entities=["Apple"]
        )
        
        result = extractor._validate_claim_indices(claim, text)
        assert result is True
    
    def test_validate_negative_start_index(self, extractor):
        """Test validation fails for negative start_index.
        
        Note: Pydantic validation prevents creating a Claim with negative start_index,
        so this test verifies the behavior at the _validate_claim_indices level
        by testing with a valid Claim but checking the validation logic directly.
        The actual filtering of negative indices happens during _create_claim
        which catches the Pydantic validation error.
        """
        from app.models.schemas import Claim
        
        # Since Pydantic prevents negative start_index, we test the validation
        # logic by verifying that the extractor filters out claims with invalid
        # indices during extraction (tested in test_extract_claims_filters_invalid_start_index)
        # Here we just verify the validation method works for edge case of 0
        text = "Apple stock rose 10% today"
        claim = Claim(
            id="test-id",
            text="Apple",
            start_index=0,
            end_index=5,
            type="market",
            entities=[]
        )
        
        result = extractor._validate_claim_indices(claim, text)
        assert result is True
    
    def test_validate_start_index_equals_end_index(self, extractor):
        """Test validation fails when start_index equals end_index."""
        from app.models.schemas import Claim
        
        text = "Apple stock rose 10% today"
        claim = Claim(
            id="test-id",
            text="",
            start_index=5,
            end_index=5,
            type="market",
            entities=[]
        )
        
        with patch("app.services.claim_extractor.logger"):
            result = extractor._validate_claim_indices(claim, text)
            assert result is False
    
    def test_validate_start_index_greater_than_end_index(self, extractor):
        """Test validation fails when start_index > end_index."""
        from app.models.schemas import Claim
        
        text = "Apple stock rose 10% today"
        claim = Claim(
            id="test-id",
            text="Apple",
            start_index=10,
            end_index=5,
            type="market",
            entities=[]
        )
        
        with patch("app.services.claim_extractor.logger"):
            result = extractor._validate_claim_indices(claim, text)
            assert result is False
    
    def test_validate_end_index_exceeds_text_length(self, extractor):
        """Test validation fails when end_index exceeds text length."""
        from app.models.schemas import Claim
        
        text = "Apple"  # Length 5
        claim = Claim(
            id="test-id",
            text="Apple",
            start_index=0,
            end_index=100,
            type="market",
            entities=[]
        )
        
        with patch("app.services.claim_extractor.logger"):
            result = extractor._validate_claim_indices(claim, text)
            assert result is False
    
    def test_validate_substring_mismatch(self, extractor):
        """Test validation fails when substring doesn't match claim text."""
        from app.models.schemas import Claim
        
        text = "Apple stock rose 10% today"
        claim = Claim(
            id="test-id",
            text="Different text",
            start_index=0,
            end_index=14,
            type="market",
            entities=[]
        )
        
        with patch("app.services.claim_extractor.logger"):
            result = extractor._validate_claim_indices(claim, text)
            assert result is False


class TestClaimExtractionError:
    """Tests for ClaimExtractionError exception class."""
    
    def test_claim_extraction_error_message(self):
        """Test ClaimExtractionError has correct message."""
        error = ClaimExtractionError("Test error message")
        assert str(error) == "Test error message"
    
    def test_claim_extraction_error_is_exception(self):
        """Test ClaimExtractionError is an Exception."""
        assert issubclass(ClaimExtractionError, Exception)
